from importlib import import_module
from contextlib import closing
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.db.migrations.state import ProjectState
from django.test import TestCase
from django.urls import reverse

from .roles import CLIENTE, TECNICO, permisos_panel
from .management.commands.migrar_datos_locales import Command as ImportarDatos


class CambioRolesTests(TestCase):
    def migrar(self):
        migracion = import_module('usuarios.migrations.0008_roles_cliente')
        estado = ProjectState.from_apps(apps)
        migracion.actualizar_roles(estado.apps, SimpleNamespace(connection=connection))

    def test_migracion_conserva_cuentas_y_fusiona_membresias_sin_elevar_permisos(self):
        supervisor = Group.objects.create(name='Supervisor')
        permiso = Permission.objects.get(codename='add_user')
        supervisor.permissions.add(permiso)
        cliente, _ = Group.objects.get_or_create(name=CLIENTE)
        tecnico, _ = Group.objects.get_or_create(name=TECNICO)
        usuario = get_user_model().objects.create_user(
            username='cuenta_existente', password='ClaveExistente123!',
            first_name='Luis', is_active=False,
        )
        usuario.groups.add(supervisor, cliente, tecnico)
        get_user_model().objects.create_superuser(username='admin_roles')
        antes = list(get_user_model().objects.order_by('pk').values())
        self.migrar()
        self.migrar()
        self.assertEqual(antes, list(get_user_model().objects.order_by('pk').values()))
        self.assertFalse(Group.objects.filter(name='Supervisor').exists())
        self.assertEqual(set(usuario.groups.values_list('name', flat=True)), {CLIENTE, TECNICO})
        self.assertFalse(cliente.permissions.filter(pk=permiso.pk).exists())
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password('ClaveExistente123!'))

    def test_migracion_retira_acceso_sin_convertir_empleado_en_cliente(self):
        usuario = get_user_model().objects.create_user(username='anterior_supervisor')
        usuario.groups.add(Group.objects.create(name='Supervisor'))
        self.migrar()
        self.assertEqual(list(usuario.groups.values_list('name', flat=True)), [])
        self.client.force_login(usuario)
        self.assertContains(self.client.get(reverse('dashboard')), 'Sin rol asignado')

    def test_roles_retirados_no_habilitan_acceso_aunque_se_recreen(self):
        for nombre in ('Supervisor', 'Operador'):
            usuario = get_user_model().objects.create_user(username=nombre)
            usuario.groups.add(Group.objects.create(name=nombre))
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse('maquinaria_lista')).status_code, 403)
            for metodo in (self.client.get, self.client.post):
                self.assertEqual(metodo('/operadores/registrar/').status_code, 404)

    def test_cliente_inactivo_no_recibe_permisos(self):
        usuario = get_user_model().objects.create_user(username='inactivo', is_active=False)
        usuario.groups.add(Group.objects.get_or_create(name=CLIENTE)[0])
        self.assertFalse(permisos_panel(usuario)['puede_consultar_maquinaria'])


class ImportacionRolesTests(TestCase):
    def test_importar_conserva_cuentas_sin_recrear_roles_ni_permisos_retirados(self):
        with TemporaryDirectory() as directorio:
            origen = Path(directorio) / 'origen.sqlite3'
            maquinaria = Path(directorio) / 'maquinaria.json'
            maquinaria.write_text(json.dumps([]), encoding='utf-8')
            with closing(sqlite3.connect(origen)) as db:
                db.executescript('''
                    CREATE TABLE auth_user (id integer, username text, password text,
                        last_login text, is_superuser integer, first_name text,
                        last_name text, email text, is_staff integer, is_active integer, date_joined text);
                    INSERT INTO auth_user VALUES (1, 'empleado_importado', '!hash_conservado',
                        NULL, 0, 'Luis', 'Pérez', '', 0, 1, '2026-01-01T00:00:00+00:00');
                    INSERT INTO auth_user VALUES (2, 'tecnico_importado', '!otro_hash',
                        NULL, 0, 'Ana', '', '', 0, 0, '2026-01-01T00:00:00+00:00');
                    CREATE TABLE auth_group (id integer, name text);
                    INSERT INTO auth_group VALUES (1, 'Supervisor'), (2, 'Operador'), (3, 'Técnico');
                    CREATE TABLE auth_user_groups (user_id integer, group_id integer);
                    INSERT INTO auth_user_groups VALUES (1, 1), (1, 2), (2, 3);
                    CREATE TABLE django_content_type (id integer, app_label text, model text);
                    INSERT INTO django_content_type VALUES (1, 'auth', 'user'), (2, 'usuarios', 'operador');
                    CREATE TABLE auth_permission (id integer, codename text, content_type_id integer);
                    INSERT INTO auth_permission VALUES (1, 'add_user', 1), (2, 'view_operador', 2);
                    CREATE TABLE auth_group_permissions (group_id integer, permission_id integer);
                    INSERT INTO auth_group_permissions VALUES (1, 1), (2, 2);
                    CREATE TABLE auth_user_user_permissions (user_id integer, permission_id integer);
                    INSERT INTO auth_user_user_permissions VALUES (1, 2);
                ''')
            ct, _ = apps.get_model('contenttypes', 'ContentType').objects.get_or_create(app_label='usuarios', model='operador')
            Permission.objects.get_or_create(content_type=ct, codename='view_operador', defaults={'name': 'Histórico'})
            comando = ImportarDatos()
            self.assertEqual(comando._migrar_cuentas(origen), (2, 0))
            comando._verificar(origen, maquinaria)
            self.assertEqual(comando._migrar_cuentas(origen), (0, 2))
            empleado = get_user_model().objects.get(username='empleado_importado')
            self.assertEqual(empleado.password, '!hash_conservado')
            self.assertEqual(empleado.get_full_name(), 'Luis Pérez')
            self.assertFalse(empleado.is_staff or empleado.is_superuser)
            self.assertFalse(empleado.groups.exists())
            self.assertFalse(empleado.user_permissions.exists())
            self.assertFalse(Group.objects.filter(name__in=['Supervisor', 'Operador']).exists())
            tecnico = get_user_model().objects.get(username='tecnico_importado')
            self.assertEqual(list(tecnico.groups.values_list('name', flat=True)), [TECNICO])
            self.assertFalse(tecnico.is_active)
            self.assertFalse(Group.objects.get(name=TECNICO).permissions.exists())
