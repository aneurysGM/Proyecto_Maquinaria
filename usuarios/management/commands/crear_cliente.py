from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from usuarios.roles import CLIENTE


class Command(BaseCommand):
    help = 'Crea una cuenta de cliente en el grupo Cliente, sin acceso a Django Admin.'

    def add_arguments(self, parser):
        parser.add_argument('username', nargs='?', default='cliente')
        parser.add_argument('--nombre', default=None)
        parser.add_argument('--apellido', default=None)

    @transaction.atomic
    def handle(self, *args, **options):
        usuario, creado = get_user_model().objects.get_or_create(
            username=options['username'],
            defaults={'is_staff': False, 'is_superuser': False},
        )
        if not creado and (usuario.is_staff or usuario.is_superuser):
            raise CommandError(
                'Esta cuenta tiene privilegios administrativos. Usa otro nombre '
                'para mantener al administrador separado.'
            )
        if creado:
            usuario.set_unusable_password()
        for opcion, campo in (('nombre', 'first_name'), ('apellido', 'last_name')):
            if options[opcion] is not None:
                setattr(usuario, campo, options[opcion])
        usuario.save()
        grupo, _ = Group.objects.get_or_create(name=CLIENTE)
        usuario.groups.remove(*Group.objects.filter(name__in=['Técnico', 'Supervisor', 'Operador']))
        usuario.groups.add(grupo)
        self.stdout.write(self.style.SUCCESS(
            f'Cuenta {usuario.username} asignada al grupo {CLIENTE}; '
            'sin permisos de superusuario ni acceso a Django Admin.'
        ))
        self.stdout.write(f'Establece su contraseña con: python manage.py changepassword {usuario.username}')
