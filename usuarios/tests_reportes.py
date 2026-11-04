from datetime import date, datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import Mantenimiento, SolicitudAlquiler, Unidad
from .tests import crear_unidad


class Enlaces(HTMLParser):
    def __init__(self, contenido):
        super().__init__()
        self.hrefs = []
        self.feed(contenido)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.hrefs.extend(v for k,v in attrs if k == 'href')


class DatosReportesMixin:
    tipos = ('maquinaria', 'solicitudes', 'entregas', 'mantenimientos')

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username='admin_reportes', first_name='Administrador Ñ')
        self.receptor = User.objects.create_superuser(username='receptor_reportes', first_name='Ana recepción')
        self.cliente_a = User.objects.create_user(username='cliente_a', first_name='María, "Ñ"')
        self.cliente_a.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.cliente_b = User.objects.create_user(username='cliente_b', first_name='José')
        self.cliente_b.groups.add(Group.objects.get_or_create(name='Cliente')[0])
        self.tecnico = User.objects.create_user(username='tecnico_reportes', first_name='Óscar')
        self.tecnico.groups.add(Group.objects.get_or_create(name='Técnico')[0])
        self.staff = User.objects.create_user(username='staff_reportes', is_staff=True)
        self.sin_rol = User.objects.create_user(username='sin_rol_reportes')
        self.unidad = crear_unidad(codigo='EX-001', serie='SERIE-Ñ-001')
        self.unidad.maquinaria.nombre = 'Excavadora, "Ágil"'
        self.unidad.maquinaria.save()
        self.unidad.ubicacion_actual = 'Patio norte'
        self.unidad.save()
        self.segunda = Unidad.objects.create(maquinaria=self.unidad.maquinaria, numero_serie='SEGUNDA', estado='Mantenimiento', ubicacion_actual='Patio sur')
        self.inactiva = Unidad.objects.create(maquinaria=self.unidad.maquinaria, numero_serie='INACTIVA', estado='Baja', activo=False)
        self.alquilada = crear_unidad(codigo='GR-002', serie='ALQUILADA', estado='Alquilado')
        self.pendiente = self.solicitud(self.unidad, self.cliente_a, 'Pendiente', date(2026,10,1), date(2026,10,5))
        self.entregada = self.solicitud(self.alquilada, self.cliente_b, 'Aprobada', date(2026,10,10), date(2026,10,20),
            fecha_salida=self.utc(2026,10,15,2), entregado_por=self.admin)
        self.devuelta = self.solicitud(self.unidad, self.cliente_a, 'Aprobada', date(2026,10,22), date(2026,10,28),
            fecha_salida=self.utc(2026,10,22,15), entregado_por=self.admin,
            fecha_retorno=self.utc(2026,10,24,19), recibido_por=self.receptor)
        self.rechazada = self.solicitud(self.inactiva, self.cliente_b, 'Rechazada', date(2026,9,20), date(2026,10,31))
        self.m1 = Mantenimiento.objects.create(unidad=self.unidad, fecha=date(2026,10,10), tipo='Preventivo',
            descripcion='Cambio, "filtro"; ajuste\nRevisión de ñ y á.', tecnico=self.tecnico, costo=Decimal('10.10'))
        self.m2 = Mantenimiento.objects.create(unidad=self.unidad, fecha=date(2026,10,15), tipo='Correctivo',
            descripcion='<script>alert("x")</script>', tecnico=self.admin, costo=Decimal('20.20'))
        self.m3 = Mantenimiento.objects.create(unidad=self.segunda, fecha=date(2026,10,20), tipo='Preventivo',
            descripcion=None, tecnico=None, costo=Decimal('0.00'))
        self.m4 = Mantenimiento.objects.create(unidad=self.inactiva, fecha=date(2026,9,30), tipo='Correctivo',
            descripcion='Anterior', tecnico=self.admin, costo=Decimal('123.45'))
        self.client.force_login(self.admin)

    @staticmethod
    def utc(*args):
        return datetime(*args, tzinfo=datetime_timezone.utc)

    @staticmethod
    def solicitud(unidad, cliente, estado, inicio, fin, **extra):
        return SolicitudAlquiler.objects.create(unidad=unidad, cliente=cliente, estado=estado, fecha_inicio=inicio, fecha_fin=fin, **extra)

    def pantalla(self, tipo, filtros=None):
        return self.client.get(reverse('reporte_'+tipo), filtros or {})


class ReportesTests(DatosReportesMixin, TestCase):
    def test_csv_retirado_devuelve_410_con_mensaje_sin_consultar_ni_generar_archivo(self):
        filtros = {
            'maquinaria': {'q': 'EX', 'estado': 'Disponible'},
            'solicitudes': {'cliente': self.cliente_a.pk, 'desde': '2026-10-01', 'hasta': '2026-10-30'},
            'entregas': {'desde': '2026-10-14', 'hasta': '2026-10-24', 'situacion': 'devuelta'},
            'mantenimientos': {'unidad': self.unidad.pk, 'tipo': 'Preventivo'},
        }
        for tipo, datos in filtros.items():
            with self.subTest(tipo=tipo):
                with patch('usuarios.reportes.construir_reporte') as consultar, patch('usuarios.reportes.exportar_excel') as exportar:
                    respuesta = self.pantalla(tipo, {**datos, 'formato': 'csv'})
                self.assertContains(respuesta, 'La descarga CSV fue retirada. Utiliza Descargar Excel (.xlsx).', status_code=410)
                self.assertNotIn('Content-Disposition', respuesta)
                self.assertIn('text/html', respuesta['Content-Type'])
                self.assertEqual(respuesta.context['filas'], [])
                consultar.assert_not_called()
                exportar.assert_not_called()
                enlace = respuesta.context['volver_url']
                self.assertIn(enlace, Enlaces(respuesta.content.decode()).hrefs)
                self.assertEqual(parse_qs(urlsplit(enlace).query), {k:[str(v)] for k,v in datos.items()})
                self.assertFalse(any('formato=' in e for e in Enlaces(respuesta.content.decode()).hrefs))

    def test_csv_retirado_incluso_con_filtros_invalidos_no_descarga(self):
        for tipo in self.tipos:
            respuesta = self.pantalla(tipo, {'formato': 'csv', 'desde': 'incorrecta', 'estado': 'Invalido'})
            self.assertContains(respuesta, 'La descarga CSV fue retirada.', status_code=410)
            self.assertNotIn('Content-Disposition', respuesta)

    def test_pantallas_y_menu_solo_anuncian_descarga_excel(self):
        for url in (reverse('reporte_indice'), reverse('dashboard')):
            self.assertNotContains(self.client.get(url), 'CSV')
        for tipo in self.tipos:
            respuesta = self.pantalla(tipo)
            self.assertContains(respuesta, 'Descargar Excel (.xlsx)')
            self.assertNotContains(respuesta, 'CSV')

    def test_indice_menu_panel_y_cuatro_reportes(self):
        indice = self.client.get(reverse('reporte_indice'))
        self.assertEqual(indice.status_code, 200)
        for tipo in self.tipos:
            self.assertContains(indice, reverse('reporte_'+tipo))
            self.assertEqual(self.pantalla(tipo).status_code, 200)
        self.assertContains(self.client.get(reverse('dashboard')), reverse('reporte_indice'), count=2)

    def test_permisos_pantallas_y_descargas_no_administrativos(self):
        for usuario in (self.cliente_a, self.tecnico, self.staff, self.sin_rol):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse('reporte_indice')).status_code, 403)
            for tipo in self.tipos:
                for formato in ('html', 'csv', 'xlsx'):
                    with self.subTest(usuario=usuario.username, tipo=tipo, formato=formato):
                        self.assertEqual(self.pantalla(tipo, {'formato': formato}).status_code, 403)
            self.assertNotContains(self.client.get(reverse('dashboard')), reverse('reporte_indice'))

    def test_anonimo_e_inactivo_no_acceden(self):
        self.client.logout()
        for url in [reverse('reporte_indice'), *[reverse('reporte_'+t) for t in self.tipos]]:
            self.assertRedirects(self.client.get(url), reverse('login')+'?next='+url)
        self.admin.is_active = False
        self.admin.save()
        self.client.force_login(self.admin)
        for tipo in self.tipos:
            for formato in ('csv', 'xlsx'):
                self.assertEqual(self.pantalla(tipo, {'formato': formato}).status_code, 302)

    def test_maquinaria_busqueda_por_cada_dato_y_estado_combinado(self):
        for consulta, series in (
            ('EX-001', {self.unidad.numero_serie, 'SEGUNDA', 'INACTIVA'}),
            ('Ágil', {self.unidad.numero_serie, 'SEGUNDA', 'INACTIVA'}),
            ('SERIE-Ñ', {self.unidad.numero_serie}), ('Patio sur', {'SEGUNDA'}),
        ):
            filas = self.pantalla('maquinaria', {'q': consulta}).context['filas']
            self.assertEqual({r[2] for r in filas}, series)
        filas = self.pantalla('maquinaria', {'q': 'Patio', 'estado': 'Mantenimiento'}).context['filas']
        self.assertEqual([r[2] for r in filas], ['SEGUNDA'])
        self.assertEqual(len(self.pantalla('maquinaria').context['filas']), 4)

    def test_maquinaria_incluye_inactivas_y_desconocidos_sin_inventar_valores(self):
        filas = self.pantalla('maquinaria', {'estado': 'Baja'}).context['filas']
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0][2], 'INACTIVA')
        self.assertEqual(filas[0][-1], '')

    def test_solicitudes_estado_cliente_y_periodo_combinados(self):
        respuesta = self.pantalla('solicitudes', {'estado': 'Aprobada', 'cliente': self.cliente_b.pk,
            'desde': '2026-10-15', 'hasta': '2026-10-16'})
        self.assertEqual([r[0] for r in respuesta.context['filas']], [self.entregada.pk])
        filas = self.pantalla('solicitudes', {'cliente': self.cliente_a.pk}).context['filas']
        self.assertEqual({r[0] for r in filas}, {self.pendiente.pk, self.devuelta.pk})

    def test_periodo_solicitado_interseccion_inclusiva_y_extremos_abiertos(self):
        for filtros, ids in (
            ({'desde': '2026-10-05', 'hasta': '2026-10-05'}, {self.pendiente.pk,self.rechazada.pk}),
            ({'desde': '2026-10-15', 'hasta': '2026-10-16'}, {self.entregada.pk,self.rechazada.pk}),
            ({'desde': '2026-10-29'}, {self.rechazada.pk}),
            ({'hasta': '2026-10-01'}, {self.pendiente.pk,self.rechazada.pk}),
        ):
            filas = self.pantalla('solicitudes', filtros).context['filas']
            self.assertEqual({r[0] for r in filas}, ids)

    def test_cliente_historico_desactivado_o_sin_rol_sigue_filtrable(self):
        self.cliente_a.groups.clear()
        self.cliente_a.is_active = False
        self.cliente_a.save()
        respuesta = self.pantalla('solicitudes', {'cliente': self.cliente_a.pk})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['filas']), 2)

    def test_entregas_excluye_sin_salida_y_filtra_situacion(self):
        todas = self.pantalla('entregas').context['filas']
        self.assertEqual({r[0] for r in todas}, {self.entregada.pk,self.devuelta.pk})
        pendientes = self.pantalla('entregas', {'situacion': 'pendiente'}).context['filas']
        self.assertEqual([r[0] for r in pendientes], [self.entregada.pk])
        self.assertEqual(pendientes[0][4], '')
        self.assertEqual(pendientes[0][6], '')
        devueltas = self.pantalla('entregas', {'situacion': 'devuelta'}).context['filas']
        self.assertEqual([r[0] for r in devueltas], [self.devuelta.pk])
        self.assertIn('Ana recepción', devueltas[0][6])

    def test_entregas_fechas_en_santo_domingo_y_limites_de_dia_completo(self):
        # 15/10 02:00 UTC equivale a 14/10 22:00 en Santo Domingo.
        parametros = {'desde': '2026-10-14', 'hasta': '2026-10-14', 'situacion': 'pendiente'}
        filas = self.pantalla('entregas', parametros).context['filas']
        self.assertEqual([r[0] for r in filas], [self.entregada.pk])
        self.assertEqual(filas[0][3], '2026-10-14 22:00:00')
        limites = [self.utc(2026,10,14,4), self.utc(2026,10,15,3,59,59,999999), self.utc(2026,10,15,4)]
        ids = []
        for fecha in limites:
            registro = self.solicitud(self.unidad,self.cliente_a,'Aprobada',date(2026,10,14),date(2026,10,15),
                fecha_salida=fecha,entregado_por=self.admin,fecha_retorno=fecha+timedelta(hours=1),recibido_por=self.receptor)
            ids.append(registro.pk)
        filas = self.pantalla('entregas', {'desde': '2026-10-14', 'hasta': '2026-10-14'}).context['filas']
        self.assertEqual({r[0] for r in filas}, {self.entregada.pk,ids[0],ids[1]})
        self.assertEqual(self.pantalla('entregas', {'desde': '9999-12-31', 'hasta': '9999-12-31'}).status_code, 200)

    def test_mantenimiento_periodo_unidad_tipo_y_total_exacto(self):
        parametros = {'desde': '2026-10-10', 'hasta': '2026-10-15', 'unidad': self.unidad.pk, 'tipo': 'Preventivo'}
        respuesta = self.pantalla('mantenimientos', parametros)
        self.assertEqual(len(respuesta.context['filas']), 1)
        self.assertEqual(respuesta.context['total_costo'], Decimal('10.10'))
        parametros['tipo'] = ''
        respuesta = self.pantalla('mantenimientos', parametros)
        self.assertEqual(len(respuesta.context['filas']), 2)
        self.assertEqual(respuesta.context['total_costo'], Decimal('30.30'))
        self.assertEqual(self.pantalla('mantenimientos').context['total_costo'], Decimal('153.75'))

    def test_mantenimiento_costo_cero_nulos_y_total_grande_sin_redondeo_float(self):
        respuesta = self.pantalla('mantenimientos', {'unidad': self.segunda.pk})
        filas = respuesta.context['filas']
        self.assertEqual(filas[0][3], '')
        self.assertEqual(filas[0][4], 'No registrado (registro anterior)')
        self.assertEqual(filas[0][-1], Decimal('0.00'))
        self.assertEqual(respuesta.context['total_costo'], Decimal('0.00'))
        for costo in ('9999999999999999.99','0.01'):
            Mantenimiento.objects.create(unidad=self.unidad,fecha=date(2026,10,10),tipo='Preventivo',costo=Decimal(costo))
        respuesta = self.pantalla('mantenimientos', {'unidad': self.unidad.pk})
        self.assertEqual(respuesta.context['total_costo'], Decimal('10000000000000030.30'))

    def test_resultados_vacios_permiten_excel_y_muestran_total_cero(self):
        filtros = {'maquinaria': {'q': 'No existe'}, 'solicitudes': {'desde': '2030-01-01'},
            'entregas': {'desde': '2030-01-01'}, 'mantenimientos': {'desde': '2030-01-01'}}
        for tipo, datos in filtros.items():
            respuesta = self.pantalla(tipo, datos)
            self.assertContains(respuesta, 'Sin resultados')
            self.assertEqual(respuesta.context['filas'], [])
            self.assertContains(respuesta, 'Descargar Excel (.xlsx)')
            if tipo == 'mantenimientos':
                self.assertEqual(respuesta.context['total_costo'], Decimal('0.00'))

    def test_filtros_invalidos_no_exportan_ni_muestran_resultados_sin_filtrar(self):
        parametros = {
            'maquinaria': [{'estado':'Invalido'}, {'q':'x'*201}],
            'solicitudes': [{'estado':'Invalido'}, {'cliente':999999}, {'cliente':'abc'}],
            'entregas': [{'situacion':'Invalida'}],
            'mantenimientos': [{'unidad':999999}, {'unidad':'abc'}, {'tipo':'Otro'}],
        }
        fechas = [{'desde':'incorrecta'}, {'hasta':'2026-02-30'}, {'desde':'2026-10-20','hasta':'2026-10-01'}]
        for tipo in self.tipos:
            casos = parametros[tipo] + ([*fechas] if tipo != 'maquinaria' else []) + [{'formato':'pdf'}]
            for datos in casos:
                for formato in ('html','xlsx'):
                    peticion = {'formato': formato, **datos}
                    with self.subTest(tipo=tipo, datos=peticion):
                        respuesta = self.pantalla(tipo, peticion)
                        self.assertEqual(respuesta.status_code, 400)
                        self.assertNotIn('Content-Disposition', respuesta)
                        self.assertEqual(respuesta.context['filas'], [])
                        self.assertTrue(respuesta.context['form'].errors)
                        self.assertNotContains(respuesta, 'Descargar CSV', status_code=400)
                        self.assertNotContains(respuesta, 'Descargar Excel', status_code=400)

    def test_html_escapa_datos_y_no_ejecuta_texto_de_descripcion(self):
        respuesta = self.pantalla('mantenimientos')
        self.assertNotContains(respuesta, '<script>alert')
        self.assertContains(respuesta, '&lt;script&gt;')

    def test_reportes_no_modifican_solicitudes_unidades_o_mantenimientos(self):
        antes = [list(m.objects.order_by('pk').values()) for m in (Unidad,SolicitudAlquiler,Mantenimiento)]
        for tipo in self.tipos:
            self.pantalla(tipo)
            self.assertEqual(self.pantalla(tipo, {'formato': 'xlsx'}).status_code, 200)
        despues = [list(m.objects.order_by('pk').values()) for m in (Unidad,SolicitudAlquiler,Mantenimiento)]
        self.assertEqual(antes, despues)

    def test_post_no_escribe_y_no_se_inventan_ingresos_o_importes_de_alquiler(self):
        for tipo in self.tipos:
            self.assertEqual(self.client.post(reverse('reporte_'+tipo), {}).status_code, 405)
            if tipo != 'mantenimientos':
                encabezados = self.pantalla(tipo).context['encabezados']
                self.assertFalse(any(palabra in ' '.join(encabezados).lower() for palabra in ('ingreso','pago','subtotal','itbis','importe')))
