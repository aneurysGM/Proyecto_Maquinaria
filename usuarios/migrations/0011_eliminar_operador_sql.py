"""Retirada física con respaldo verificado y rechazo de dependencias ajenas.

0009 conservó la tabla deliberadamente. Esta migración completa la retirada
sin tocar alquileres, unidades ni mantenimiento. No tiene reversión automática:
los registros retirados se recuperan del respaldo, nunca de datos inventados.
"""
import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import PureWindowsPath

from django.db import migrations, transaction


def comprobar_dependencias(connection):
    """No se eliminan FK, columnas ni objetos de otros módulos por cascada."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'VIEW DEFINITION')")
        if cursor.fetchone()[0] != 1:
            raise RuntimeError('Se requiere VIEW DEFINITION para inspeccionar todas las dependencias SQL.')
        cursor.execute("SELECT OBJECT_ID(N'dbo.Operador', N'U')")
        objeto = cursor.fetchone()[0]
        if objeto is None:
            return False
        cursor.execute('''
            SELECT name FROM sys.foreign_keys
            WHERE referenced_object_id = %s AND parent_object_id <> %s
            UNION ALL
            SELECT OBJECT_NAME(referencing_id)
            FROM sys.sql_expression_dependencies
            WHERE referenced_id = %s AND referencing_id <> %s
            UNION ALL
            SELECT OBJECT_NAME(object_id) FROM sys.sql_modules
            WHERE object_id <> %s AND (
                LOWER(definition) LIKE '%%operador%%' OR definition IS NULL
            )
            UNION ALL
            SELECT name FROM sys.synonyms
            WHERE LOWER(base_object_name) LIKE '%%operador%%'
            UNION ALL
            SELECT OBJECT_SCHEMA_NAME(object_id) + '.' + OBJECT_NAME(object_id) + '.' + name
            FROM sys.columns
            WHERE object_id <> %s AND LOWER(name) LIKE '%%operador%%'
        ''', [objeto] * 6)
        dependencias = sorted({fila[0] for fila in cursor.fetchall()})
        if dependencias:
            raise RuntimeError(
                'No se retirará Operador: hay dependencias SQL que requieren '
                'revisión sin alterar datos de otros módulos: '
                + ', '.join(dependencias)
            )
    return True


def respaldar_y_verificar(connection):
    if connection.in_atomic_block or not connection.get_autocommit():
        raise RuntimeError('El respaldo requiere una conexión sin transacción activa.')
    with connection.cursor() as cursor:
        cursor.execute("SELECT DB_NAME(), CONVERT(nvarchar(4000), SERVERPROPERTY('InstanceDefaultBackupPath'))")
        base, directorio = cursor.fetchone()
        if not directorio:
            raise RuntimeError('SQL Server no informa su directorio de respaldos; no se eliminará Operador.')
        nombre = re.sub(r'[^\w.-]', '_', base)
        sello = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        fichero = f'{nombre}_pre_retirada_operadores_{sello}_{uuid.uuid4().hex[:8]}.bak'
        archivo = (
            str(PureWindowsPath(directorio) / fichero) if '\\' in directorio
            else directorio.rstrip('/') + '/' + fichero
        )
        cursor.execute(
            'BACKUP DATABASE ' + connection.ops.quote_name(base)
            + ' TO DISK = %s WITH COPY_ONLY, CHECKSUM', [archivo],
        )
        while cursor.nextset():
            pass
        cursor.execute('RESTORE VERIFYONLY FROM DISK = %s WITH CHECKSUM, STOP_ON_ERROR', [archivo])
        while cursor.nextset():
            pass
    print(f'\nRespaldo de {base} verificado con CHECKSUM: {archivo}', flush=True)
    return archivo


def huella_operadores(connection):
    with connection.cursor() as cursor:
        cursor.execute('SELECT * FROM [dbo].[Operador] ORDER BY [IdOperador]')
        return hashlib.sha256(repr(cursor.fetchall()).encode()).hexdigest()


def retirar_operador(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == 'microsoft':
        existe = comprobar_dependencias(connection)
        if existe:
            huella = huella_operadores(connection)
            # BACKUP no puede ejecutarse dentro de una transacción SQL Server.
            respaldar_y_verificar(connection)
    elif connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            existe = 'Operador' in connection.introspection.table_names(cursor)
            if existe:
                cursor.execute('SELECT COUNT(*) FROM "Operador"')
                if cursor.fetchone()[0]:
                    raise RuntimeError('Operador contiene datos en SQLite. Respáldalos y migra a SQL Server antes de retirarlo.')
    else:
        raise RuntimeError('La retirada con respaldo solo está implementada para SQL Server.')

    with transaction.atomic(using=connection.alias):
        if existe:
            if connection.vendor == 'microsoft':
                # Impide nuevas escrituras y vuelve a revisar antes del DROP.
                with connection.cursor() as cursor:
                    cursor.execute('SELECT COUNT_BIG(*) FROM [dbo].[Operador] WITH (TABLOCKX, HOLDLOCK)')
                    cursor.fetchone()
                comprobar_dependencias(connection)
                if huella_operadores(connection) != huella:
                    raise RuntimeError('Operador cambió durante el respaldo. No se eliminará; repetir con las escrituras detenidas.')
                schema_editor.execute('DROP TABLE [dbo].[Operador]')
            else:
                schema_editor.execute('DROP TABLE "Operador"')
        alias = connection.alias
        Permission = apps.get_model('auth', 'Permission')
        Permission.objects.using(alias).filter(
            content_type__app_label='usuarios', content_type__model='operador',
        ).delete()
        # El ContentType se conserva como metadato de auditoría: no tocar logs.
        Group = apps.get_model('auth', 'Group')
        Group.objects.using(alias).filter(name__in=['Supervisor', 'Operador']).delete()


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('usuarios', '0010_solicitudes_alquiler')]
    operations = [migrations.RunPython(retirar_operador, atomic=False)]
