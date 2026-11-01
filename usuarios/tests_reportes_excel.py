from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

from django.test import SimpleTestCase, TestCase
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .exportacion_excel import (
    FORMATO_COSTO, FORMATO_FECHA, FORMATO_FECHA_HORA, MIME_XLSX, exportar_excel,
)
from .models import Mantenimiento, SolicitudAlquiler, Unidad
from .tests_reportes import DatosReportesMixin, Enlaces


class ReportesExcelTests(DatosReportesMixin, TestCase):
    def excel(self, tipo, filtros=None):
        respuesta = self.pantalla(tipo, {**(filtros or {}), 'formato': 'xlsx'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], MIME_XLSX)
        self.assertEqual(respuesta['Content-Disposition'], f'attachment; filename="reporte_{tipo}.xlsx"')
        self.assertTrue(respuesta.content.startswith(b'PK'))
        with ZipFile(BytesIO(respuesta.content)) as archivo:
            self.assertIsNone(archivo.testzip())
            self.assertIn('[Content_Types].xml', archivo.namelist())
        return load_workbook(BytesIO(respuesta.content))

    def test_cuatro_xlsx_reales_con_encabezados_anchos_filtros_y_panel_inmovilizado(self):
        for tipo in self.tipos:
            with self.subTest(tipo=tipo):
                pantalla = self.pantalla(tipo)
                hoja = self.excel(tipo).active
                self.assertEqual([c.value for c in hoja[1]], list(pantalla.context['encabezados']))
                self.assertTrue(all(c.font.bold for c in hoja[1]))
                self.assertEqual(hoja.freeze_panes, 'A2')
                columnas = len(pantalla.context['encabezados'])
                filas = len(pantalla.context['filas'])
                self.assertEqual(hoja.auto_filter.ref, f'A1:{get_column_letter(columnas)}{filas+1}')
                for indice in range(1, columnas+1):
                    self.assertGreaterEqual(hoja.column_dimensions[get_column_letter(indice)].width, 12)
                self.assertGreater(hoja.row_dimensions[1].height, 15)

    def test_enlace_excel_conserva_exactamente_los_filtros_y_es_la_unica_descarga(self):
        filtros = {
            'maquinaria': {'q': 'EX', 'estado': 'Disponible'},
            'solicitudes': {'cliente': self.cliente_a.pk, 'desde': '2026-10-01', 'hasta': '2026-10-30'},
            'entregas': {'desde': '2026-10-14', 'hasta': '2026-10-24', 'situacion': 'devuelta'},
            'mantenimientos': {'desde': '2026-10-10', 'hasta': '2026-10-15', 'unidad': self.unidad.pk},
        }
        for tipo, datos in filtros.items():
            with self.subTest(tipo=tipo):
                pantalla = self.pantalla(tipo, datos)
                self.assertContains(pantalla, 'Descargar Excel (.xlsx)')
                enlaces = Enlaces(pantalla.content.decode()).hrefs
                enlace = next(e for e in enlaces if 'formato=xlsx' in e)
                self.assertEqual(parse_qs(urlsplit(enlace).query), {
                    **{k: [str(v)] for k,v in datos.items()}, 'formato': ['xlsx'],
                })
                hoja = load_workbook(BytesIO(self.client.get(enlace).content)).active
                datos_excel = list(hoja.iter_rows(min_row=2, values_only=True))
                if tipo == 'mantenimientos':
                    self.assertEqual(Decimal(str(datos_excel[-1][-1])), pantalla.context['total_costo'])
                    datos_excel = datos_excel[:-1]
                filas_normalizadas = []
                for fila in datos_excel:
                    normalizada = []
                    for valor in fila:
                        if isinstance(valor, datetime):
                            valor = valor.strftime('%Y-%m-%d %H:%M:%S') if tipo == 'entregas' else valor.date().isoformat()
                        elif isinstance(valor, date):
                            valor = valor.isoformat()
                        normalizada.append('' if valor is None else str(valor))
                    filas_normalizadas.append(normalizada)
                esperadas = [[str(v) for v in fila] for fila in pantalla.context['filas']]
                # Los costos son números Excel; comparar su valor, no los ceros de presentación.
                if tipo == 'mantenimientos':
                    for fila, esperada in zip(filas_normalizadas, esperadas):
                        fila[-1] = format(Decimal(fila[-1]), '.2f')
                self.assertEqual(filas_normalizadas, esperadas)
                self.assertFalse(any('formato=csv' in e for e in enlaces))
                self.assertNotContains(pantalla, 'Descargar CSV')

    def test_codigos_series_y_solicitudes_se_guardan_como_texto_sin_perder_ceros(self):
        self.unidad.maquinaria.codigo = '000001'
        self.unidad.maquinaria.save()
        self.unidad.numero_serie = '000000000000000123456'
        self.unidad.save()
        hoja = self.excel('maquinaria', {'q': self.unidad.numero_serie}).active
        self.assertEqual(hoja['A2'].value, '000001')
        self.assertEqual(hoja['C2'].value, '000000000000000123456')
        for coordenada in ('A2', 'C2'):
            self.assertEqual(hoja[coordenada].data_type, 's')
            self.assertEqual(hoja[coordenada].number_format, '@')
        solicitudes = self.excel('solicitudes', {'cliente': self.cliente_a.pk}).active
        self.assertEqual(solicitudes['A2'].value, str(self.pendiente.pk))
        self.assertEqual(solicitudes['A2'].data_type, 's')
        self.assertIn('000000000000000123456', solicitudes['C2'].value)

    def test_fechas_nativas_y_hora_local_sin_zona_horaria_de_excel(self):
        solicitudes = self.excel('solicitudes', {'cliente': self.cliente_a.pk}).active
        for coordenada, esperado in (('D2', date(2026,10,1)), ('E2', date(2026,10,5))):
            celda = solicitudes[coordenada]
            self.assertTrue(celda.is_date)
            self.assertEqual(celda.value.date(), esperado)
            self.assertEqual(celda.number_format, FORMATO_FECHA)
        entregas = self.excel('entregas', {'situacion': 'pendiente'}).active
        self.assertEqual(entregas['D2'].value, datetime(2026,10,14,22))
        self.assertIsNone(entregas['D2'].value.tzinfo)
        self.assertEqual(entregas['D2'].number_format, FORMATO_FECHA_HORA)
        self.assertIsNone(entregas['E2'].value)
        mantenimiento = self.excel('mantenimientos').active
        self.assertTrue(mantenimiento['B2'].is_date)
        self.assertEqual(mantenimiento['B2'].number_format, FORMATO_FECHA)

    def test_costos_numericos_total_filtrado_en_negrita_y_fuera_del_filtro(self):
        hoja = self.excel('mantenimientos', {
            'unidad': self.unidad.pk, 'desde': '2026-10-10', 'hasta': '2026-10-15',
        }).active
        self.assertEqual(hoja['F2'].data_type, 'n')
        self.assertEqual(hoja['F2'].number_format, FORMATO_COSTO)
        self.assertEqual(Decimal(str(hoja['F2'].value)), Decimal('10.10'))
        self.assertEqual(Decimal(str(hoja['F3'].value)), Decimal('20.20'))
        self.assertEqual(hoja['A4'].value, 'Total de costos')
        self.assertEqual(Decimal(str(hoja['F4'].value)), Decimal('30.30'))
        self.assertTrue(hoja['A4'].font.bold and hoja['F4'].font.bold)
        self.assertEqual(hoja['F4'].number_format, FORMATO_COSTO)
        self.assertEqual(hoja.auto_filter.ref, 'A1:F3')

    def test_valores_que_exceden_precision_excel_se_conservan_exactos_como_texto(self):
        Mantenimiento.objects.create(unidad=self.unidad, fecha=date(2026,10,10), tipo='Preventivo',
            costo=Decimal('9999999999999999.99'))
        hoja = self.excel('mantenimientos', {'unidad': self.unidad.pk}).active
        costos = [hoja.cell(fila,6) for fila in range(2,hoja.max_row)]
        self.assertTrue(any(c.value == '9999999999999999.99' and c.data_type == 's' for c in costos))
        self.assertEqual(hoja.cell(hoja.max_row,6).value, '10000000000000030.29')
        self.assertEqual(hoja.cell(hoja.max_row,6).data_type, 's')

    def test_formulas_y_errores_introducidos_por_usuario_son_texto_literal(self):
        self.unidad.maquinaria.codigo = '=1+1'
        self.unidad.maquinaria.nombre = '+SUM(1,2)'
        self.unidad.maquinaria.save()
        self.unidad.numero_serie = '-2+3'
        self.unidad.ubicacion_actual = '@SUM(1,2)'
        self.unidad.save()
        self.cliente_a.first_name = '=HYPERLINK("x")'
        self.cliente_a.save()
        self.admin.first_name = '＠SUM(1,1)'
        self.admin.save()
        self.m1.descripcion = '#REF!'
        self.m1.save()
        for tipo in self.tipos:
            hoja = self.excel(tipo).active
            self.assertFalse(any(c.data_type in ('f','e') for fila in hoja for c in fila))
            self.assertFalse(any(c.hyperlink for fila in hoja for c in fila))
        hoja = self.excel('maquinaria', {'q': '-2+3'}).active
        self.assertEqual([hoja[c].value for c in ('A2','B2','C2','E2')], ['=1+1','+SUM(1,2)','-2+3','@SUM(1,2)'])
        for c in ('A2','B2','C2','E2'):
            self.assertEqual(hoja[c].data_type, 's')
        hoja = self.excel('mantenimientos', {'unidad': self.unidad.pk,'tipo': 'Preventivo'}).active
        self.assertEqual(hoja['D2'].value, '#REF!')
        self.assertEqual(hoja['D2'].data_type, 's')
        self.m1.refresh_from_db()
        self.assertEqual(self.m1.descripcion, '#REF!')

    def test_vacios_generan_archivos_validos_con_encabezados_y_total_cero(self):
        filtros = {'maquinaria': {'q': 'No existe'}, 'solicitudes': {'desde': '2030-01-01'},
            'entregas': {'desde': '2030-01-01'}, 'mantenimientos': {'desde': '2030-01-01'}}
        for tipo, datos in filtros.items():
            hoja = self.excel(tipo, datos).active
            self.assertEqual(hoja.max_row, 2 if tipo == 'mantenimientos' else 1)
            self.assertTrue(all(c.font.bold for c in hoja[1]))
            self.assertEqual(hoja.freeze_panes, 'A2')
            if tipo == 'mantenimientos':
                self.assertEqual(hoja['F2'].value, 0)
                self.assertEqual(hoja['F2'].number_format, FORMATO_COSTO)
                self.assertEqual(hoja.auto_filter.ref, 'A1:F1')

    def test_tildes_comillas_y_saltos_con_ajuste_de_texto(self):
        hoja = self.excel('mantenimientos', {'unidad': self.unidad.pk, 'tipo': 'Preventivo'}).active
        self.assertEqual(hoja['D2'].value, self.m1.descripcion)
        self.assertTrue(hoja['D2'].alignment.wrap_text)
        self.assertGreater(hoja.row_dimensions[2].height, 20)
        solicitudes = self.excel('solicitudes', {'cliente': self.cliente_a.pk}).active
        self.assertIn('María, "Ñ"', solicitudes['B2'].value)
        self.assertIn('Excavadora, "Ágil"', solicitudes['C2'].value)

    def test_descargas_excel_no_cambian_registros_de_la_aplicacion(self):
        modelos = (Unidad,SolicitudAlquiler,Mantenimiento)
        antes = [list(m.objects.order_by('pk').values()) for m in modelos]
        for tipo in self.tipos:
            self.excel(tipo)
        self.assertEqual(antes, [list(m.objects.order_by('pk').values()) for m in modelos])


class ExcelLiteralTests(SimpleTestCase):
    def test_todos_los_prefijos_se_escriben_como_cadenas_sin_formulas_xml(self):
        textos = ('=1+1','+SUM(1,2)','-1+2','@SUM(1,2)',' =1','\t=1','\n=1','\r=1','\r\n=1',
            '\ufeff＝1','\u200b＋1','\u202e＠SUM(1)','#REF!','0000000000000123')
        respuesta = exportar_excel('maquinaria','Maquinaria',('Texto',),[(t,) for t in textos],None)
        hoja = load_workbook(BytesIO(respuesta.content)).active
        for celda, texto in zip(hoja['A'][1:],textos):
            self.assertEqual(celda.value, texto)
            self.assertEqual(celda.data_type,'s')
            self.assertEqual(celda.number_format,'@')
        with ZipFile(BytesIO(respuesta.content)) as archivo:
            self.assertNotIn(b'<f>', archivo.read('xl/worksheets/sheet1.xml'))
            self.assertFalse(any(n.startswith('xl/externalLinks/') for n in archivo.namelist()))

    def test_caracteres_prohibidos_en_xml_no_corrompen_el_libro(self):
        respuesta = exportar_excel('maquinaria','Maquinaria',('Texto',),[('Antes\x00después\uffff',)],None)
        hoja = load_workbook(BytesIO(respuesta.content)).active
        self.assertEqual(hoja['A2'].value, 'Antes\ufffddespués\ufffd')

    def test_fechas_anteriores_a_1900_se_conservan_como_texto_iso(self):
        respuesta = exportar_excel('mantenimientos','Mantenimientos',('Unidad','Fecha'),[('Unidad','1899-12-01')],None)
        celda = load_workbook(BytesIO(respuesta.content)).active['B2']
        self.assertEqual(celda.value, '1899-12-01')
        self.assertEqual(celda.data_type,'s')
