# Organización y limpieza del proyecto

Revisión del 30 de octubre de 2026, zona America/Santo_Domingo. Se respetaron los
cambios locales anteriores; no se hizo commit ni publicación en GitHub.

## Estructura

| Ubicación | Contenido |
| --- | --- |
| `config/`, `usuarios/`, `manage.py` | Aplicación Django; modelos, formularios, vistas, plantillas, estáticos y pruebas. |
| `usuarios/migrations/` | Toda la cadena histórica, incluida la retirada de operadores; sin cambios en esta limpieza. |
| `docs/` | Documentación vigente y antecedentes identificados como tales. |
| `sql/` | Scripts SQL mantenidos y documentados. |
| `sql/legacy/` | Copias originales SQL/TXT locales, distintas y sin validar completamente; excluidas de Git. |
| `scripts/` | Configuración y utilidades compartidas de verificación, exportación y rasterización. |
| `scripts/documentos/` | Fuentes editables históricas de documentos antes guardadas en `tmp`. |
| `output/` | Documentos finales, editables, versiones y evidencias documentales locales. |
| `sprint3_work/` | Fuentes y revisiones históricas de Sprint 3, separadas de `output`. |
| `evidencias_locales/` | Logs, inventarios, resultados y copias iniciales de las sesiones de integración. |
| `respaldos_locales/` | Respaldos originales y copia recuperable de la limpieza; fuera de las carpetas limpiadas. |
| `tmp/verificaciones/` | Nuevos logs de comprobación y temporales reproducibles. |

`output`, `scripts` y `sprint3_work` **no se fusionaron**. No se modifica la
configuración privada, el entorno virtual, los datos locales ni las dependencias
externas del runtime. Se mantienen las reglas anteriores de exclusión y se
añaden las de respaldos, evidencias y SQL legacy.

## Retirado del árbol de trabajo

Se compararon SHA-256 de archivos completos y las partes internas de los paquetes
DOCX/PPTX/XLSX. Las fechas y nombres no se usaron como prueba de duplicación.
Del inventario inicial se retiraron **246 archivos**, unos **16,1 MiB**:

| Tipo | Cantidad | Justificación |
| --- | --- | --- |
| Cachés Python | 44 | Regenerables; no son código ni pruebas. |
| PNG de revisión | 168 | Vistas generadas; se conservan el PDF o editable fuente y sus generadores. |
| Copias exactas | 10 | Un DOCX, un PPTX intermedio, cinco PNG extraídos y tres auxiliares de transferencia. |
| Exportadores Word duplicados | 2 | Sustituidos por una implementación compartida. |
| Scripts puntuales de sesiones terminadas | 21 | Aplicaciones antiguas de migraciones, cambios y comprobaciones ya cubiertas por los comandos y pruebas permanentes; fuente íntegra archivada. |
| Bandera de una revisión UI finalizada | 1 | Control temporal sin función en la aplicación. |

Se conserva el DOCX `sprint3_work/Software_alquiler_maquinarias_pesadas.docx` en
lugar de su copia idéntica con sufijo `_reparado`. Se conserva el PPTX final
`output/preview_samples/files/Habitos_de_estudio.pptx` en lugar de su copia exacta
`build/candidate.pptx`. Los generadores pueden recrear esos intermediarios.

Las imágenes de diagramas originales permanecen en
`output/documentos/Diagramas_originales/`; sus generadores ya usan esa ubicación.
Los auxiliares de transferencia compartidos permanecen en
`output/preview_samples/transfer_helpers/`.

El `node_modules` de las muestras resultó ser una unión de Windows hacia una
caché externa. Se conservó el enlace porque lo utiliza `build.mjs`, sin recorrerlo
para limpiar ni borrar su destino. Sus dependencias no se contabilizan como
archivos propios del proyecto ni se incluyen en la copia de limpieza.

## Unificado y reorganizado

- **Pruebas:** los lanzadores puntuales se sustituyen por
  `scripts/verificar_proyecto.py`. Admite la suite completa o etiquetas Django,
  asigna una base temporal única y guarda logs. Las pruebas siguen en
  `usuarios/tests*.py`; no se cambió su descubrimiento.
- **Word:** `scripts/exportar_word.ps1` concentra exportación y normalización.
  Los accesos de `sprint3_work` y `output/sprint3_update` delegan en él.
- **PNG de revisión:** `scripts/renderizar_pdf.py` concentra rasterización y
  hoja de contacto opcional. Los accesos de Sprint 3 delegan en él. Si cambia
  un DOCX, primero se exporta su PDF; ya no se usa un renderizador de una versión
  antigua del plugin.
- **Fuentes documentales:** seis generadores pasan de `tmp/diagramas` y
  `tmp/pdfs` a `scripts/documentos`, con rutas y referencias actualizadas.
  No se juntan generadores de documentos con contenido diferente.
- **Evidencias:** los resultados históricos se trasladan a `evidencias_locales`.
  Los respaldos originales del 20 de octubre pasan a
  `respaldos_locales/20261020-211605/`. Se actualizaron sus referencias en docs.
- **SQL/TXT originales:** pasan de la raíz a `sql/legacy` sin cambiar bytes.
  No son dependencias de arranque Django y las referencias puntuales antiguas
  quedan documentadas en el archivo de limpieza. Se conservan las tres consultas
  y scripts mantenidos de `sql/`, sin ejecutarlos.

En total se trasladaron **51 archivos** conservando su contenido; los cambios de
rutas de los generadores y de los accesos compartidos se registran por separado.
Cada carpeta de resultados tiene un README local y las utilidades se explican en
[scripts/README.md](../scripts/README.md).

## Copia recuperable

Antes de retirar archivos se creó y verificó:

```text
respaldos_locales/limpieza_20261030T232744Z/proyecto_antes.zip
```

El ZIP contiene los 419 archivos regulares del inventario inicial, incluidos
los archivos ignorados por Git, las fuentes antiguas y la configuración privada.
No incluye `.git`, `.venv` ni el contenido del enlace externo de Node. Ocupa unos
30,6 MiB; se conserva como respaldo, por lo que el ahorro del árbol activo no
equivale a una reducción neta de espacio en disco.

SHA-256 del ZIP:

```text
fb354415a3e1cb36ded4e4b130943acc5d1e0bb0910d93f31c8f3600c3d87b90
```

La misma carpeta contiene `inventario_antes.json`, `diff_inicial.patch`,
`status_inicial.txt`, `acciones.json`, `resumen.json` y `verificacion_final.json`.
El inventario registra las rutas y hashes; el manifiesto de acciones explica cada
baja y traslado. Para recuperar algo, extraer primero los archivos seleccionados
a una carpeta nueva y revisar sus diferencias antes de sustituir archivos activos.
El directorio completo de respaldos permanece excluido de Git.

## Conservado por duda o por ser una versión distinta

- Todos los DOCX distintos de casos de uso y Sprint 3, incluidos `source.docx`,
  `preview_input.docx` y `draft.docx`; sus paquetes internos difieren.
- Los PDF `sprint3_work/review.pdf` y `reparado_review.pdf`, y la imagen
  `selected.jpeg`: no se pudo justificar descartar una revisión o evidencia.
- Los cuatro PDF de `output/antecedentes/diagramas`: `restaurado.pdf`,
  `solo_fuente.pdf`, `solo_fuente_final.pdf` y `verificacion.pdf`. Sus contenidos
  binarios difieren, aunque algunos tengan el mismo número de páginas.
- `output/evidencias_historicas/pdf/`: capturas únicas de revisiones anteriores
  e intermedio `client_pages.pdf`, cuya utilidad actual no está completamente resuelta.
- `output/preview_samples`: muestras de gastos y estudio ajenas al flujo Django,
  con editables únicos, fuentes, validaciones y auxiliares. Algunas fuentes dependen
  del entorno original de autoría; no se borraron por parecer ajenas al negocio.
- `sql/legacy/AlquilerEquipos_.sql` y `base_recuperada_.txt`: hashes distintos;
  el TXT declara recuperación desde PDF y validación pendiente. No se ejecutaron.

## Comprobaciones realizadas

- `check`: sin incidencias; `makemigrations --check --dry-run`: sin cambios;
  `migrate --check`: sin migraciones pendientes. No se aplicaron migraciones en
  la base de trabajo ni se ejecutaron los scripts antiguos de escritura SQL.
- **80 pruebas aprobadas en SQL Server**, sin omisiones, en la base temporal
  `test_verif_84b4960e73`, eliminada al finalizar. Solo las pruebas usan una
  base temporal; los datos de la base de trabajo permanecen fuera de ese flujo.
- Registro en `tmp/verificaciones/django_20261030T233525Z_ed278f.log`.
- **57 archivos protegidos** comparados con sus hashes iniciales: aplicación,
  pruebas, migraciones, configuración, requisitos, SQLite y datos locales intactos.
- **31 entregables y fuentes** verificados contra sus hashes originales, en
  su ubicación conservada o la de su copia exacta.
- Sintaxis de 67 archivos Python y de los cuatro exportadores/accesos PowerShell
  comprobada. El renderizador compartido produjo correctamente un PNG temporal
  de 255 × 330, retirado después de la comprobación.
- No se ejecutó Word ni se regeneraron los DOCX finales: se comprobó su conservación
  por hash. `git diff --check` sin errores. No se publicó nada en GitHub.
