"""Adopta la tabla legacy sin reemplazar filas ni atribuir técnicos históricos."""

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def integrar_mantenimiento(apps, schema_editor):
    modelo = apps.get_model('usuarios', 'Mantenimiento')
    connection = schema_editor.connection
    tabla = modelo._meta.db_table
    qn = schema_editor.quote_name
    with connection.cursor() as cursor:
        tablas = connection.introspection.table_names(cursor)
        if tabla.lower() not in {nombre.lower() for nombre in tablas}:
            schema_editor.create_model(modelo)
            return
        if connection.vendor != 'microsoft':
            raise RuntimeError('La adopción de Mantenimiento legacy requiere SQL Server.')
        # Validar todo antes del primer ALTER. Nunca corregir o eliminar filas aquí.
        cursor.execute('''SELECT c.name, t.name, c.max_length, c.precision, c.scale,
            c.is_nullable, c.is_identity FROM sys.columns c
            JOIN sys.types t ON c.user_type_id=t.user_type_id
            WHERE c.object_id=OBJECT_ID(%s)''', [tabla])
        columnas = {fila[0].lower(): fila[1:] for fila in cursor.fetchall()}
        esperadas = {
            'mantenimientoid', 'unidadid', 'fechainicio', 'fechafin', 'tipo', 'costo', 'descripcion',
        }
        if not esperadas.issubset(columnas):
            raise RuntimeError('Mantenimiento tiene un esquema incompatible: faltan columnas legacy.')
        if 'tecnicoresponsableid' in columnas:
            raise RuntimeError('TecnicoResponsableID ya existe sin esta migración. Revisa el esquema.')
        for nombre in esperadas:
            tipo, longitud, precision, escala, nullable, identidad = columnas[nombre]
            if nombre in ('mantenimientoid', 'unidadid'):
                compatible = tipo == 'int' and not nullable
                if nombre == 'mantenimientoid':
                    compatible = compatible and identidad
            elif nombre in ('fechainicio', 'fechafin'):
                compatible = tipo == 'date' and nullable == (nombre == 'fechafin')
            elif nombre == 'costo':
                compatible = tipo in ('decimal', 'numeric') and precision >= 18 and escala == 2 and not nullable
            else:
                minimo = 12 if nombre == 'tipo' else 300
                compatible = tipo in ('varchar', 'nvarchar') and (
                    longitud == -1 or longitud >= minimo * (2 if tipo == 'nvarchar' else 1)
                ) and nullable == (nombre == 'descripcion')
            if not compatible:
                raise RuntimeError(f'Mantenimiento tiene una columna incompatible: {nombre}. No se modificaron datos.')
        restricciones = connection.introspection.get_constraints(cursor, tabla)
        if not any(c['primary_key'] and c['columns'] == ['MantenimientoID'] for c in restricciones.values()):
            raise RuntimeError('MantenimientoID debe ser la clave primaria legacy.')
        unidad = modelo._meta.get_field('unidad')
        tabla_unidad = unidad.remote_field.model._meta.db_table
        cursor.execute(
            f'''SELECT COUNT(*) FROM {qn(tabla)} m LEFT JOIN {qn(tabla_unidad)} u
                ON m.[UnidadID]=u.[UnidadID] WHERE u.[UnidadID] IS NULL
                OR m.[Costo]<0 OR m.[Tipo] NOT IN ('Preventivo','Correctivo')'''
        )
        if cursor.fetchone()[0]:
            raise RuntimeError('Hay mantenimientos con unidad inexistente, costo negativo o tipo inválido. Revisa los registros sin borrar datos.')
        relaciones = [c['foreign_key'] for c in restricciones.values() if c['columns'] == ['UnidadID'] and c['foreign_key']]
        if any((destino.lower(), columna.lower()) != (tabla_unidad.lower(), 'unidadid') for destino, columna in relaciones):
            raise RuntimeError('UnidadID tiene una relación incompatible. Revisa el esquema.')
        if any(c.name in restricciones for c in modelo._meta.constraints):
            raise RuntimeError('Ya existen restricciones HU-07 sin esta migración. Revisa el esquema.')
    schema_editor.add_field(modelo, modelo._meta.get_field('tecnico'))
    if not relaciones:
        schema_editor.execute(schema_editor._create_fk_sql(modelo, unidad, '_hu07_fk'))
    for restriccion in modelo._meta.constraints:
        schema_editor.add_constraint(modelo, restriccion)


def crear_grupo_tecnico(apps, schema_editor):
    apps.get_model('auth', 'Group').objects.using(schema_editor.connection.alias).get_or_create(name='Técnico')


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0006_integrar_operador'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[migrations.CreateModel(
            name='Mantenimiento',
            fields=[
                ('id', models.AutoField(db_column='MantenimientoID', primary_key=True, serialize=False)),
                ('fecha', models.DateField(db_column='FechaInicio')),
                ('fecha_fin', models.DateField(blank=True, db_column='FechaFin', editable=False, null=True)),
                ('tipo', models.CharField(choices=[('Preventivo', 'Preventivo'), ('Correctivo', 'Correctivo')], db_column='Tipo', max_length=12)),
                ('descripcion', models.CharField(blank=True, db_column='Descripcion', max_length=300, null=True)),
                ('costo', models.DecimalField(db_column='Costo', decimal_places=2, max_digits=18, validators=[django.core.validators.MinValueValidator(0)])),
                ('tecnico', models.ForeignKey(blank=True, db_column='TecnicoResponsableID', editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='mantenimientos_registrados', to=settings.AUTH_USER_MODEL)),
                ('unidad', models.ForeignKey(db_column='UnidadID', on_delete=django.db.models.deletion.PROTECT, related_name='mantenimientos', to='usuarios.unidad')),
            ],
            options={
                'db_table': 'Mantenimiento',
                'ordering': ('-fecha', '-id'),
                'constraints': [models.CheckConstraint(condition=models.Q(('costo__gte', 0)), name='CK_Mantenimiento_Costo_NoNegativo'), models.CheckConstraint(condition=models.Q(('tipo__in', ['Preventivo', 'Correctivo'])), name='CK_Mantenimiento_Tipo_Valido')],
            },
            )],
        ),
        # Adopción irreversible: retroceder no debe eliminar una tabla del negocio.
        migrations.RunPython(integrar_mantenimiento),
        migrations.RunPython(crear_grupo_tecnico, migrations.RunPython.noop),
    ]
