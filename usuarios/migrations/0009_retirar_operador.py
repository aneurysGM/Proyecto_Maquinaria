"""Retira el modelo activo; preserva la tabla legacy y sus relaciones SQL."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0008_roles_cliente')]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[migrations.DeleteModel(name='Operador')],
        ),
    ]
