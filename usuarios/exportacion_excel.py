"""XLSX de las filas ya filtradas del reporte, sin consultas adicionales."""
import os
import re
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from math import ceil
from zipfile import ZipFile

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
FORMATO_FECHA = 'dd/mm/yyyy'
FORMATO_FECHA_HORA = 'dd/mm/yyyy hh:mm:ss'
FORMATO_COSTO = '#,##0.00'
FECHAS = {'solicitudes': {3, 4}, 'mantenimientos': {1}}
FECHAS_HORAS = {'entregas': {3, 4}}
IDENTIFICADORES = {'solicitudes': {0}, 'entregas': {0}}
# XML 1.0 no admite estos caracteres, aunque puedan existir en datos legacy.
CONTROLES_XML = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]')


def _valor_excel(tipo, columna, valor):
    if valor is None or valor == '':
        return None
    if columna in FECHAS.get(tipo, ()):
        fecha = date.fromisoformat(valor)
        # Excel no representa correctamente fechas anteriores a 1900.
        return fecha if fecha >= date(1900, 1, 1) else valor
    if columna in FECHAS_HORAS.get(tipo, ()):
        # El constructor compartido ya convirtió la fecha a Santo Domingo.
        # XLSX almacena fecha/hora local sin información de zona horaria.
        fecha = datetime.fromisoformat(valor)
        return fecha if fecha.date() >= date(1900, 1, 1) else valor
    if columna in IDENTIFICADORES.get(tipo, ()):
        return str(valor)
    if isinstance(valor, Decimal) and len(valor.normalize().as_tuple().digits) > 15:
        # Excel admite 15 dígitos significativos: conservar el valor exacto como
        # texto en los casos que perderían cifras o centavos al convertirlos.
        return format(valor, '.2f')
    return valor


def _escribir(celda, valor):
    if isinstance(valor, str):
        celda.value = CONTROLES_XML.sub('\ufffd', valor)
        # La asignación normal interpreta '=' como fórmula y '#REF!' como error.
        # Forzar siempre el tipo de cadena preserva el texto y los ceros iniciales.
        celda.data_type = 's'
        celda.number_format = '@'
    else:
        celda.value = valor
        if isinstance(valor, datetime):
            celda.number_format = FORMATO_FECHA_HORA
        elif isinstance(valor, date):
            celda.number_format = FORMATO_FECHA
        elif isinstance(valor, Decimal):
            celda.number_format = FORMATO_COSTO
    celda.font = Font(name='Calibri', size=11)
    celda.alignment = Alignment(vertical='top', wrap_text=True)


def _ajustar_dimensiones(hoja, numero_columnas):
    for columna in range(1, numero_columnas + 1):
        celdas = [hoja.cell(fila, columna) for fila in range(1, hoja.max_row + 1)]
        anchura = 12
        for celda in celdas:
            valor = celda.value
            if isinstance(valor, datetime):
                longitud = 19
            elif isinstance(valor, date):
                longitud = 10
            elif isinstance(valor, Decimal):
                longitud = len(format(valor, ',.2f'))
            else:
                longitud = max((len(linea) for linea in str(valor or '').splitlines()), default=0)
            anchura = max(anchura, longitud + 3)
        hoja.column_dimensions[get_column_letter(columna)].width = min(anchura, 60)
    hoja.row_dimensions[1].height = 32
    for fila in range(2, hoja.max_row + 1):
        lineas = 1
        for columna in range(1, numero_columnas + 1):
            celda = hoja.cell(fila, columna)
            if not isinstance(celda.value, str):
                continue
            ancho = hoja.column_dimensions[get_column_letter(columna)].width - 2
            texto = celda.value.replace('\r\n', '\n').replace('\r', '\n')
            lineas = max(lineas, sum(max(1, ceil(len(linea) / ancho)) for linea in texto.split('\n')))
        hoja.row_dimensions[fila].height = min(409, lineas * 15 + 5)


def _conservar_retornos_xml(contenido):
    """Evitar que XML normalice CR a LF al volver a abrir cadenas literales.

    El serializador estándar puede convertir LF a CRLF en Windows al escribir
    su archivo temporal. Se deshace esa traducción antes de escapar CR como
    entidad XML. Los serializadores que ya usan entidades no requieren cambios.
    """
    with ZipFile(BytesIO(contenido)) as original:
        hojas = {
            nombre: original.read(nombre) for nombre in original.namelist()
            if nombre.startswith('xl/worksheets/') and nombre.endswith('.xml')
        }
        if not any(b'\r' in hoja for hoja in hojas.values()):
            return contenido
        with BytesIO() as salida:
            with ZipFile(salida, 'w') as nuevo:
                for info in original.infolist():
                    datos = hojas.get(info.filename)
                    if datos is None:
                        datos = original.read(info.filename)
                    else:
                        if os.linesep == '\r\n':
                            datos = datos.replace(b'\r\n', b'\n')
                        datos = datos.replace(b'\r', b'&#13;')
                    nuevo.writestr(info, datos)
            return salida.getvalue()


def exportar_excel(tipo, titulo, encabezados, filas, total):
    libro = Workbook()
    hoja = libro.active
    hoja.title = titulo
    hoja.freeze_panes = 'A2'
    for columna, encabezado in enumerate(encabezados, 1):
        celda = hoja.cell(1, columna)
        _escribir(celda, encabezado)
        celda.font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        celda.fill = PatternFill('solid', fgColor='145A86')
    for numero_fila, fila in enumerate(filas, 2):
        for indice, valor in enumerate(fila):
            _escribir(hoja.cell(numero_fila, indice + 1), _valor_excel(tipo, indice, valor))
    ultima_columna = get_column_letter(len(encabezados))
    # El total queda fuera del rango filtrable, incluso con cero registros.
    hoja.auto_filter.ref = f'A1:{ultima_columna}{len(filas) + 1}'
    if total is not None:
        numero_fila = len(filas) + 2
        _escribir(hoja.cell(numero_fila, 1), 'Total de costos')
        _escribir(hoja.cell(numero_fila, len(encabezados)), _valor_excel(tipo, len(encabezados) - 1, total))
        for celda in hoja[numero_fila]:
            celda.font = Font(name='Calibri', size=11, bold=True)
            celda.fill = PatternFill('solid', fgColor='E8F3EC')
    _ajustar_dimensiones(hoja, len(encabezados))
    with BytesIO() as contenido:
        libro.save(contenido)
        respuesta = HttpResponse(_conservar_retornos_xml(contenido.getvalue()), content_type=MIME_XLSX)
    libro.close()
    respuesta['Content-Disposition'] = f'attachment; filename="reporte_{tipo}.xlsx"'
    return respuesta
