from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0004_anio_fabricacion_unidad')]

    operations = [
        migrations.AddField(
            model_name='maquinaria',
            name='fecha_modificacion',
            field=models.DateTimeField(
                blank=True, null=True, editable=False, db_column='FechaModificacion',
            ),
        ),
        migrations.AddField(
            model_name='unidad',
            name='fecha_modificacion',
            field=models.DateTimeField(
                blank=True, null=True, editable=False, db_column='FechaModificacion',
            ),
        ),
    ]
