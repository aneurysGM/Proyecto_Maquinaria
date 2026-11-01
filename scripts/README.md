# Utilidades del proyecto

Ejecutar desde la raíz del repositorio. Las utilidades no se importan desde la
aplicación Django. `configurar_desarrollo.py` conserva su comportamiento anterior.

| Archivo | Uso |
| --- | --- |
| `configurar_desarrollo.py` | Crear o completar la configuración privada sin sustituir secretos existentes. |
| `verificar_proyecto.py` | Comprobar Django, coherencia y estado de migraciones; ejecutar las pruebas en una base temporal única. |
| `exportar_word.ps1` | Exportar DOCX a PDF mediante Word; normalizar una copia solo si se indica `-NormalizadoPath`. |
| `renderizar_pdf.py` | Generar PNG de revisión desde un PDF con Poppler; hoja de contacto opcional con Pillow. |
| `documentos/` | Fuentes históricas de documentos y diagramas; no ejecutarlas como parte del arranque de la aplicación. |

## Verificar Django

```powershell
.\.venv\Scripts\python.exe -B scripts/verificar_proyecto.py
.\.venv\Scripts\python.exe -B scripts/verificar_proyecto.py usuarios.tests_solicitudes
.\.venv\Scripts\python.exe -B scripts/verificar_proyecto.py --solo-comprobaciones
```

La utilidad sustituye los anteriores lanzadores puntuales de `tmp`. Consulta
`migrate --check` en la base de trabajo, sin aplicar migraciones. Para las pruebas
asigna un nombre `test_verif_<identificador>` y Django crea y elimina esa base
temporal. Los resultados se guardan en `tmp/verificaciones/` y se muestra la ruta
del log. Los fallos devuelven un código de salida distinto de cero. La opción
`--solo-comprobaciones` no crea una base de pruebas.

La suite puede crear respaldos de la base temporal al verificar la migración de
retirada; permanecen en el directorio de respaldo de SQL Server. No se toca la
base de trabajo desde las pruebas. Se conservan todos los módulos de pruebas en
`usuarios/tests*.py`; no se cambió su descubrimiento.

Para crear y verificar un respaldo completo de la base SQL Server configurada,
antes de aplicar migraciones:

```powershell
.\.venv\Scripts\python.exe manage.py respaldar_sqlserver --motivo pre_hu09
```

El comando usa `COPY_ONLY, CHECKSUM` y `RESTORE VERIFYONLY WITH CHECKSUM,
STOP_ON_ERROR`; imprime la ruta del archivo y falla si no se puede verificar.
No aplica migraciones ni modifica datos de negocio. Necesita permisos de respaldo
y verificación y un directorio de respaldo configurado en la instancia.

## Exportar y revisar documentos

```powershell
powershell -NoProfile -File scripts/exportar_word.ps1 -DocxPath ruta/documento.docx -PdfPath ruta/revision.pdf
.\.venv\Scripts\python.exe -B scripts/renderizar_pdf.py ruta/revision.pdf --output-dir tmp/revision --dpi 120
```

La exportación requiere Microsoft Word instalado y no guarda cambios en el DOCX
de entrada. `-NormalizadoPath ruta/copia.docx` conserva una copia normalizada en
otra ruta. La rasterización requiere `pdftoppm` de Poppler en PATH, en
`POPPLER_BIN`, en la caché local instalada o en la carpeta indicada mediante
`--poppler-bin`. `--primera` y `--ultima` limitan el intervalo de páginas.
`--contacto` crea además una hoja de contacto y requiere Pillow.

Los accesos `renderizar_revision.py` de las dos carpetas Sprint 3 delegan en el
renderizador común y usan los PDF conservados. Si se modifica su DOCX, primero
hay que exportar el PDF con `exportar_word.ps1`. `sprint3_work/qa.py` usa la misma
implementación; sus exportadores y `output/sprint3_update/normalize.ps1` delegan
en el exportador Word común. No dependen de una versión antigua del plugin.

## Fuentes históricas

`documentos/` conserva los generadores que estaban en `tmp/diagramas` y `tmp/pdfs`.
Se actualizaron las rutas para que localicen la raíz del proyecto desde su nueva
ubicación y los PNG originales de `output/documentos/Diagramas_originales`.
Requieren bibliotecas de autoría como python-docx, ReportLab y pypdf según el
archivo, además de recursos locales o programas externos que indique su código.
No se añadieron estas dependencias a los requisitos de Django.

Estos generadores describen entregas anteriores y pueden reemplazar sus archivos
de salida al ejecutarse. Se conservaron como fuentes editables; la limpieza no
los ejecutó ni actualizó el contenido de los documentos finales.
