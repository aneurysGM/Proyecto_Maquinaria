from copy import deepcopy
from datetime import date
from decimal import Decimal
from importlib import import_module
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.migrations.state import ProjectState
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from .forms import MantenimientoForm
from .models import Mantenimiento, Maquinaria, Unidad
from .roles import TECNICO, permisos_panel
from .tests import crear_unidad


class MantenimientoTests(TestCase):
    def setUp(self):
        self.tecnico = get_user_model().objects.create_user(
            username='tecnico_hu07', first_name='Ana', last_name='Pérez', password='TecnicoSeguro123!',
        )
        self.tecnico.groups.add(Group.objects.get_or_create(name=TECNICO)[0])
        self.admin = get_user_model().objects.create_superuser(username='admin_hu07', password='AdminSeguro123!')
        self.unidad = crear_unidad()
        self.otra = Unidad.objects.create(maquinaria=self.unidad.maquinaria, numero_serie='MISMO-CATALOGO-OTRA-SERIE')
        self.client.force_login(self.tecnico)
        self.url = reverse('mantenimiento_registrar')
        self.historial = reverse('mantenimiento_historial', args=[self.unidad.pk])
        self.datos = {
            'unidad': self.unidad.pk, 'fecha': '2026-10-27', 'tipo': 'Preventivo',
            'descripcion': '  Cambio de aceite y revisión de filtros.  ', 'costo': '1250.50',
        }

    def assertSinCambios(self):
        self.assertFalse(Mantenimiento.objects.exists())
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.estado, 'Disponible')

    def test_registra_todos_los_datos_y_solo_cambia_la_unidad_elegida(self):
        catalogo_antes = Maquinaria.objects.values().get(pk=self.unidad.maquinaria_id)
        respuesta = self.client.post(self.url, self.datos, follow=True)
        self.assertRedirects(respuesta, self.historial)
        self.assertContains(respuesta, 'El mantenimiento se registró correctamente.')
        registro = Mantenimiento.objects.get()
        self.assertEqual(registro.fecha, date(2026, 10, 27))
        self.assertEqual(registro.tipo, 'Preventivo')
        self.assertEqual(registro.descripcion, self.datos['descripcion'].strip())
        self.assertEqual(registro.costo, Decimal('1250.50'))
        self.assertEqual(registro.tecnico_id, self.tecnico.pk)
        self.assertEqual(registro.unidad_id, self.unidad.pk)
        self.assertIsNone(registro.fecha_fin)
        self.unidad.refresh_from_db()
        self.otra.refresh_from_db()
        self.assertEqual(self.unidad.estado, 'Mantenimiento')
        self.assertEqual(self.otra.estado, 'Disponible')
        self.assertEqual(Maquinaria.objects.values().get(pk=self.unidad.maquinaria_id), catalogo_antes)
        self.assertIsNone(self.unidad.fecha_modificacion)  # La fecha de HU-04 corresponde a edición.
        for texto in ('En mantenimiento', 'Ana Pérez', self.tecnico.username, registro.descripcion, '27/10/2026', '1250,50'):
            self.assertContains(respuesta, texto)
        self.assertContains(self.client.get(reverse('maquinaria_detalle', args=[self.unidad.pk])), 'En mantenimiento')

    def test_costo_cero_es_valido_y_admite_mas_actividades_sin_cerrar(self):
        for tipo in ('Preventivo', 'Correctivo'):
            self.assertEqual(self.client.post(self.url, {**self.datos, 'tipo': tipo, 'costo': '0'}).status_code, 302)
        self.assertEqual(Mantenimiento.objects.count(), 2)
        self.assertTrue(all(m.costo == 0 and m.fecha_fin is None for m in Mantenimiento.objects.all()))

    def test_no_puede_suplantar_tecnico_unidad_estado_o_fecha_fin_por_campos_extra(self):
        self.client.post(self.url, {
            **self.datos, 'tecnico': self.admin.pk, 'tecnico_id': self.admin.pk,
            'TecnicoResponsableID': self.admin.pk, 'unidad_id': self.otra.pk,
            'estado': 'Disponible', 'fecha_fin': '2026-10-28',
        })
        registro = Mantenimiento.objects.get()
        self.assertEqual(registro.tecnico_id, self.tecnico.pk)
        self.assertEqual(registro.unidad_id, self.unidad.pk)
        self.assertIsNone(registro.fecha_fin)
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.estado, 'Mantenimiento')

    def test_obligatorios_y_espacios_se_validan_en_servidor(self):
        for campo in self.datos:
            for valor in ('', '   '):
                with self.subTest(campo=campo, valor=valor):
                    respuesta = self.client.post(self.url, {**self.datos, campo: valor})
                    self.assertEqual(respuesta.status_code, 200)
                    self.assertIn(campo, respuesta.context['form'].errors)
                    self.assertSinCambios()
        respuesta = self.client.post(self.url, {})
        self.assertEqual(set(respuesta.context['form'].errors), set(self.datos))

    def test_fechas_invalidas_costos_no_numericos_negativos_y_fuera_de_precision(self):
        for campo, valores in (
            ('fecha', ('no-fecha', '2026-02-30', '2026-13-01')),
            ('costo', ('texto', '-0.01', 'NaN', 'Infinity', '1.001', '10000000000000000.00')),
            ('tipo', ('Otro',)), ('descripcion', ('a' * 301,)),
            ('unidad', ('999999', 'inexistente')),
        ):
            for valor in valores:
                with self.subTest(campo=campo, valor=valor):
                    respuesta = self.client.post(self.url, {**self.datos, campo: valor})
                    self.assertIn(campo, respuesta.context['form'].errors)
                    self.assertSinCambios()

    def test_formulario_identifica_unidades_y_no_expone_un_campo_para_tecnico(self):
        respuesta = self.client.get(self.url, {'unidad': self.otra.pk})
        self.assertContains(respuesta, self.unidad.numero_serie)
        self.assertContains(respuesta, self.otra.numero_serie)
        self.assertContains(respuesta, f'Unidad #{self.otra.pk}')
        self.assertContains(respuesta, self.unidad.codigo)
        self.assertContains(respuesta, 'type="date"')
        self.assertContains(respuesta, f'value="{self.otra.pk}" selected')
        self.assertContains(respuesta, 'Técnico responsable:')
        self.assertNotContains(respuesta, 'name="tecnico"')
        self.assertSinCambios()

    def test_rechaza_unidades_alquiladas_de_baja_inactivas_o_catalogo_inactivo(self):
        for cambios in ({'estado': 'Alquilado'}, {'estado': 'Baja'}, {'activo': False}):
            Unidad.objects.filter(pk=self.otra.pk).update(**cambios)
            respuesta = self.client.post(self.url, {**self.datos, 'unidad': self.otra.pk})
            self.assertIn('unidad', respuesta.context['form'].errors)
            self.assertSinCambios()
            Unidad.objects.filter(pk=self.otra.pk).update(estado='Disponible', activo=True)
        self.unidad.maquinaria.activo = False
        self.unidad.maquinaria.save()
        respuesta = self.client.post(self.url, self.datos)
        self.assertIn('unidad', respuesta.context['form'].errors)
        self.assertSinCambios()

    def test_cambio_de_estado_entre_validacion_y_guardado_se_revalida(self):
        guardar = MantenimientoForm.save

        def cambia_estado(form, *, tecnico):
            Unidad.objects.filter(pk=self.unidad.pk).update(estado='Alquilado')
            return guardar(form, tecnico=tecnico)

        with patch.object(MantenimientoForm, 'save', cambia_estado):
            respuesta = self.client.post(self.url, self.datos)
        self.assertContains(respuesta, 'La unidad ya no está disponible')
        self.assertFalse(Mantenimiento.objects.exists())
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.estado, 'Alquilado')

    def test_historial_aislado_por_unidad_ordenado_y_con_tecnico_tras_cambio_de_rol(self):
        self.client.post(self.url, self.datos)
        self.client.force_login(self.admin)
        self.client.post(self.url, {**self.datos, 'fecha': '2026-10-28', 'descripcion': 'Actividad más reciente'})
        self.client.post(self.url, {**self.datos, 'unidad': self.otra.pk, 'descripcion': 'ACTIVIDAD DE OTRA UNIDAD'})
        self.tecnico.groups.clear()
        respuesta = self.client.get(self.historial)
        registros = list(respuesta.context['mantenimientos'])
        self.assertEqual([m.fecha for m in registros], [date(2026, 10, 28), date(2026, 10, 27)])
        self.assertContains(respuesta, 'Ana Pérez')
        self.assertNotContains(respuesta, 'ACTIVIDAD DE OTRA UNIDAD')
        self.assertEqual(registros[1].tecnico_id, self.tecnico.pk)

    def test_unidad_eliminada_entre_validacion_y_guardado_no_produce_registro(self):
        guardar = MantenimientoForm.save

        def elimina_unidad(form, *, tecnico):
            Unidad.objects.filter(pk=self.unidad.pk).delete()
            return guardar(form, tecnico=tecnico)

        with patch.object(MantenimientoForm, 'save', elimina_unidad):
            respuesta = self.client.post(self.url, self.datos)
        self.assertContains(respuesta, 'La unidad ya no está disponible')
        self.assertFalse(Mantenimiento.objects.exists())

    def test_historial_vacio_y_legacy_y_unidades_inactivas(self):
        self.assertContains(self.client.get(self.historial), 'Sin mantenimientos registrados')
        Mantenimiento.objects.create(unidad=self.unidad, fecha='2020-01-01', tipo='Correctivo', costo=0)
        self.unidad.activo = False
        self.unidad.save()
        self.assertContains(self.client.get(self.historial), 'No registrado (registro anterior)')
        self.assertContains(self.client.get(self.historial), 'No especificada (registro anterior)')
        respuesta = self.client.get(reverse('mantenimiento_lista'), {'q': self.unidad.numero_serie})
        self.assertContains(respuesta, self.historial)
        self.assertContains(respuesta, 'Inactiva')
        self.assertNotContains(respuesta, self.otra.numero_serie)
        self.assertEqual(self.client.get(reverse('mantenimiento_historial', args=[999999])).status_code, 404)

    def test_fallo_real_de_sql_al_actualizar_unidad_revierte_tambien_el_registro(self):
        guardar = Unidad.save

        def falla_estado(unidad, *args, **kwargs):
            unidad.estado = 'Estado inválido'
            return guardar(unidad, *args, **kwargs)  # CHECK de SQL Server produce IntegrityError.

        with patch.object(Unidad, 'save', falla_estado):
            respuesta = self.client.post(self.url, self.datos)
        self.assertContains(respuesta, 'No se pudo registrar el mantenimiento.')
        self.assertSinCambios()

    def test_fallo_despues_de_guardar_ambas_operaciones_revierte_todo(self):
        guardar = Unidad.save

        def guardar_y_fallar(unidad, *args, **kwargs):
            guardar(unidad, *args, **kwargs)
            raise OperationalError('Fallo simulado después del segundo guardado')

        with patch.object(Unidad, 'save', guardar_y_fallar):
            respuesta = self.client.post(self.url, self.datos)
        self.assertContains(respuesta, 'No se guardaron cambios.')
        self.assertSinCambios()

    def test_fallo_en_primer_guardado_no_modifica_estado(self):
        with patch.object(Mantenimiento, 'save', side_effect=IntegrityError('Fallo simulado')):
            respuesta = self.client.post(self.url, self.datos)
        self.assertContains(respuesta, 'No se guardaron cambios.')
        self.assertSinCambios()

    def test_relaciones_protegidas_y_restricciones_directas_de_base(self):
        self.client.post(self.url, self.datos)
        for objeto in (self.tecnico, self.unidad):
            with self.assertRaises(ProtectedError):
                objeto.delete()
        for cambios in ({'costo': '-1'}, {'tipo': 'Otro'}, {'unidad_id': 999999}, {'tecnico_id': 999999}):
            with self.subTest(cambios=cambios):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Mantenimiento.objects.create(
                        **{'unidad_id': self.unidad.pk, 'tecnico_id': self.tecnico.pk, 'fecha': '2026-10-27',
                           'tipo': 'Preventivo', 'costo': 0, 'descripcion': 'Prueba', **cambios}
                    )
        registro = Mantenimiento(unidad=self.unidad, fecha='2026-10-27', tipo='Preventivo', costo=0)
        with self.assertRaises(ValidationError) as error:
            registro.full_clean()
        self.assertIn('tecnico', error.exception.message_dict)
        self.assertIn('descripcion', error.exception.message_dict)

    def test_tecnico_conserva_accesos_de_consulta_y_no_adquiere_hu04_hu05(self):
        for nombre in ('maquinaria_lista', 'dashboard', 'mantenimiento_lista'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)
        self.assertContains(self.client.get(reverse('dashboard')), 'Panel de Técnico')
        for url in (
            reverse('maquinaria_registrar'), reverse('maquinaria_editar', args=[self.unidad.pk]),
            reverse('operador_registrar'), reverse('operador_lista'), reverse('operador_detalle', args=[999999]),
        ):
            for metodo in (self.client.get, self.client.post):
                self.assertEqual(metodo(url, self.datos).status_code, 403)
        panel = self.client.get(reverse('dashboard'))
        self.assertContains(panel, self.url)
        self.assertNotContains(panel, reverse('operador_lista'))
        self.assertNotContains(panel, reverse('maquinaria_registrar'))
        self.assertRedirects(self.client.get(reverse('admin:index')), '/admin/login/?next=/admin/')

    def test_roles_no_autorizados_reciben_403_en_get_y_post_directos(self):
        supervisor = get_user_model().objects.create_user(username='supervisor_hu07')
        supervisor.groups.add(Group.objects.get_or_create(name='Supervisor')[0])
        sin_rol = get_user_model().objects.create_user(username='sinrol_hu07')
        staff = get_user_model().objects.create_user(username='staff_hu07', is_staff=True)
        for usuario in (supervisor, sin_rol, staff):
            self.client.force_login(usuario)
            for url in (self.url, self.historial, reverse('mantenimiento_lista'), reverse('mantenimiento_historial', args=[999999])):
                for metodo in (self.client.get, self.client.post):
                    with self.subTest(usuario=usuario.username, url=url, metodo=metodo.__name__):
                        self.assertEqual(metodo(url, self.datos).status_code, 403)
            self.assertNotContains(self.client.get(reverse('dashboard')), self.url)
            self.assertNotContains(self.client.get(reverse('dashboard')), reverse('mantenimiento_lista'))
        self.assertSinCambios()

    def test_admin_puede_registrar_y_consultar(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.post(self.url, self.datos), self.historial)
        self.assertEqual(Mantenimiento.objects.get().tecnico_id, self.admin.pk)
        self.assertContains(self.client.get(reverse('dashboard')), self.url)

    def test_sin_sesion_o_cuenta_inactiva_no_registra_ni_consulta(self):
        self.client.logout()
        for url in (self.url, self.historial, reverse('mantenimiento_lista')):
            for metodo in (self.client.get, self.client.post):
                self.assertRedirects(metodo(url, self.datos if metodo == self.client.post else {}), f'{reverse("login")}?next={url}')
        self.tecnico.is_active = False
        self.tecnico.save()
        self.client.force_login(self.tecnico)
        self.assertRedirects(self.client.post(self.url, self.datos), f'{reverse("login")}?next={self.url}')
        self.assertFalse(permisos_panel(self.tecnico)['puede_registrar_mantenimiento'])
        self.assertSinCambios()

    def test_login_logout_tecnico_y_rechazo_de_clave_incorrecta(self):
        self.client.logout()
        self.assertContains(self.client.post(reverse('login'), {'username': self.tecnico.username, 'password': 'incorrecta'}), 'Usuario o contraseña incorrectos.')
        respuesta = self.client.post(reverse('login'), {'username': self.tecnico.username, 'password': 'TecnicoSeguro123!'}, follow=True)
        self.assertRedirects(respuesta, reverse('dashboard'))
        self.assertContains(respuesta, 'Panel de Técnico')
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))

    def test_post_sin_csrf_no_escribe(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.tecnico)
        self.assertEqual(cliente.post(self.url, self.datos).status_code, 403)
        self.assertSinCambios()


class TecnicoComandoTests(TestCase):
    def test_crea_cuenta_y_repetir_conserva_clave_grupos_y_actividad(self):
        call_command('crear_tecnico', 'nuevo_tecnico', nombre='Luis', stdout=StringIO())
        usuario = get_user_model().objects.get(username='nuevo_tecnico')
        self.assertFalse(usuario.has_usable_password())
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertTrue(usuario.groups.filter(name=TECNICO).exists())
        self.assertEqual(usuario.first_name, 'Luis')
        usuario.set_password('ClaveExistente123!')
        usuario.is_active = False
        usuario.save()
        usuario.groups.add(Group.objects.get_or_create(name='Supervisor')[0])
        call_command('crear_tecnico', usuario.username, stdout=StringIO())
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password('ClaveExistente123!'))
        self.assertFalse(usuario.is_active)
        self.assertEqual(set(usuario.groups.values_list('name', flat=True)), {TECNICO, 'Supervisor'})

    def test_no_modifica_cuentas_administrativas(self):
        for cambios in ({'is_superuser': True}, {'is_staff': True}):
            usuario = get_user_model().objects.create_user(username='privilegiado' + str(cambios), **cambios)
            with self.assertRaises(CommandError):
                call_command('crear_tecnico', usuario.username, stdout=StringIO())
            self.assertFalse(usuario.groups.filter(name=TECNICO).exists())


class MantenimientoMigracionTests(TransactionTestCase):
    def setUp(self):
        self.migracion = import_module('usuarios.migrations.0007_integrar_mantenimiento')
        self.estado = ProjectState.from_apps(apps)
        opciones = self.estado.models['usuarios', 'mantenimiento'].options
        opciones['db_table'] = 'MantenimientoPruebaHU07'
        opciones['constraints'] = [deepcopy(c) for c in opciones['constraints']]
        for restriccion in opciones['constraints']:
            restriccion.name += '_Prueba'
        self.modelo = self.estado.apps.get_model('usuarios', 'Mantenimiento')
        self.unidad = crear_unidad()

    def tearDown(self):
        if self.modelo._meta.db_table in connection.introspection.table_names():
            with connection.schema_editor() as editor:
                editor.delete_model(self.modelo)
        super().tearDown()

    def crear_legacy(self, con_relacion=False):
        estado = self.estado.clone()
        estado.remove_field('usuarios', 'mantenimiento', 'tecnico')
        estado.models['usuarios', 'mantenimiento'].options['constraints'] = []
        campo = deepcopy(estado.models['usuarios', 'mantenimiento'].fields['unidad'])
        campo.db_constraint = con_relacion  # La tabla real revisada no tiene FK de unidad.
        estado.alter_field('usuarios', 'mantenimiento', 'unidad', campo, preserve_default=True)
        modelo = estado.apps.get_model('usuarios', 'Mantenimiento')
        with connection.schema_editor() as editor:
            editor.create_model(modelo)
        return modelo

    def adoptar(self):
        with connection.schema_editor() as editor:
            self.migracion.integrar_mantenimiento(self.estado.apps, editor)

    def test_crea_tabla_si_no_existe(self):
        self.adoptar()
        usuario = get_user_model().objects.create_user(username='tecnico_migracion')
        registro = self.modelo.objects.create(unidad_id=self.unidad.pk, tecnico_id=usuario.pk, fecha='2026-10-27', tipo='Preventivo', costo=0, descripcion='Prueba')
        self.assertEqual(self.modelo.objects.get().pk, registro.pk)

    def test_adopta_legacy_conservando_todos_los_valores_y_agrega_relaciones(self):
        legacy = self.crear_legacy()
        legacy.objects.create(unidad_id=self.unidad.pk, fecha='2020-01-01', fecha_fin='2020-01-02', tipo='Correctivo', costo='25.50')
        antes = list(legacy.objects.values())
        self.adoptar()
        self.assertEqual(list(legacy.objects.values()), antes)
        self.assertIsNone(self.modelo.objects.get().tecnico_id)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.modelo.objects.create(unidad_id=999999, fecha='2026-10-27', tipo='Preventivo', costo=0)

    def test_datos_invalidos_detienen_adopcion_sin_perder_filas_o_agregar_columnas(self):
        legacy = self.crear_legacy()
        for cambios in ({'costo': '-1'}, {'tipo': 'Otro'}, {'unidad_id': 999999}):
            with self.subTest(cambios=cambios):
                legacy.objects.all().delete()
                legacy.objects.create(**{'unidad_id': self.unidad.pk, 'fecha': '2020-01-01', 'tipo': 'Preventivo', 'costo': 0, **cambios})
                antes = list(legacy.objects.values())
                with self.assertRaisesMessage(RuntimeError, 'sin borrar datos'):
                    self.adoptar()
                self.assertEqual(list(legacy.objects.values()), antes)
                with connection.cursor() as cursor:
                    columnas = connection.introspection.get_table_description(cursor, legacy._meta.db_table)
                self.assertNotIn('TecnicoResponsableID', [c.name for c in columnas])

    def test_adopta_legacy_con_fk_existente_sin_duplicar_la_relacion(self):
        legacy = self.crear_legacy(con_relacion=True)
        legacy.objects.create(unidad_id=self.unidad.pk, fecha='2020-01-01', tipo='Preventivo', costo=0)
        self.adoptar()
        with connection.cursor() as cursor:
            restricciones = connection.introspection.get_constraints(cursor, self.modelo._meta.db_table)
        relaciones = [c for c in restricciones.values() if c['columns'] == ['UnidadID'] and c['foreign_key']]
        self.assertEqual(len(relaciones), 1)

    def test_esquema_incompatible_no_se_reemplaza(self):
        legacy = self.crear_legacy()
        legacy.objects.create(unidad_id=self.unidad.pk, fecha='2020-01-01', tipo='Preventivo', costo=0)
        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE [MantenimientoPruebaHU07] DROP COLUMN [Descripcion]')
        with self.assertRaisesMessage(RuntimeError, 'faltan columnas legacy'):
            self.adoptar()
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM [MantenimientoPruebaHU07]')
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_grupo_tecnico_se_crea_de_forma_idempotente(self):
        with connection.schema_editor() as editor:
            self.migracion.crear_grupo_tecnico(self.estado.apps, editor)
            self.migracion.crear_grupo_tecnico(self.estado.apps, editor)
        self.assertEqual(Group.objects.filter(name=TECNICO).count(), 1)
