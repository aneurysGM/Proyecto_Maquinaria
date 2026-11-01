# HU-10: generar reportes

Sprint 4. Revisión del 30 de octubre de 2026, America/Santo_Domingo.
Se conserva el código local anterior y toda la funcionalidad de HU-09. No se
crean modelos, migraciones ni tablas nuevas y no se ejecutan procedimientos legacy.

## Acceso y reportes

La sección **Reportes** está en el menú y panel del Administrador activo
(`is_superuser`). `is_staff` por sí solo no habilita acceso. Cliente y Técnico
reciben HTTP 403 tanto en las pantallas como en las descargas por URL directa.
Las sesiones anónimas se redirigen al login y las cuentas inactivas no acceden.

| Reporte | Ruta | Contenido y filtros |
| --- | --- | --- |
| Maquinaria | `/reportes/maquinaria/` | Código, nombre, serie, estado y ubicación; búsqueda y estado. |
| Solicitudes | `/reportes/solicitudes/` | Solicitud, Cliente, unidad, fechas solicitadas y estado; estado, Cliente y período. |
| Salidas y retornos | `/reportes/entregas/` | Solicitud, Cliente, unidad, fechas, responsables y situación; fecha de salida y situación pendiente/devuelta. |
| Mantenimientos | `/reportes/mantenimientos/` | Unidad, fecha, tipo, descripción, responsable y costo; período, unidad y tipo, con total de costos. |

`/reportes/` ofrece los cuatro accesos. La unidad se identifica por código, nombre,
número de serie e ID; no se mezclan unidades del mismo catálogo. Los responsables
se muestran con nombre y username. Los datos antiguos sin responsable se identifican
como «No registrado (registro anterior)», sin inventar una cuenta.

Las consultas incluyen registros históricos y unidades inactivas; no se ocultan
movimientos porque cambió la disponibilidad, el rol o la actividad de una cuenta.
El selector de Cliente usa las cuentas vinculadas a solicitudes existentes,
incluidas las que ya no tengan el grupo Cliente. No cambia las reglas del catálogo
normal, que sigue mostrando sus unidades activas.

## Significado de los filtros

- **Maquinaria:** `q` busca por código, nombre, serie o ubicación. `estado` usa los
  valores existentes Disponible, Alquilado, Mantenimiento y Baja, con sus etiquetas.
- **Solicitudes:** `estado` y `cliente` se combinan con `desde` y `hasta`. El período
  se interpreta como intersección inclusiva: incluye solicitudes cuyo intervalo
  solicitado coincida total o parcialmente con el rango consultado.
- **Salidas/retornos:** solo incluye solicitudes con salida registrada. `situacion`
  admite `pendiente` o `devuelta`; sin valor incluye ambas. El período corresponde
  a la fecha de **salida**, con días completos en America/Santo_Domingo. El límite
  final incluye hasta el último instante del día indicado, no solo su medianoche.
- **Mantenimientos:** `desde` y `hasta` filtran su fecha inclusivamente; `unidad`
  y `tipo` se combinan con ese período. Se mantienen costos cero y registros legacy.
- Las fechas usan `AAAA-MM-DD`. Puede indicarse solo un extremo del período.
  Fechas inexistentes, períodos invertidos, estados/tipos no válidos e IDs no válidos
  producen HTTP 400 con errores visibles. Se conservan los filtros introducidos y
  no se muestra una consulta general ni se entrega un XLSX por error.

## Pantalla y descarga Excel (.xlsx)

Los formularios envían GET. **Consultar** muestra todos los resultados filtrados,
sin paginación. La única descarga es **Descargar Excel (.xlsx)**; su enlace conserva
los parámetros de la consulta mostrada y añade `formato=xlsx`. Editar el formulario
sin consultar no cambia el enlace de los resultados anteriores. Pantalla y descarga
comparten validación, consultas, orden y columnas.

Los datos se leen en cada petición. Si se registran movimientos entre consulta y
descarga, el archivo refleja los datos vigentes con los mismos filtros. No se
almacenan copias permanentes de reportes en la base.

Sin coincidencias, la pantalla muestra **Sin resultados** y permite descargar un
libro válido con sus encabezados. Mantenimiento incluye además el total **0.00**.
Los filtros inválidos no ofrecen descarga ni resultados sin filtrar.

## Enlaces antiguos de descarga

La exportación CSV fue retirada de los cuatro reportes, incluidos botones,
serializadores y protección de texto utilizados exclusivamente por ese formato.
Una petición de Administrador con `?formato=csv` devuelve **HTTP 410**, una página
HTML con el mensaje «La descarga CSV fue retirada. Utiliza Descargar Excel (.xlsx).»
y un enlace para volver al reporte conservando sus filtros. No consulta los resultados,
no genera archivo ni incluye `Content-Disposition`. Esto también se aplica si
los filtros de esa petición son inválidos; al volver se pueden corregir.

La comprobación de permisos sigue siendo anterior: Cliente, Técnico y otras
cuentas sin permiso reciben 403, incluso por estas URL antiguas. Los formatos
desconocidos siguen devolviendo 400.

## Formato del libro

Se genera un libro Office Open XML real con `openpyxl==3.1.5`, usando las filas ya
filtradas del constructor compartido, sin consultas adicionales.

- Una hoja por reporte, cada dato en su columna y encabezados en negrita.
- Anchos calculados, texto largo ajustado y alturas de fila adaptadas. Primera fila
  inmovilizada en `A2` y autofiltros en los encabezados.
- Códigos, series, identificadores y demás textos como cadenas explícitas con
  formato Texto. Se conservan ceros iniciales y números largos.
- Fechas nativas `dd/mm/yyyy`; salida y retorno con hora local de Santo Domingo y
  formato `dd/mm/yyyy hh:mm:ss`. Excel no almacena zona horaria.
- Costos numéricos `#,##0.00`. La última fila de mantenimiento contiene el total
  filtrado en negrita y fuera del autofiltro. Es una instantánea de los filtros web;
  no se recalcula al aplicar otros filtros dentro de Excel.
- Textos que empiezan por `=`, `+`, `-`, `@`, espacios o controles previos se guardan
  literalmente como cadenas, sin fórmulas ni apóstrofos añadidos. Valores como
  `#REF!` también son texto. Los datos guardados no se modifican.
- Resultados vacíos producen un libro válido con encabezados, filtros e
  inmovilización; mantenimiento añade su total numérico cero.

Un costo o total que exceda 15 cifras significativas se conserva como texto exacto
para evitar pérdida de precisión. Las fechas anteriores a 1900 se guardan como texto
ISO. Los controles que XML no admite se representan con `�`; tildes, comillas,
tabulaciones y saltos de línea válidos se conservan. El HTML mantiene el escape de
Django.

La respuesta usa `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
y `attachment; filename="reporte_<tipo>.xlsx"`, con cabeceras para evitar caché.
Los permisos y validaciones también protegen las descargas por URL directa.

Para instalar las dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Total y alcance

El total suma exclusivamente `Mantenimiento.costo` de las filas realmente obtenidas
tras aplicar los filtros. Se calcula con Decimal, sin float ni una segunda consulta
que pudiera leer otros registros.

No hay reportes de ingresos, pagos, mora, depósitos, ITBIS ni importes de alquiler.
Las tarifas del catálogo no se usan para inventar importes. HU-09 conserva fechas,
responsables, transacciones, restricciones y cambios de estado. Esta retirada no
modifica esquema, migraciones ni datos de SQL Server.

## Código y comprobaciones

- `usuarios/forms_reportes.py`: filtros y selectores históricos.
- `usuarios/reportes.py`: permisos, consultas compartidas y rechazo del formato retirado.
- `usuarios/exportacion_excel.py`: tipos, formatos y protección de cadenas del XLSX;
  conservado sin cambios en esta retirada.
- `usuarios/templates/usuarios/reportes_indice.html` y `reporte.html`: filtros,
  resultados, vacíos, errores y descarga Excel.
- `usuarios/tests_reportes.py`: permisos, filtros, totales, lectura y enlaces antiguos.
- `usuarios/tests_reportes_excel.py`: cuatro libros, equivalencia con pantalla,
  contenido, tipos, formatos, textos literales y resultados vacíos.

Ejecutar en una base temporal de SQL Server:

```powershell
.\.venv\Scripts\python.exe -B scripts/verificar_proyecto.py
```

Las 33 pruebas específicas de reportes y XLSX pasaron. Registro:
`tmp/verificaciones/django_20261031T030354Z_aa9851.log`.
La suite completa pasó **139 pruebas en SQL Server**; `check`, la detección de
cambios de modelos y la comprobación de migraciones pendientes no encontraron problemas.
Registro completo: `tmp/verificaciones/django_20261031T030533Z_dc9460.log`.
Las bases de pruebas temporales se eliminaron. Se comprobaron también los cuatro
reportes con datos reales, en solo lectura: pantalla y XLSX con HTTP 200, libros
reabiertos sin errores y peticiones antiguas con HTTP 410 sin archivo.
Las 26 tablas conservan columnas, cantidades y huellas de sus datos iniciales.
El generador XLSX, los filtros, HU-09 y las migraciones permanecen intactos.
La comprobación de integridad se documenta en
`evidencias_locales/hu10_solo_excel_20261031T030247Z/verificacion_final.json`.
La copia recuperable del código anterior está en
`respaldos_locales/hu10_solo_excel_20261031T030247Z/codigo_antes.zip`.

## Prueba manual

1. Iniciar sesión como Administrador y abrir **Reportes** desde menú o panel.
   Los cuatro reportes deben ofrecer únicamente **Descargar Excel (.xlsx)**.
2. En maquinaria, combinar búsqueda y estado, pulsar **Consultar** y descargar.
   Comparar filas y columnas con la pantalla; comprobar códigos y series como texto.
3. En solicitudes, combinar Cliente, estado y período. Comprobar fechas nativas y
   que el XLSX contiene las solicitudes mostradas.
4. En salidas y retornos, combinar fecha de salida y situación pendiente/devuelta.
   Comprobar horas de Santo Domingo, responsables y retornos pendientes vacíos.
5. En mantenimientos, combinar período, unidad y tipo. Comparar registros y total
   con pantalla; el total debe estar fuera del autofiltro y en negrita.
6. En los cuatro, probar una consulta vacía y una fecha o filtro inválido. Vacíos
   permiten un XLSX válido; errores muestran HTTP 400 sin descargar.
7. Abrir cada XLSX en Excel: revisar columnas, negrita, anchos, filtros, encabezado
   inmovilizado, tildes y saltos de línea. Los textos de fórmula deben seguir siendo texto.
8. Añadir `formato=csv` a cada URL filtrada. Debe mostrarse el mensaje de formato
   retirado, sin archivo; **Volver al reporte conservando los filtros** permite usar Excel.
9. Con Cliente y Técnico, abrir las cuatro rutas y sus URL con `formato=xlsx` o
   `formato=csv`: deben responder 403, sin acceso en su menú o panel.
