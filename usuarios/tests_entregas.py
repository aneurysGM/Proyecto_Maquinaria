from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .entregas import registrar_retorno, registrar_salida
from .forms import FechaMovimientoField, MaquinariaEdicionForm
from .models import Mantenimiento, SolicitudAlquiler, Unidad
from .tests import crear_unidad


def solicitud_para(unidad, cliente, estado='Aprobada'):
    return SolicitudAlquiler.objects.create(
        unidad=unidad, cliente=cliente, estado=estado,
        fecha_inicio=timezone.localdate(), fecha_fin=timezone.localdate()+timedelta(days=3),
    )


class EntregasTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username='admin_entrega', first_name='Administrador salida')
        self.receptor = get_user_model().objects.create_superuser(username='admin_retorno', first_name='Administrador retorno')
        self.cliente_usuario = get_user_model().objects.create_user(username='cliente_entrega', first_name='Cliente de prueba')
        self.cliente_usuario.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.tecnico = get_user_model().objects.create_user(username='tecnico_entrega')
        self.tecnico.groups.add(Group.objects.get_or_create(name='Técnico')[0])
        self.staff = get_user_model().objects.create_user(username='staff_entrega', is_staff=True)
        self.sin_rol = get_user_model().objects.create_user(username='sin_rol_entrega')
        self.unidad = crear_unidad()
        self.unidad.anio_fabricacion = 2020
        self.unidad.ubicacion_actual = 'Patio'
        self.unidad.save()
        self.otra = Unidad.objects.create(maquinaria=self.unidad.maquinaria, numero_serie='OTRA-HU09')
        self.solicitud = solicitud_para(self.unidad, self.cliente_usuario)
        self.salida = (timezone.now()-timedelta(hours=2)).replace(second=0, microsecond=0)
        self.retorno = self.salida+timedelta(hours=1)
        self.url_salida = reverse('entrega_salida', args=[self.solicitud.pk])
        self.url_retorno = reverse('entrega_retorno', args=[self.solicitud.pk])
        self.lista = reverse('entrega_lista')
        self.client.force_login(self.admin)

    def fecha_html(self, fecha):
        return timezone.localtime(fecha, FechaMovimientoField.zona).strftime('%Y-%m-%dT%H:%M')

    def salir(self):
        return self.client.post(self.url_salida, {'fecha_salida': self.fecha_html(self.salida)})

    def volver(self, fecha=None):
        return self.client.post(self.url_retorno, {'fecha_retorno': self.fecha_html(fecha or self.retorno)})

    def snapshot(self):
        return (
            list(SolicitudAlquiler.objects.order_by('pk').values()),
            list(Unidad.objects.order_by('pk').values()),
        )

    def test_salida_desde_aprobada_registra_fecha_admin_y_estado_sin_duplicar_solicitud(self):
        lista = self.client.get(reverse('solicitud_lista'))
        self.assertContains(lista, f'href="{self.url_salida}"')
        form = self.client.get(self.url_salida)
        self.assertContains(form, self.unidad.numero_serie)
        self.assertContains(form, self.cliente_usuario.username)
        self.assertContains(form, 'datetime-local')
        self.assertNotContains(form, 'name="entregado_por"')
        self.assertRedirects(self.salir(), self.lista)
        self.solicitud.refresh_from_db()
        self.unidad.refresh_from_db()
        self.assertEqual(self.solicitud.fecha_salida, self.salida)
        self.assertEqual(self.solicitud.entregado_por_id, self.admin.pk)
        self.assertIsNone(self.solicitud.fecha_retorno)
        self.assertEqual(self.solicitud.estado, 'Aprobada')
        self.assertEqual(self.unidad.estado, 'Alquilado')
        self.otra.refresh_from_db()
        self.assertEqual(self.otra.estado, 'Disponible')
        self.assertEqual(SolicitudAlquiler.objects.count(), 1)
        self.assertNotContains(self.client.get(reverse('solicitud_lista')), f'href="{self.url_salida}"')

    def test_retorno_registra_otro_admin_y_pasa_a_historial(self):
        self.salir()
        self.client.force_login(self.receptor)
        pendientes = self.client.get(self.lista)
        self.assertContains(pendientes, self.url_retorno)
        self.assertContains(pendientes, 'Pendiente de devolución')
        self.assertRedirects(self.volver(), self.lista)
        self.solicitud.refresh_from_db()
        self.unidad.refresh_from_db()
        self.assertEqual(self.solicitud.fecha_retorno, self.retorno)
        self.assertEqual(self.solicitud.recibido_por_id, self.receptor.pk)
        self.assertEqual(self.solicitud.entregado_por_id, self.admin.pk)
        self.assertEqual(self.unidad.estado, 'Disponible')
        self.assertContains(self.client.get(self.lista), 'No hay entregas pendientes')
        for filtro in ('devueltas', 'todas'):
            historial = self.client.get(self.lista, {'estado': filtro})
            self.assertContains(historial, 'Devuelta')
            for texto in (self.unidad.numero_serie, self.cliente_usuario.username, 'Administrador salida', 'Administrador retorno'):
                self.assertContains(historial, texto)
            self.assertNotContains(historial, self.url_retorno)
        self.assertEqual(self.client.get(self.lista, {'estado': 'invalido'}).status_code, 400)

    def test_solo_aprobadas_y_no_repetir_salida_incluso_despues_del_retorno(self):
        for estado in ('Pendiente', 'Rechazada'):
            SolicitudAlquiler.objects.filter(pk=self.solicitud.pk).update(estado=estado)
            self.assertContains(self.salir(), 'solicitud aprobada')
            self.assertIsNone(SolicitudAlquiler.objects.get(pk=self.solicitud.pk).fecha_salida)
        SolicitudAlquiler.objects.filter(pk=self.solicitud.pk).update(estado='Aprobada')
        self.salir()
        antes = self.snapshot()
        self.assertContains(self.salir(), 'ya fue entregada')
        self.assertEqual(antes, self.snapshot())
        self.volver()
        antes = self.snapshot()
        self.assertContains(self.salir(), 'ya fue entregada')
        self.assertEqual(antes, self.snapshot())

    def test_salida_rechaza_estados_inactivos_y_catalogo_inactivo(self):
        for estado in ('Alquilado', 'Mantenimiento', 'Baja'):
            Unidad.objects.filter(pk=self.unidad.pk).update(estado=estado)
            antes = self.snapshot()
            self.assertContains(self.salir(), 'activa y Disponible')
            self.assertEqual(antes, self.snapshot())
        Unidad.objects.filter(pk=self.unidad.pk).update(estado='Disponible', activo=False)
        self.assertContains(self.salir(), 'activa y Disponible')
        Unidad.objects.filter(pk=self.unidad.pk).update(activo=True)
        self.unidad.maquinaria.activo = False
        self.unidad.maquinaria.save()
        self.assertContains(self.salir(), 'activa y Disponible')
        self.assertIsNone(SolicitudAlquiler.objects.get(pk=self.solicitud.pk).fecha_salida)

    def test_retorno_sin_salida_y_retorno_duplicado_no_cambian_datos(self):
        antes = self.snapshot()
        self.assertContains(self.volver(), 'no tiene una salida')
        self.assertEqual(antes, self.snapshot())
        self.salir()
        self.volver()
        antes = self.snapshot()
        self.assertContains(self.volver(), 'ya fue registrado')
        self.assertEqual(antes, self.snapshot())

    def test_retorno_anterior_se_rechaza_y_mismo_instante_se_admite(self):
        self.salir()
        antes = self.snapshot()
        self.assertContains(self.volver(self.salida-timedelta(minutes=1)), 'anterior a la salida')
        self.assertEqual(antes, self.snapshot())
        self.assertRedirects(self.volver(self.salida), self.lista)

    def test_fechas_obligatorias_invalidas_y_futuras(self):
        for url, campo in ((self.url_salida, 'fecha_salida'), (self.url_retorno, 'fecha_retorno')):
            for fecha in ('', 'incorrecta', '2026-02-30T12:00', self.fecha_html(timezone.now()+timedelta(days=1))):
                with self.subTest(campo=campo, fecha=fecha):
                    antes = self.snapshot()
                    respuesta = self.client.post(url, {campo: fecha})
                    self.assertEqual(respuesta.status_code, 200)
                    self.assertTrue(respuesta.context['form'].errors)
                    self.assertEqual(antes, self.snapshot())

    def test_no_se_suplantan_cliente_unidad_admin_o_fechas_por_campos_extra(self):
        self.client.post(self.url_salida, {
            'fecha_salida': self.fecha_html(self.salida), 'entregado_por': self.receptor.pk,
            'unidad': self.otra.pk, 'cliente': self.admin.pk, 'fecha_retorno': self.fecha_html(self.retorno),
            'estado': 'Rechazada',
        })
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.cliente_id, self.cliente_usuario.pk)
        self.assertEqual(self.solicitud.unidad_id, self.unidad.pk)
        self.assertEqual(self.solicitud.entregado_por_id, self.admin.pk)
        self.assertIsNone(self.solicitud.fecha_retorno)
        self.client.post(self.url_retorno, {'fecha_retorno': self.fecha_html(self.retorno), 'recibido_por': self.receptor.pk})
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.recibido_por_id, self.admin.pk)

    def test_roles_no_administrativos_no_acceden_por_get_post_o_servicio(self):
        antes = self.snapshot()
        for usuario in (self.cliente_usuario, self.tecnico, self.staff, self.sin_rol):
            self.client.force_login(usuario)
            for url in (self.lista, self.url_salida, self.url_retorno):
                for metodo in (self.client.get, self.client.post):
                    self.assertEqual(metodo(url, {}).status_code, 403)
            self.assertNotContains(self.client.get(reverse('dashboard')), 'Salidas y retornos')
            with self.assertRaises(PermissionDenied):
                registrar_salida(self.solicitud.pk, administrador=usuario, fecha_salida=self.salida)
            with self.assertRaises(PermissionDenied):
                registrar_retorno(self.solicitud.pk, administrador=usuario, fecha_retorno=self.retorno)
        self.assertEqual(antes, self.snapshot())

    def test_anonimos_inactivos_csrf_y_get_no_escriben(self):
        antes = self.snapshot()
        for url in (self.url_salida, self.url_retorno):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(antes, self.snapshot())
        self.client.logout()
        for url in (self.lista, self.url_salida, self.url_retorno):
            self.assertRedirects(self.client.get(url), f'{reverse("login")}?next={url}')
        self.admin.is_active = False
        self.admin.save()
        with self.assertRaises(PermissionDenied):
            registrar_salida(self.solicitud.pk, administrador=self.admin, fecha_salida=self.salida)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.receptor)
        self.assertEqual(cliente.post(self.url_salida, {'fecha_salida': self.fecha_html(self.salida)}).status_code, 403)
        self.assertEqual(antes, self.snapshot())

    def test_ids_inexistentes_y_metodos_no_crean_movimientos(self):
        antes = self.snapshot()
        for url in (self.url_salida, self.url_retorno):
            self.assertEqual(self.client.put(url, {}).status_code, 405)
            self.assertEqual(self.client.delete(url).status_code, 405)
        self.assertEqual(antes, self.snapshot())
        for vista in ('entrega_salida', 'entrega_retorno'):
            url = reverse(vista, args=[999999])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, {}).status_code, 404)

    def test_otra_solicitud_no_se_entrega_mientras_hay_pendiente_aunque_cambie_estado_por_sql(self):
        segunda = solicitud_para(self.unidad, self.cliente_usuario)
        self.salir()
        # Una escritura ajena al flujo no debe permitir duplicar la entrega.
        Unidad.objects.filter(pk=self.unidad.pk).update(estado='Disponible')
        with self.assertRaisesMessage(ValidationError, 'entrega pendiente'):
            registrar_salida(segunda.pk, administrador=self.admin, fecha_salida=self.salida)
        self.assertEqual(SolicitudAlquiler.objects.filter(fecha_salida__isnull=False).count(), 1)

    def test_otra_solicitud_puede_entregarse_despues_de_un_retorno(self):
        self.salir()
        self.volver()
        segunda = solicitud_para(self.unidad, self.cliente_usuario)
        registrar_salida(segunda.pk, administrador=self.admin, fecha_salida=self.retorno)
        self.assertEqual(SolicitudAlquiler.objects.filter(fecha_salida__isnull=False).count(), 2)
        self.assertEqual(SolicitudAlquiler.objects.filter(fecha_salida__isnull=False, fecha_retorno__isnull=True).count(), 1)

    def test_retorno_de_unidad_desactivada_conserva_historial(self):
        self.salir()
        Unidad.objects.filter(pk=self.unidad.pk).update(activo=False)
        self.cliente_usuario.is_active = False
        self.cliente_usuario.save()
        self.assertRedirects(self.volver(), self.lista)
        self.unidad.refresh_from_db()
        self.assertFalse(self.unidad.activo)
        self.assertEqual(self.unidad.estado, 'Disponible')
        self.assertContains(self.client.get(self.lista, {'estado': 'todas'}), self.unidad.numero_serie)
        with self.assertRaises(ProtectedError):
            self.cliente_usuario.delete()

    def test_retorno_con_estado_inesperado_no_sobrescribe_mantenimiento(self):
        self.salir()
        Unidad.objects.filter(pk=self.unidad.pk).update(estado='Mantenimiento')
        antes = self.snapshot()
        self.assertContains(self.volver(), 'no corresponde a una entrega pendiente')
        self.assertEqual(antes, self.snapshot())

    def test_edicion_manual_no_libera_una_unidad_con_entrega_pendiente(self):
        self.salir()
        self.unidad.refresh_from_db()
        datos = {campo: '' if valor is None else valor for campo, valor in MaquinariaEdicionForm(unidad=self.unidad).initial.items()}
        datos['estado'] = 'Disponible'
        antes = self.snapshot()
        respuesta = self.client.post(reverse('maquinaria_editar', args=[self.unidad.pk]), datos)
        self.assertContains(respuesta, 'entrega pendiente')
        self.assertEqual(antes, self.snapshot())
        self.unidad.estado = 'Disponible'
        with self.assertRaises(ValidationError):
            self.unidad.full_clean()

    def test_mantenimiento_y_solicitudes_siguen_rechazando_unidad_entregada(self):
        self.salir()
        self.client.force_login(self.tecnico)
        respuesta = self.client.post(reverse('mantenimiento_registrar'), {
            'unidad': self.unidad.pk, 'fecha': timezone.localdate().isoformat(),
            'tipo': 'Preventivo', 'descripcion': 'No registrar', 'costo': '0',
        })
        self.assertIn('unidad', respuesta.context['form'].errors)
        self.assertFalse(Mantenimiento.objects.exists())
        self.client.force_login(self.cliente_usuario)
        respuesta = self.client.post(reverse('solicitud_registrar', args=[self.unidad.pk]), {
            'fecha_inicio': timezone.localdate().isoformat(),
            'fecha_fin': (timezone.localdate()+timedelta(days=1)).isoformat(),
        })
        self.assertContains(respuesta, 'ya no está disponible')
        self.assertEqual(SolicitudAlquiler.objects.count(), 1)

    def test_fallo_en_guardado_de_solicitud_no_cambia_unidad(self):
        antes = self.snapshot()
        with patch.object(SolicitudAlquiler, 'save', side_effect=OperationalError('Fallo SQL')):
            self.assertContains(self.salir(), 'No se guardaron cambios')
        self.assertEqual(antes, self.snapshot())

    def test_fallo_real_al_actualizar_unidad_revierte_salida_y_retorno(self):
        guardar = Unidad.save
        def falla(unidad, *args, **kwargs):
            unidad.estado = 'No valido'
            return guardar(unidad, *args, **kwargs)
        antes = self.snapshot()
        with patch.object(Unidad, 'save', falla):
            self.assertContains(self.salir(), 'No se guardaron cambios')
        self.assertEqual(antes, self.snapshot())
        self.salir()
        antes = self.snapshot()
        with patch.object(Unidad, 'save', falla):
            self.assertContains(self.volver(), 'No se guardaron cambios')
        self.assertEqual(antes, self.snapshot())

    def test_fallo_despues_de_ambos_guardados_revierte_todo(self):
        guardar = Unidad.save
        def falla(unidad, *args, **kwargs):
            guardar(unidad, *args, **kwargs)
            raise OperationalError('Fallo después del cambio de estado')
        antes = self.snapshot()
        with patch.object(Unidad, 'save', falla):
            self.assertContains(self.salir(), 'No se guardaron cambios')
        self.assertEqual(antes, self.snapshot())
        self.salir()
        antes = self.snapshot()
        with patch.object(Unidad, 'save', falla):
            self.assertContains(self.volver(), 'No se guardaron cambios')
        self.assertEqual(antes, self.snapshot())

    def test_restricciones_sql_impiden_fechas_incoherentes_y_doble_entrega(self):
        for cambios in (
            {'fecha_salida': self.salida},
            {'entregado_por': self.admin},
            {'fecha_retorno': self.retorno, 'recibido_por': self.admin},
            {'estado': 'Pendiente', 'fecha_salida': self.salida, 'entregado_por': self.admin},
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                SolicitudAlquiler.objects.filter(pk=self.solicitud.pk).update(**cambios)
        self.salir()
        for cambios in (
            {'fecha_retorno': self.salida-timedelta(minutes=1), 'recibido_por': self.admin},
            {'fecha_retorno': self.retorno},
            {'recibido_por': self.admin},
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                SolicitudAlquiler.objects.filter(pk=self.solicitud.pk).update(**cambios)
        segunda = solicitud_para(self.unidad, self.cliente_usuario)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SolicitudAlquiler.objects.filter(pk=segunda.pk).update(fecha_salida=self.salida, entregado_por=self.admin)


@skipUnless(connection.vendor == 'microsoft', 'Pruebas de concurrencia y migración SQL Server')
class EntregasSQLTests(TransactionTestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username='admin_sql_hu09')
        self.cliente_usuario = get_user_model().objects.create_user(username='cliente_sql_hu09')
        self.unidad = crear_unidad()
        self.solicitud = solicitud_para(self.unidad, self.cliente_usuario)
        self.fecha = timezone.now()-timedelta(hours=1)

    def competir(self, funcion, ids, campo):
        barrera = Barrier(2)
        base_temporal = connection.settings_dict['NAME']
        admin_id = self.admin.pk
        fecha = self.fecha
        def intento(solicitud_id):
            conn = connections['default']
            try:
                if conn.settings_dict['NAME'] != base_temporal or not str(base_temporal).startswith('test_'):
                    raise RuntimeError('La concurrencia solo puede probarse en la base temporal.')
                with conn.cursor() as cursor:
                    cursor.execute('SET LOCK_TIMEOUT 10000')
                administrador = get_user_model().objects.get(pk=admin_id)
                barrera.wait(timeout=10)
                try:
                    funcion(solicitud_id, administrador=administrador, **{campo: fecha})
                    return 'registrado'
                except ValidationError:
                    return 'rechazado'
            finally:
                conn.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futuros = [executor.submit(intento, pk) for pk in ids]
            resultados = [f.result(timeout=25) for f in futuros]
        self.assertCountEqual(resultados, ['registrado', 'rechazado'])

    def test_dos_salidas_simultaneas_para_la_misma_solicitud(self):
        self.competir(registrar_salida, [self.solicitud.pk]*2, 'fecha_salida')
        self.assertEqual(SolicitudAlquiler.objects.filter(fecha_salida__isnull=False).count(), 1)
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.estado, 'Alquilado')

    def test_dos_solicitudes_simultaneas_para_la_misma_unidad(self):
        segunda = solicitud_para(self.unidad, self.cliente_usuario)
        self.competir(registrar_salida, [self.solicitud.pk, segunda.pk], 'fecha_salida')
        self.assertEqual(SolicitudAlquiler.objects.filter(fecha_salida__isnull=False).count(), 1)

    def test_dos_retornos_simultaneos(self):
        registrar_salida(self.solicitud.pk, administrador=self.admin, fecha_salida=self.fecha-timedelta(hours=1))
        self.competir(registrar_retorno, [self.solicitud.pk]*2, 'fecha_retorno')
        self.unidad.refresh_from_db()
        self.assertEqual(self.unidad.estado, 'Disponible')

    def test_indice_filtrado_es_unico_y_los_check_estan_activos(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT is_unique,has_filter,filter_definition FROM sys.indexes WHERE object_id=OBJECT_ID('usuarios_solicitudalquiler') AND name='UQ_Entrega_Unidad_Pendiente'")
            unico, filtrado, definicion = cursor.fetchone()
            self.assertTrue(unico and filtrado)
            self.assertIn('fecha_salida', definicion)
            self.assertIn('fecha_retorno', definicion)
            cursor.execute("SELECT name,is_disabled,is_not_trusted FROM sys.check_constraints WHERE name IN ('CK_Solicitud_Salida','CK_Solicitud_Retorno')")
            checks = cursor.fetchall()
            self.assertEqual(len(checks), 2)
            # El flush de mssql-django puede dejar CHECK como no confiables,
            # aunque siguen habilitados y rechazan datos nuevos inválidos.
            self.assertTrue(all(not desactivado for _,desactivado,_ in checks))

    def test_migracion_preserva_solicitudes_previas_sin_inventar_entregas(self):
        ejecutor = MigrationExecutor(connection)
        anterior = ('usuarios', '0011_eliminar_operador_sql')
        nueva = ('usuarios', '0012_salida_retorno_maquinaria')
        try:
            ejecutor.migrate([anterior])
            historicas = ejecutor.loader.project_state([anterior]).apps
            solicitud = historicas.get_model('usuarios', 'SolicitudAlquiler')
            for estado in ('Pendiente', 'Rechazada'):
                solicitud.objects.create(cliente_id=self.cliente_usuario.pk, unidad_id=self.unidad.pk,
                    estado=estado, fecha_inicio=timezone.localdate(), fecha_fin=timezone.localdate())
            antes = list(solicitud.objects.order_by('pk').values())
            ejecutor = MigrationExecutor(connection)
            ejecutor.migrate([nueva])
            self.assertEqual(antes, list(solicitud.objects.order_by('pk').values()))
            self.assertEqual(SolicitudAlquiler.objects.filter(fecha_salida__isnull=True,
                fecha_retorno__isnull=True, entregado_por__isnull=True, recibido_por__isnull=True).count(), 3)
            with connection.cursor() as cursor:
                cursor.execute("SELECT is_disabled,is_not_trusted FROM sys.check_constraints WHERE name IN ('CK_Solicitud_Salida','CK_Solicitud_Retorno')")
                self.assertEqual([tuple(row) for row in cursor.fetchall()], [(False, False), (False, False)])
        finally:
            MigrationExecutor(connection).migrate([nueva])
