from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Categoria, Maquinaria, Unidad
from .validators import anio_actual


def crear_unidad(codigo='RET-001', serie='SERIE-001', estado='Disponible'):
    categoria, _ = Categoria.objects.get_or_create(nombre='Construcción')
    maquinaria = Maquinaria.objects.create(
        categoria=categoria,
        codigo=codigo,
        nombre='Retroexcavadora',
        marca='Marca',
        modelo='Modelo X',
        costo_adquisicion='125000.00',
        tarifa_diaria='150.00',
        tarifa_semanal='900.00',
        tarifa_mensual='3000.00',
        deposito_garantia='500.00',
    )
    return Unidad.objects.create(
        maquinaria=maquinaria,
        numero_serie=serie,
        estado=estado,
        horas_uso='12.5',
    )


class MaquinariaViewsTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_superuser(
            username='prueba', password='ClaveSegura123!'
        )
        self.client.force_login(usuario)
        self.datos = {
            'codigo': 'RET-001', 'nombre': 'Retroexcavadora',
            'categoria': 'Construcción', 'marca': 'Marca', 'modelo': 'Modelo X',
            'costo_adquisicion': '125000.00', 'tarifa_diaria': '150.00',
            'tarifa_semanal': '900.00', 'tarifa_mensual': '3000.00',
            'deposito_garantia': '500.00', 'numero_serie': 'SERIE-001',
            'estado': 'Disponible', 'horas_uso': '12.5',
            'fecha_adquisicion': '',
            'anio_fabricacion': str(anio_actual()),
            'ubicacion_actual': '  Almacén central  ',
        }

    def test_maquinaria_pages_require_login(self):
        self.client.logout()
        respuesta = self.client.get(reverse('maquinaria_lista'))
        self.assertRedirects(
            respuesta,
            f"{reverse('login')}?next={reverse('maquinaria_lista')}",
        )

    def test_admin_can_register_filter_and_open_details(self):
        respuesta = self.client.post(reverse('maquinaria_registrar'), self.datos)
        self.assertEqual(respuesta.status_code, 302)
        unidad = Unidad.objects.select_related('maquinaria').get()
        unidad.refresh_from_db()
        self.assertEqual(unidad.anio_fabricacion, anio_actual())
        self.assertEqual(unidad.ubicacion_actual, 'Almacén central')
        self.assertRedirects(
            respuesta,
            reverse('maquinaria_detalle', kwargs={'maquinaria_id': unidad.id}),
        )
        for filtros in ({'q': 'retro'}, {'q': 'SERIE-001'}, {'estado': 'Disponible'}):
            with self.subTest(filtros=filtros):
                self.assertContains(
                    self.client.get(reverse('maquinaria_lista'), filtros),
                    'Retroexcavadora',
                )
        self.assertNotContains(
            self.client.get(reverse('maquinaria_lista'), {'estado': 'Mantenimiento'}),
            'SERIE-001',
        )
        detalle = self.client.get(reverse('maquinaria_detalle', args=[unidad.id]))
        self.assertContains(detalle, 'SERIE-001')
        self.assertContains(detalle, str(anio_actual()))
        self.assertContains(detalle, 'Año de fabricación')
        self.assertContains(detalle, 'Almacén central')
        self.assertContains(self.client.get(reverse('maquinaria_lista')), 'Almacén central')
        self.assertContains(detalle, 'Construcción')

    def test_invalid_input_displays_field_validation(self):
        datos_invalidos = {**self.datos, 'tarifa_diaria': '0', 'numero_serie': ''}
        respuesta = self.client.post(reverse('maquinaria_registrar'), datos_invalidos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '0.01')
        self.assertContains(respuesta, 'obligatorio')
        self.assertFalse(Unidad.objects.exists())

    def test_duplicate_code_and_serial_are_rejected(self):
        self.client.post(reverse('maquinaria_registrar'), self.datos)
        respuesta_codigo = self.client.post(
            reverse('maquinaria_registrar'),
            {**self.datos, 'numero_serie': 'SERIE-002'},
        )
        self.assertContains(
            respuesta_codigo, 'Ya existe una maquinaria con este código.'
        )
        respuesta_serie = self.client.post(
            reverse('maquinaria_registrar'),
            {**self.datos, 'codigo': 'RET-002'},
        )
        self.assertContains(
            respuesta_serie, 'Ya existe una maquinaria con este número de serie.'
        )
        self.assertEqual(Unidad.objects.count(), 1)

    def test_missing_detail_returns_not_found(self):
        self.assertEqual(
            self.client.get(reverse('maquinaria_detalle', args=[999999])).status_code,
            404,
        )

    def test_registration_form_includes_new_fields(self):
        respuesta = self.client.get(reverse('maquinaria_registrar'))
        self.assertContains(respuesta, 'name="anio_fabricacion"')
        self.assertContains(respuesta, f'max="{anio_actual()}"')
        self.assertContains(respuesta, 'name="ubicacion_actual"')

    def test_invalid_year_or_missing_location_does_not_create_records(self):
        for cambios, campo in (
            ({'anio_fabricacion': str(anio_actual() + 1)}, 'anio_fabricacion'),
            ({'anio_fabricacion': '0'}, 'anio_fabricacion'),
            ({'anio_fabricacion': '2020.5'}, 'anio_fabricacion'),
            ({'anio_fabricacion': ''}, 'anio_fabricacion'),
            ({'ubicacion_actual': ''}, 'ubicacion_actual'),
            ({'ubicacion_actual': '   '}, 'ubicacion_actual'),
            ({'ubicacion_actual': 'x' * 201}, 'ubicacion_actual'),
        ):
            with self.subTest(cambios=cambios):
                respuesta = self.client.post(
                    reverse('maquinaria_registrar'), {**self.datos, **cambios}
                )
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(campo, respuesta.context['form'].errors)
                self.assertFalse(Unidad.objects.exists())
                self.assertFalse(Maquinaria.objects.exists())
                self.assertFalse(Categoria.objects.exists())

    def test_legacy_unknown_values_are_displayed_without_fabricating_data(self):
        unidad = crear_unidad()
        unidad.refresh_from_db()
        self.assertIsNone(unidad.anio_fabricacion)
        self.assertIsNone(unidad.ubicacion_actual)
        detalle = self.client.get(reverse('maquinaria_detalle', args=[unidad.id]))
        self.assertContains(detalle, 'No especificado')
        self.assertContains(detalle, 'No especificada')
        self.assertContains(self.client.get(reverse('maquinaria_lista')), 'No especificada')
        unidad.full_clean()  # Las unidades existentes pueden conservar su ubicación nula.

    def test_model_validation_rejects_future_year_and_new_empty_location(self):
        unidad = crear_unidad()
        unidad.anio_fabricacion = anio_actual() + 1
        with self.assertRaises(ValidationError) as error:
            unidad.full_clean()
        self.assertIn('anio_fabricacion', error.exception.message_dict)
        nueva = Unidad(maquinaria=unidad.maquinaria, numero_serie='NUEVA')
        with self.assertRaises(ValidationError) as error:
            nueva.full_clean()
        self.assertIn('ubicacion_actual', error.exception.message_dict)


class ClienteTests(TestCase):
    def setUp(self):
        self.cliente_usuario = get_user_model().objects.create_user(
            username='cliente_usuario', first_name='Ana', last_name='Pérez',
            password='ClaveCliente123!',
        )
        self.cliente_usuario.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.admin = get_user_model().objects.create_superuser(
            username='admin', password='ClaveAdmin123!'
        )

    def test_shared_login_displays_independent_roles(self):
        for usuario, clave, nombre, rol in (
            (self.cliente_usuario, 'ClaveCliente123!', 'Ana Pérez', 'Cliente'),
            (self.admin, 'ClaveAdmin123!', 'admin', 'Administrador'),
        ):
            with self.subTest(rol=rol):
                respuesta = self.client.post(
                    reverse('login'),
                    {'username': usuario.username, 'password': clave},
                    follow=True,
                )
                self.assertRedirects(respuesta, reverse('dashboard'))
                self.assertContains(respuesta, nombre)
                self.assertContains(respuesta, f'Panel de {rol}')
                if rol == 'Cliente':
                    self.assertNotContains(respuesta, reverse('maquinaria_registrar'))
                else:
                    self.assertContains(respuesta, reverse('maquinaria_registrar'))
                self.client.post(reverse('logout'))

    def test_cliente_usuario_can_consult_but_cannot_register_by_direct_url(self):
        unidad = crear_unidad()
        unidad.anio_fabricacion = 2020
        unidad.ubicacion_actual = 'Patio norte'
        unidad.save()
        self.client.force_login(self.cliente_usuario)
        lista = self.client.get(reverse('maquinaria_lista'))
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, 'Patio norte')
        detalle = self.client.get(reverse('maquinaria_detalle', args=[unidad.id]))
        self.assertContains(detalle, 'Patio norte')
        self.assertContains(detalle, '2020')
        self.assertNotContains(lista, reverse('maquinaria_registrar'))
        self.assertEqual(
            self.client.get(reverse('maquinaria_detalle', args=[unidad.id])).status_code,
            200,
        )
        for metodo in (self.client.get, self.client.post):
            with self.subTest(metodo=metodo.__name__):
                self.assertEqual(
                    metodo(reverse('maquinaria_registrar'), self._datos_post()).status_code,
                    403,
                )
        self.assertEqual(Unidad.objects.count(), 1)
        self.assertRedirects(
            self.client.get(reverse('admin:index')), '/admin/login/?next=/admin/'
        )

    def test_unassigned_user_has_no_maquinaria_access(self):
        usuario = get_user_model().objects.create_user(username='sinrol')
        self.client.force_login(usuario)
        self.assertContains(self.client.get(reverse('dashboard')), 'Sin rol asignado')
        for url in (
            reverse('maquinaria_lista'), reverse('maquinaria_registrar'),
            reverse('maquinaria_detalle', args=[999999]),
        ):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_custom_permission_denied_page_with_debug_enabled_and_disabled(self):
        sin_rol = get_user_model().objects.create_user(username='sinrol403')
        for debug in (True, False):
            with self.settings(DEBUG=debug):
                for usuario, urls in (
                    (self.cliente_usuario, (reverse('maquinaria_registrar'),)),
                    (sin_rol, (
                        reverse('maquinaria_lista'),
                        reverse('maquinaria_registrar'),
                        reverse('maquinaria_detalle', args=[999999]),
                    )),
                ):
                    self.client.force_login(usuario)
                    for url in urls:
                        for metodo in (self.client.get, self.client.post):
                            with self.subTest(
                                debug=debug, usuario=usuario.username,
                                url=url, metodo=metodo.__name__,
                            ):
                                respuesta = metodo(url, self._datos_post())
                                self.assertTemplateUsed(respuesta, 'usuarios/acceso_denegado.html')
                                self.assertContains(
                                    respuesta, 'data-page="acceso-denegado"', status_code=403,
                                )
                                self.assertContains(respuesta, 'Acceso denegado', status_code=403)
                                self.assertContains(
                                    respuesta, 'No tienes permisos para acceder a esta página.',
                                    status_code=403,
                                )
                                self.assertContains(
                                    respuesta,
                                    f'<a class="button" href="{reverse("dashboard")}">Volver al panel</a>',
                                    status_code=403, html=True,
                                )
                                self.assertNotContains(respuesta, 'Guardar maquinaria', status_code=403)
                                self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        self.assertFalse(Unidad.objects.exists())
        self.assertFalse(Maquinaria.objects.exists())

    def test_command_creates_account_and_preserves_password_on_rerun(self):
        call_command('crear_cliente', 'nuevo', nombre='Luis', stdout=StringIO())
        usuario = get_user_model().objects.get(username='nuevo')
        self.assertFalse(usuario.has_usable_password())
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertTrue(usuario.groups.filter(name='Cliente').exists())
        usuario.set_password('NuevaClaveSegura123!')
        usuario.save()
        call_command('crear_cliente', 'nuevo', stdout=StringIO())
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password('NuevaClaveSegura123!'))

    def test_command_never_changes_admin(self):
        with self.assertRaises(CommandError):
            call_command('crear_cliente', 'admin', stdout=StringIO())
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(self.admin.is_superuser)
        self.assertFalse(self.admin.groups.filter(name='Cliente').exists())

    @staticmethod
    def _datos_post():
        return {
            'codigo': 'PROHIBIDO', 'nombre': 'No debe guardarse',
            'categoria': 'Prueba', 'costo_adquisicion': '1',
            'tarifa_diaria': '1', 'tarifa_semanal': '1',
            'tarifa_mensual': '1', 'deposito_garantia': '0',
            'numero_serie': 'PROHIBIDO', 'estado': 'Disponible',
            'horas_uso': '0',
            'anio_fabricacion': '2020', 'ubicacion_actual': 'Patio norte',
        }

class MaquinariaEdicionTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='editor', password='ClaveEdicion123!',
        )
        self.client.force_login(self.admin)
        self.unidad = crear_unidad()
        self.unidad.anio_fabricacion = 2020
        self.unidad.ubicacion_actual = 'Patio norte'
        self.unidad.save()
        self.url = reverse('maquinaria_editar', args=[self.unidad.pk])
        self.datos = {
            'codigo': 'RET-001', 'nombre': 'Retroexcavadora',
            'categoria': 'Construcción', 'marca': 'Marca', 'modelo': 'Modelo X',
            'costo_adquisicion': '125000.00', 'tarifa_diaria': '150.00',
            'tarifa_semanal': '900.00', 'tarifa_mensual': '3000.00',
            'deposito_garantia': '500.00', 'numero_serie': 'SERIE-001',
            'estado': 'Disponible', 'horas_uso': '12.5',
            'fecha_adquisicion': '', 'anio_fabricacion': '2020',
            'ubicacion_actual': 'Patio norte',
        }

    def test_form_shows_current_values_and_edit_actions(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Editar maquinaria')
        self.assertEqual(respuesta.context['form'].initial['numero_serie'], 'SERIE-001')
        self.assertEqual(respuesta.context['form'].initial['categoria'], 'Construcción')
        self.assertContains(
            self.client.get(reverse('maquinaria_lista')), self.url,
        )
        self.assertContains(
            self.client.get(reverse('maquinaria_detalle', args=[self.unidad.pk])),
            self.url,
        )
        self.unidad.refresh_from_db()
        self.assertIsNone(self.unidad.fecha_modificacion)

    def test_date_input_uses_iso_format_for_existing_acquisition(self):
        from datetime import date
        self.unidad.fecha_adquisicion = date(2025, 1, 15)
        self.unidad.save()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="2025-01-15"')

    def test_edit_updates_existing_rows_and_records_dates(self):
        from django.utils import timezone
        inicio = timezone.now()
        respuesta = self.client.post(self.url, {
            **self.datos, 'nombre': 'Retroexcavadora actualizada',
            'codigo': 'RET-NUEVO', 'numero_serie': 'SERIE-NUEVA',
            'categoria': 'Excavación', 'ubicacion_actual': '  Patio sur  ',
            'tarifa_diaria': '200.00', 'anio_fabricacion': '2021',
        })
        self.assertRedirects(
            respuesta, reverse('maquinaria_detalle', args=[self.unidad.pk]),
        )
        self.unidad.refresh_from_db()
        catalogo = self.unidad.maquinaria
        self.assertEqual(Unidad.objects.count(), 1)
        self.assertEqual(Maquinaria.objects.count(), 1)
        self.assertEqual(self.unidad.numero_serie, 'SERIE-NUEVA')
        self.assertEqual(self.unidad.ubicacion_actual, 'Patio sur')
        self.assertEqual(self.unidad.anio_fabricacion, 2021)
        self.assertEqual(catalogo.codigo, 'RET-NUEVO')
        self.assertEqual(str(catalogo.tarifa_diaria), '200.00')
        self.assertEqual(catalogo.categoria.nombre, 'Excavación')
        self.assertGreaterEqual(self.unidad.fecha_modificacion, inicio)
        self.assertGreaterEqual(catalogo.fecha_modificacion, inicio)
        detalle = self.client.get(reverse('maquinaria_detalle', args=[self.unidad.pk]))
        self.assertContains(detalle, 'Retroexcavadora actualizada')
        self.assertContains(detalle, 'Última modificación')

    def test_own_identifiers_are_allowed_without_fabricating_modification(self):
        respuesta = self.client.post(self.url, self.datos)
        self.assertEqual(respuesta.status_code, 302)
        self.unidad.refresh_from_db()
        self.assertIsNone(self.unidad.fecha_modificacion)
        self.assertIsNone(self.unidad.maquinaria.fecha_modificacion)

    def test_other_codes_and_serials_are_rejected(self):
        crear_unidad(codigo='RET-002', serie='SERIE-002')
        for cambio, campo in (
            ({'codigo': 'ret-002'}, 'codigo'),
            ({'numero_serie': 'serie-002'}, 'numero_serie'),
        ):
            with self.subTest(campo=campo):
                respuesta = self.client.post(self.url, {**self.datos, **cambio})
                self.assertIn(campo, respuesta.context['form'].errors)
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.codigo, 'RET-001')
        self.assertEqual(self.unidad.numero_serie, 'SERIE-001')
        self.assertIsNone(self.unidad.fecha_modificacion)

    def test_invalid_fields_do_not_change_either_record(self):
        for cambio, campo in (
            ({'nombre': ''}, 'nombre'),
            ({'numero_serie': ''}, 'numero_serie'),
            ({'ubicacion_actual': '   '}, 'ubicacion_actual'),
            ({'anio_fabricacion': str(anio_actual() + 1)}, 'anio_fabricacion'),
            ({'tarifa_diaria': '-1'}, 'tarifa_diaria'),
        ):
            with self.subTest(campo=campo):
                respuesta = self.client.post(self.url, {
                    **self.datos, 'categoria': 'No debe crearse',
                    'estado': 'Mantenimiento', **cambio,
                })
                self.assertIn(campo, respuesta.context['form'].errors)
                self.unidad.refresh_from_db()
                self.assertEqual(self.unidad.estado, 'Disponible')
                self.assertIsNone(self.unidad.fecha_modificacion)
                self.assertIsNone(self.unidad.maquinaria.fecha_modificacion)
                self.assertFalse(Categoria.objects.filter(nombre='No debe crearse').exists())

    def test_shared_catalog_and_independent_units(self):
        otra = Unidad.objects.create(
            maquinaria=self.unidad.maquinaria, numero_serie='OTRA-UNIDAD',
            ubicacion_actual='Taller', anio_fabricacion=2019,
        )
        self.client.post(self.url, {
            **self.datos, 'nombre': 'Nombre compartido', 'ubicacion_actual': 'Patio sur',
        })
        otra.refresh_from_db()
        self.unidad.refresh_from_db()
        self.assertEqual(otra.nombre, 'Nombre compartido')
        self.assertEqual(otra.ubicacion_actual, 'Taller')
        self.assertIsNone(otra.fecha_modificacion)
        self.assertEqual(self.unidad.ubicacion_actual, 'Patio sur')

    def test_unit_edit_does_not_stamp_unchanged_catalog(self):
        self.client.post(self.url, {**self.datos, 'ubicacion_actual': 'Patio sur'})
        self.unidad.refresh_from_db()
        self.assertIsNotNone(self.unidad.fecha_modificacion)
        self.assertIsNone(self.unidad.maquinaria.fecha_modificacion)

    def test_non_admin_cannot_edit_by_get_or_post(self):
        grupo = Group.objects.get_or_create(name='Cliente')[0]
        cliente_usuario = get_user_model().objects.create_user(username='cliente_usuario_edicion')
        cliente_usuario.groups.add(grupo)
        sin_rol = get_user_model().objects.create_user(username='sinrol_edicion')
        for usuario in (cliente_usuario, sin_rol):
            self.client.force_login(usuario)
            for metodo in (self.client.get, self.client.post):
                with self.subTest(usuario=usuario.username, metodo=metodo.__name__):
                    respuesta = metodo(self.url, {**self.datos, 'nombre': 'Prohibido'})
                    self.assertEqual(respuesta.status_code, 403)
            self.assertNotContains(self.client.get(reverse('dashboard')), self.url)
        self.client.force_login(cliente_usuario)
        self.assertNotContains(
            self.client.get(reverse('maquinaria_detalle', args=[self.unidad.pk])),
            self.url,
        )
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.nombre, 'Retroexcavadora')
        self.assertIsNone(self.unidad.fecha_modificacion)

    def test_missing_inactive_and_anonymous_access(self):
        self.assertEqual(
            self.client.get(reverse('maquinaria_editar', args=[999999])).status_code, 404,
        )
        self.unidad.activo = False
        self.unidad.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.logout()
        respuesta = self.client.get(self.url)
        self.assertRedirects(respuesta, f'{reverse("login")}?next={self.url}')

    def test_database_failure_rolls_back_catalog_unit_and_category(self):
        from unittest.mock import patch
        from django.db import IntegrityError
        from .forms import MaquinariaEdicionForm
        guardar = MaquinariaEdicionForm._guardar_cambios

        def falla_segundo_guardado(objeto, valores, fecha):
            if isinstance(objeto, Unidad):
                raise IntegrityError('Conflicto simulado')
            guardar(objeto, valores, fecha)

        with patch.object(
            MaquinariaEdicionForm, '_guardar_cambios',
            side_effect=falla_segundo_guardado,
        ):
            respuesta = self.client.post(self.url, {
                **self.datos, 'nombre': 'Debe revertirse',
                'categoria': 'Categoría temporal', 'ubicacion_actual': 'Patio sur',
            })
        self.assertContains(respuesta, 'No se pudieron guardar los cambios.')
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.nombre, 'Retroexcavadora')
        self.assertEqual(self.unidad.ubicacion_actual, 'Patio norte')
        self.assertIsNone(self.unidad.maquinaria.fecha_modificacion)
        self.assertIsNone(self.unidad.fecha_modificacion)
        self.assertFalse(Categoria.objects.filter(nombre='Categoría temporal').exists())
