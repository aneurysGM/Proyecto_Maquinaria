"""Adopta Operador sin reemplazar filas y protege la identidad normalizada."""

import django.utils.timezone
import usuarios.validators
from django.db import migrations, models
from django.db.models.functions import Replace


# Congelado para que cambios futuros en validadores no alteren esta migración.
SEPARADORES = '- \t\n\r\v\f\x1c\x1d\x1e\x1f\x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000'


def expresion_cedula():
    expresion = models.F('cedula')
    for separador in SEPARADORES:
        expresion = Replace(expresion, models.Value(separador), models.Value(''))
    return expresion


def integrar_operador(apps, schema_editor):
    modelo = apps.get_model('usuarios', 'Operador')
    connection = schema_editor.connection
    tabla = modelo._meta.db_table
    with connection.cursor() as cursor:
        tablas = connection.introspection.table_names(cursor)
        if tabla.lower() not in {nombre.lower() for nombre in tablas}:
            schema_editor.create_model(modelo)
            return
        descripcion = connection.introspection.get_table_description(cursor, tabla)
        columnas = {columna.name.lower(): columna for columna in descripcion}
        esperadas = {campo.column.lower() for campo in modelo._meta.local_fields if not campo.generated}
        if not esperadas.issubset(columnas):
            raise RuntimeError('Operador tiene un esquema incompatible: faltan columnas legacy. No se reemplazará la tabla.')
        if 'cedulanormalizada' in columnas:
            raise RuntimeError('CedulaNormalizada ya existe sin esta migración; revisa el esquema antes de continuar.')
        cursor.execute('SELECT [Cedula] FROM ' + schema_editor.quote_name(tabla))
        vistas = set()
        traduccion = str.maketrans('', '', SEPARADORES)
        for (cedula,) in cursor.fetchall():
            normalizada = cedula.translate(traduccion)
            if not normalizada or normalizada in vistas:
                raise RuntimeError('Hay cédulas vacías o duplicadas tras normalizar. Resuelve los registros sin eliminar datos antes de migrar.')
            vistas.add(normalizada)
    # Columna calculada: también protege inserciones que no pasan por el formulario.
    schema_editor.add_field(modelo, modelo._meta.get_field('cedula_normalizada'))


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0005_fechas_modificacion_maquinaria_unidad')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[migrations.CreateModel(
                name='Operador',
                fields=[
                    ('id', models.AutoField(db_column='IdOperador', primary_key=True, serialize=False)),
                    ('cedula', models.CharField(db_column='Cedula', max_length=20, unique=True, validators=[usuarios.validators.validar_cedula])),
                    ('cedula_normalizada', models.GeneratedField(db_column='CedulaNormalizada', db_persist=True, expression=expresion_cedula(), output_field=models.CharField(max_length=20), unique=True)),
                    ('nombre', models.CharField(db_column='Nombre', max_length=80)),
                    ('apellido', models.CharField(blank=True, db_column='Apellido', default='', max_length=80)),
                    ('telefono', models.CharField(blank=True, db_column='Telefono', max_length=20, null=True)),
                    ('email', models.EmailField(blank=True, db_column='Email', max_length=100, null=True)),
                    ('direccion', models.CharField(blank=True, db_column='Direccion', max_length=200, null=True)),
                    ('fecha_nacimiento', models.DateField(blank=True, db_column='FechaNacimiento', null=True)),
                    ('fecha_contratacion', models.DateField(blank=True, db_column='FechaContratacion', null=True)),
                    ('numero_licencia', models.CharField(blank=True, db_column='NumeroLicencia', max_length=30, null=True)),
                    ('tipo_licencia', models.CharField(blank=True, db_column='CategoriaLicencia', max_length=10, null=True)),
                    ('fecha_vencimiento', models.DateField(blank=True, db_column='FechaVencimientoLicencia', null=True)),
                    ('estado', models.CharField(db_column='Estado', default='Activo', max_length=20)),
                    ('fecha_creacion', models.DateTimeField(db_column='FechaCreacion', default=django.utils.timezone.now, editable=False)),
                ],
                options={'db_table': 'Operador', 'ordering': ('nombre', 'apellido', 'id')},
            )],
        ),
        # Irreversible: revertir una adopción no debe borrar una tabla del negocio.
        migrations.RunPython(integrar_operador),
    ]
