"""Retira roles anteriores sin convertir empleados en clientes."""
from django.db import migrations


def actualizar_roles(apps, schema_editor):
    alias = schema_editor.connection.alias
    Group = apps.get_model('auth', 'Group')
    Group.objects.using(alias).get_or_create(name='Cliente')
    Group.objects.using(alias).get_or_create(name='Técnico')
    # Conserva cuentas, contraseñas y registros; retira membresías y permisos del grupo.
    Group.objects.using(alias).filter(name__in=['Supervisor', 'Operador']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0007_integrar_mantenimiento'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [migrations.RunPython(actualizar_roles)]
