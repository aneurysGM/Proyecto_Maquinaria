from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from usuarios.roles import TECNICO


class Command(BaseCommand):
    help = 'Crea o asigna una cuenta al grupo Técnico, conservando contraseña y grupos existentes.'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--nombre', default=None)
        parser.add_argument('--apellido', default=None)

    @transaction.atomic
    def handle(self, *args, **options):
        usuario, creado = get_user_model().objects.get_or_create(username=options['username'])
        if not creado and (usuario.is_staff or usuario.is_superuser):
            raise CommandError('Esta cuenta tiene privilegios administrativos. Usa una cuenta de técnico separada.')
        if creado:
            usuario.set_unusable_password()
        for opcion, campo in (('nombre', 'first_name'), ('apellido', 'last_name')):
            if options[opcion] is not None:
                setattr(usuario, campo, options[opcion])
        usuario.save()
        grupo, _ = Group.objects.get_or_create(name=TECNICO)
        usuario.groups.add(grupo)
        self.stdout.write(self.style.SUCCESS(f'Cuenta {usuario.username} asignada al grupo {TECNICO}.'))
        self.stdout.write(f'Establece su contraseña con: python manage.py changepassword {usuario.username}')
