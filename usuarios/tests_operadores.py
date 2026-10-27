from datetime import date
from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, connection, transaction
from django.db.migrations.state import ProjectState
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .forms import OperadorForm
from .models import Operador


class OperadorTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username='admin_operadores')
        self.client.force_login(self.admin)
        self.url = reverse('operador_registrar')
        self.datos = {
            'nombre_completo': '  Ana   María Pérez  ', 'cedula': '001-1234567-8',
            'telefono': '809-555-0100', 'direccion': ' Calle de prueba 10 ',
            'tipo_licencia': 'Cat. 3', 'fecha_vencimiento': '2028-06-30',
        }

    def test_register_persists_all_fields_and_confirms_without_login_account(self):
        cuentas = get_user_model().objects.count()
        respuesta = self.client.post(self.url, self.datos, follow=True)
        operador = Operador.objects.get()
        operador.refresh_from_db()
        self.assertRedirects(respuesta, reverse('operador_detalle', args=[operador.pk]))
        self.assertContains(respuesta, 'El operador se registró correctamente.')
        self.assertEqual(operador.nombre_completo, 'Ana María Pérez')
        self.assertEqual(operador.cedula, '00112345678')
        self.assertEqual(operador.cedula_normalizada, '00112345678')
        self.assertEqual(operador.telefono, '809-555-0100')
        self.assertEqual(operador.direccion, 'Calle de prueba 10')
        self.assertEqual(operador.tipo_licencia, 'Cat. 3')
        self.assertEqual(operador.fecha_vencimiento, date(2028, 6, 30))
        self.assertTrue(operador.activo)
        self.assertIsNotNone(operador.fecha_creacion)
        self.assertEqual(get_user_model().objects.count(), cuentas)
        detalle = self.client.get(reverse('operador_detalle', args=[operador.pk]))
        for valor in ('Ana María Pérez', '00112345678', '809-555-0100', 'Calle de prueba 10', 'Cat. 3', '30/06/2028', 'Activo'):
            self.assertContains(detalle, valor)
        self.assertContains(self.client.get(reverse('operador_lista')), 'Ana María Pérez')

    def test_duplicate_identifiers_are_rejected_including_inactive_legacy(self):
        Operador.objects.create(nombre='Ana', apellido='Pérez', cedula='001-1234567-8', estado='Inactivo')
        for cedula in ('00112345678', '001-1234567-8', ' 001 1234567 8 ', '001\t1234567\u00a08'):
            with self.subTest(cedula=cedula):
                respuesta = self.client.post(self.url, {**self.datos, 'cedula': cedula})
                self.assertIn('cedula', respuesta.context['form'].errors)
                self.assertEqual(Operador.objects.count(), 1)

    def test_sql_server_rejects_formatted_duplicates_without_form(self):
        Operador.objects.create(nombre='Primero', cedula='00112345678')
        for cedula in ('001-1234567-8', '001 1234567 8', '001\t1234567\u00a08'):
            with self.subTest(cedula=cedula):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Operador.objects.create(nombre='Duplicado', cedula=cedula)
        self.assertEqual(Operador.objects.count(), 1)

    def test_all_fields_are_required_and_whitespace_is_rejected(self):
        for campo in self.datos:
            for valor in ('', '   '):
                with self.subTest(campo=campo, valor=valor):
                    respuesta = self.client.post(self.url, {**self.datos, campo: valor})
                    self.assertIn(campo, respuesta.context['form'].errors)
                    self.assertFalse(Operador.objects.exists())

    def test_invalid_dates_identifiers_and_lengths_do_not_save(self):
        for campo, valor in (
            ('fecha_vencimiento', '2028-02-30'), ('fecha_vencimiento', 'no es fecha'),
            ('cedula', '---'), ('cedula', 'ABC123'), ('cedula', '1' * 21),
            ('telefono', '1' * 21), ('direccion', 'a' * 201),
            ('tipo_licencia', 'a' * 11), ('nombre_completo', 'a' * 162),
        ):
            with self.subTest(campo=campo):
                respuesta = self.client.post(self.url, {**self.datos, campo: valor})
                self.assertIn(campo, respuesta.context['form'].errors)
                self.assertFalse(Operador.objects.exists())

    def test_long_full_name_round_trips_without_truncation(self):
        nombre = ' '.join(['Nombre'] * 20)
        self.client.post(self.url, {**self.datos, 'nombre_completo': nombre})
        self.assertEqual(Operador.objects.get().nombre_completo, nombre)

    def test_post_cannot_override_state_or_create_account(self):
        self.client.post(self.url, {**self.datos, 'estado': 'Inactivo', 'is_superuser': '1', 'username': 'intruso'})
        self.assertTrue(Operador.objects.get().activo)
        self.assertFalse(get_user_model().objects.filter(username='intruso').exists())

    def test_administrator_navigation_and_empty_list(self):
        self.assertContains(self.client.get(reverse('dashboard')), self.url)
        self.assertContains(self.client.get(reverse('operador_lista')), 'No hay operadores registrados')
        self.assertContains(self.client.get(self.url), 'type="date"')
        self.assertEqual(self.client.get(reverse('operador_detalle', args=[999999])).status_code, 404)

    def test_registration_and_consultation_require_admin_on_server(self):
        operador = Operador.objects.create(nombre='Solo admin', cedula='00112345678')
        grupo = Group.objects.create(name='Supervisor')
        supervisor = get_user_model().objects.create_user(username='supervisor_operadores')
        supervisor.groups.add(grupo)
        sin_rol = get_user_model().objects.create_user(username='sin_rol_operadores')
        staff = get_user_model().objects.create_user(username='staff_operadores', is_staff=True)
        urls = (self.url, reverse('operador_lista'), reverse('operador_detalle', args=[operador.pk]))
        for usuario in (supervisor, sin_rol, staff):
            self.client.force_login(usuario)
            for url in urls:
                for metodo in (self.client.get, self.client.post):
                    with self.subTest(usuario=usuario.username, url=url, metodo=metodo.__name__):
                        self.assertEqual(metodo(url, self.datos).status_code, 403)
            self.assertNotContains(self.client.get(reverse('dashboard')), self.url)
            self.assertNotContains(self.client.get(reverse('dashboard')), reverse('operador_lista'))
        self.assertEqual(Operador.objects.count(), 1)

    def test_anonymous_requests_redirect_to_login(self):
        self.client.logout()
        for url in (self.url, reverse('operador_lista'), reverse('operador_detalle', args=[999999])):
            for metodo in (self.client.get, self.client.post):
                respuesta = metodo(url, self.datos if metodo == self.client.post else {})
                self.assertRedirects(respuesta, f'{reverse("login")}?next={url}')
        self.assertFalse(Operador.objects.exists())

    def test_database_race_displays_error_without_partial_record(self):
        with patch.object(OperadorForm, 'save', side_effect=IntegrityError('Conflicto simulado')):
            respuesta = self.client.post(self.url, self.datos)
        self.assertContains(respuesta, 'No se pudo registrar el operador.')
        self.assertContains(respuesta, 'Ana   María Pérez')
        self.assertFalse(Operador.objects.exists())


class OperadorMigracionTests(TransactionTestCase):
    """Ejecuta las dos rutas DDL sobre tablas aisladas en la base de pruebas."""

    def setUp(self):
        self.migracion = import_module('usuarios.migrations.0006_integrar_operador')
        self.estado = ProjectState.from_apps(apps)
        self.estado.models['usuarios', 'operador'].options['db_table'] = 'OperadorPruebaHU05'
        self.modelo = self.estado.apps.get_model('usuarios', 'Operador')

    def tearDown(self):
        if self.modelo._meta.db_table in connection.introspection.table_names():
            with connection.schema_editor() as editor:
                editor.delete_model(self.modelo)
        super().tearDown()

    def crear_legacy(self):
        estado = self.estado.clone()
        estado.remove_field('usuarios', 'operador', 'cedula_normalizada')
        modelo = estado.apps.get_model('usuarios', 'Operador')
        with connection.schema_editor() as editor:
            editor.create_model(modelo)
        return modelo

    def test_creates_table_when_missing(self):
        with connection.schema_editor() as editor:
            self.migracion.integrar_operador(self.estado.apps, editor)
        operador = self.modelo.objects.create(nombre='Nuevo', cedula='001-1234567-8')
        operador.refresh_from_db()
        self.assertEqual(operador.cedula_normalizada, '00112345678')

    def test_adopts_legacy_preserving_every_original_field(self):
        legacy = self.crear_legacy()
        legacy.objects.create(
            nombre='Nombre anterior', apellido='Apellido anterior', cedula='001-1234567-8',
            estado='Inactivo', email='prueba@example.invalid', numero_licencia='LEGACY',
        )
        antes = list(legacy.objects.values())
        with connection.schema_editor() as editor:
            self.migracion.integrar_operador(self.estado.apps, editor)
        self.assertEqual(list(legacy.objects.values()), antes)
        operador = self.modelo.objects.get()
        self.assertEqual(operador.cedula_normalizada, '00112345678')
        self.assertEqual(operador.estado, 'Inactivo')

    def test_legacy_normalized_duplicates_stop_without_deleting_rows(self):
        legacy = self.crear_legacy()
        legacy.objects.create(nombre='Primero', cedula='00112345678')
        legacy.objects.create(nombre='Segundo', cedula='001-1234567-8')
        antes = list(legacy.objects.values())
        with self.assertRaisesMessage(RuntimeError, 'duplicadas tras normalizar'):
            with connection.schema_editor() as editor:
                self.migracion.integrar_operador(self.estado.apps, editor)
        self.assertEqual(list(legacy.objects.values()), antes)
