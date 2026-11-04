from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import SolicitudAlquiler, Unidad
from .tests import crear_unidad


class SolicitudesTests(TestCase):
    def setUp(self):
        self.unidad = crear_unidad()
        self.cliente = get_user_model().objects.create_user(username='cliente_solicitudes')
        self.cliente.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.otro = get_user_model().objects.create_user(username='otro_cliente')
        self.otro.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.tecnico = get_user_model().objects.create_user(username='tecnico_solicitudes')
        self.tecnico.groups.add(Group.objects.get_or_create(name='Técnico')[0])
        self.admin = get_user_model().objects.create_superuser(username='admin_solicitudes')
        self.url = reverse('solicitud_registrar', args=[self.unidad.pk])
        self.lista = reverse('solicitud_lista')
        self.inicio = timezone.localdate() + timedelta(days=2)
        self.fin = self.inicio + timedelta(days=3)
        self.datos = {'fecha_inicio': self.inicio.isoformat(), 'fecha_fin': self.fin.isoformat(), 'comentario': 'Obra en San Luis'}
        self.client.force_login(self.cliente)

    def enviar(self):
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 302)
        return SolicitudAlquiler.objects.latest('id')

    def resolver(self, solicitud, decision='Aprobada'):
        self.client.force_login(self.admin)
        return self.client.post(reverse('solicitud_resolver', args=[solicitud.pk]), {'decision': decision}, follow=True)

    def test_cliente_envia_y_consulta_solo_sus_solicitudes(self):
        registro = self.enviar()
        self.assertEqual(registro.cliente, self.cliente)
        self.assertEqual(registro.estado, 'Pendiente')
        self.assertIsNone(registro.revisado_por)
        self.assertContains(self.client.get(self.lista), 'Obra en San Luis')
        self.client.force_login(self.otro)
        self.assertNotContains(self.client.get(self.lista), 'Obra en San Luis')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.lista), 'Obra en San Luis')

    def test_cliente_solicita_desde_listado_con_la_unidad_correcta(self):
        otra = Unidad.objects.create(maquinaria=self.unidad.maquinaria, numero_serie='OTRA-SERIE')
        respuesta = self.client.get(reverse('maquinaria_lista'))
        self.assertContains(respuesta, 'Solicitar alquiler', count=2)
        for unidad in (self.unidad, otra):
            url = reverse('solicitud_registrar', args=[unidad.pk])
            self.assertContains(respuesta, f'<a href="{url}">Solicitar alquiler</a>', html=True)
            detalle = reverse('maquinaria_detalle', args=[unidad.pk])
            self.assertContains(respuesta, f'<a href="{detalle}">Ver detalles</a>', html=True)
            formulario = self.client.get(url)
            self.assertEqual(formulario.context['unidad'].pk, unidad.pk)
            self.assertContains(formulario, unidad.numero_serie)
        self.assertRedirects(
            self.client.post(reverse('solicitud_registrar', args=[otra.pk]), self.datos),
            self.lista,
        )
        solicitud = SolicitudAlquiler.objects.get()
        self.assertEqual(solicitud.unidad_id, otra.pk)
        self.assertEqual(solicitud.cliente_id, self.cliente.pk)

    def test_listado_no_ofrece_solicitar_a_administrador_o_tecnico(self):
        for usuario in (self.admin, self.tecnico):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                respuesta = self.client.get(reverse('maquinaria_lista'))
                self.assertNotContains(respuesta, 'Solicitar alquiler')
                detalle = reverse('maquinaria_detalle', args=[self.unidad.pk])
                self.assertContains(respuesta, f'<a href="{detalle}">Ver detalles</a>', html=True)

    def test_cambio_de_estado_oculta_accion_y_rechaza_solicitud_por_url(self):
        self.assertContains(self.client.get(reverse('maquinaria_lista')), 'Solicitar alquiler')
        for estado in ('Alquilado', 'Mantenimiento', 'Baja'):
            with self.subTest(estado=estado):
                self.unidad.estado = estado
                self.unidad.save(update_fields=['estado'])
                listado = self.client.get(reverse('maquinaria_lista'))
                self.assertNotContains(listado, 'Solicitar alquiler')
                self.assertContains(listado, 'Ver detalles')
                self.assertContains(self.client.post(self.url, self.datos), 'ya no está disponible')
                self.assertFalse(SolicitudAlquiler.objects.exists())

    def test_campos_extra_no_suplantan_cliente_estado_o_unidad(self):
        self.client.post(self.url, {**self.datos, 'cliente': self.otro.pk, 'estado': 'Aprobada', 'unidad': 9999, 'revisado_por': self.admin.pk})
        registro = SolicitudAlquiler.objects.get()
        self.assertEqual(registro.cliente, self.cliente)
        self.assertEqual(registro.unidad, self.unidad)
        self.assertEqual(registro.estado, 'Pendiente')
        self.assertIsNone(registro.revisado_por)

    def test_fechas_obligatorias_invalidas_pasadas_y_orden_inverso(self):
        for cambios in ({'fecha_inicio': ''}, {'fecha_fin': 'incorrecta'}, {'fecha_inicio': (timezone.localdate()-timedelta(days=1)).isoformat()}, {'fecha_fin': (self.inicio-timedelta(days=1)).isoformat()}):
            respuesta = self.client.post(self.url, {**self.datos, **cambios})
            self.assertEqual(respuesta.status_code, 200)
            self.assertTrue(respuesta.context['form'].errors)
        self.assertFalse(SolicitudAlquiler.objects.exists())

    def test_rechaza_unidad_no_disponible_y_duplicado(self):
        self.enviar()
        self.assertContains(self.client.post(self.url, self.datos), 'Ya tienes una solicitud pendiente')
        self.unidad.estado = 'Mantenimiento'
        self.unidad.save()
        self.assertContains(self.client.post(self.url, {**self.datos, 'fecha_fin': (self.fin+timedelta(days=1)).isoformat()}), 'ya no está disponible')
        self.assertEqual(SolicitudAlquiler.objects.count(), 1)

    def test_admin_aprueba_registra_autor_y_no_permite_doble_revision(self):
        registro = self.enviar()
        self.assertContains(self.resolver(registro), 'Solicitud aprobada correctamente')
        registro.refresh_from_db()
        self.assertEqual(registro.estado, 'Aprobada')
        self.assertEqual(registro.revisado_por, self.admin)
        fecha = registro.fecha_revision
        self.assertContains(self.resolver(registro, 'Rechazada'), 'ya fue revisada')
        registro.refresh_from_db()
        self.assertEqual(registro.estado, 'Aprobada')
        self.assertEqual(registro.fecha_revision, fecha)

    def test_admin_rechaza_sin_reservar_fechas(self):
        registro = self.enviar()
        self.resolver(registro, 'Rechazada')
        registro.refresh_from_db()
        self.assertEqual(registro.estado, 'Rechazada')
        self.client.force_login(self.cliente)
        self.enviar()

    def test_evitar_aprobaciones_solapadas_y_permitir_periodos_distintos(self):
        primero = self.enviar()
        self.client.force_login(self.otro)
        segundo = self.enviar()
        self.resolver(primero)
        self.assertContains(self.resolver(segundo), 'Ya existe una solicitud aprobada')
        segundo.refresh_from_db()
        self.assertEqual(segundo.estado, 'Pendiente')
        self.client.force_login(self.otro)
        self.assertContains(self.client.post(self.url, self.datos), 'ya tiene una solicitud aprobada')
        self.client.post(self.url, {**self.datos, 'fecha_inicio': (self.fin+timedelta(days=1)).isoformat(), 'fecha_fin': (self.fin+timedelta(days=2)).isoformat()})
        tercero = SolicitudAlquiler.objects.latest('id')
        self.resolver(tercero)
        tercero.refresh_from_db()
        self.assertEqual(tercero.estado, 'Aprobada')

    def test_cambio_disponibilidad_impide_aprobar(self):
        registro = self.enviar()
        self.unidad.estado = 'Alquilado'
        self.unidad.save()
        self.assertContains(self.resolver(registro), 'no está disponible')
        registro.refresh_from_db()
        self.assertEqual(registro.estado, 'Pendiente')

    def test_permisos_servidor_y_metodo_post_para_resolver(self):
        registro = self.enviar()
        resolver = reverse('solicitud_resolver', args=[registro.pk])
        for usuario in (self.cliente, self.otro, self.tecnico):
            self.client.force_login(usuario)
            self.assertEqual(self.client.post(resolver, {'decision': 'Aprobada'}).status_code, 403)
        for usuario in (self.admin, self.tecnico):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)
        self.client.force_login(self.tecnico)
        self.assertEqual(self.client.get(self.lista).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(resolver).status_code, 405)
        self.assertEqual(self.client.post(resolver, {'decision': 'Invalida'}).status_code, 400)
        registro.refresh_from_db()
        self.assertEqual(registro.estado, 'Pendiente')

    def test_anonimos_y_csrf(self):
        self.client.logout()
        for url in (self.url, self.lista):
            self.assertRedirects(self.client.get(url), f'{reverse("login")}?next={url}')
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.cliente)
        self.assertEqual(cliente.post(self.url, self.datos).status_code, 403)
        self.assertFalse(SolicitudAlquiler.objects.exists())

    def test_paneles_enlaces_y_operadores_retirados(self):
        for usuario, rol in ((self.cliente, 'Cliente'), (self.tecnico, 'Técnico'), (self.admin, 'Administrador')):
            self.client.force_login(usuario)
            panel = self.client.get(reverse('dashboard'))
            self.assertContains(panel, 'Panel de '+rol)
            self.assertNotContains(panel, '/operadores/')
            for url in ('/operadores/', '/operadores/registrar/', '/operadores/1/'):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {}).status_code, 404)
        self.client.force_login(self.cliente)
        detalle = self.client.get(reverse('maquinaria_detalle', args=[self.unidad.pk]))
        self.assertContains(detalle, self.url)
        self.assertNotContains(detalle, 'Costo de adquisición')
