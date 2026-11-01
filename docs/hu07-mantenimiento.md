# HU-07: implementación y evidencias del Sprint 3

> Antecedente del 27 de octubre de 2026. Desde el 30 de octubre los roles
> vigentes son Administrador, Cliente y Técnico de mantenimiento. HU-05 y HU-06
> están retiradas, sin reemplazos redactados. Las menciones a Supervisor,
> operadores y futuras publicaciones que siguen describen aquella entrega;
> no son instrucciones vigentes. Consultar [cuentas y roles](cuentas-y-roles.md)
> y [retirada de operadores](retirada-operadores.md). No se publica en GitHub
> durante esta revisión.

Fecha: 27 de octubre de 2026, zona America/Santo_Domingo.
Rama local: `feat/sprint3-hu07-mantenimiento`, basada en `origin/main` (`e01dd1a`).
El PR #3 ya integra HU-04 y HU-05. Esta entrega se prepara para publicación
mediante un pull request hacia `main`, sin merge. HU-06 y la actualización del
documento Word siguen pendientes.

## Archivos

| Archivos | Cambio |
| --- | --- |
| `usuarios/models.py` | Mantenimiento sobre tabla legacy, relaciones protegidas, validaciones y restricciones. |
| `usuarios/migrations/0007_integrar_mantenimiento.py` | Crear o adoptar tabla sin sustituir datos; técnico, relaciones, restricciones y grupo. |
| `usuarios/forms.py` | Unidad física identificada por catálogo, serie e ID; validaciones y transacción con bloqueo/relectura. |
| `usuarios/roles.py` | Grupo Técnico y permisos de mantenimiento; conservar los permisos anteriores. |
| `usuarios/management/commands/crear_tecnico.py` | Crear o asignar Técnico sin reemplazar contraseña ni grupos. |
| `usuarios/views.py`, `usuarios/urls.py` | Registro, consulta de unidades e historial, con permisos en servidor. |
| `usuarios/templates/usuarios/mantenimiento_*.html` | Formulario, búsqueda de unidades e historial. |
| `usuarios/templates/usuarios/base.html`, `dashboard.html`, `maquinaria_detalle.html` | Enlaces de acceso según rol. |
| `usuarios/templates/usuarios/maquinaria_lista.html`, `maquinaria_detalle.html` | Mostrar la etiqueta existente «En mantenimiento». |
| `usuarios/static/usuarios/css/maquinaria.css` | Estilo del textarea y la descripción, conservando el diseño existente. |
| `usuarios/tests_mantenimiento.py` | 29 pruebas nuevas para HU-07. |
| `sql/00_inspeccionar_base.sql` | Incluir Mantenimiento en el inventario de columnas. |
| `README.md`, `docs/cuentas-y-roles.md`, `docs/estado-integracion-sql-server.md`, este documento | Instalación, permisos, resultados, decisiones y evidencias. |

## Pruebas automatizadas y verificaciones previas

Los siguientes resultados ya estaban documentados durante la implementación;
son independientes de la revisión manual reportada por el usuario y de la
verificación previa a publicar que se registra más abajo.

- `manage.py check`: sin incidencias.
- `manage.py makemigrations --check --dry-run`: sin cambios pendientes.
- `manage.py migrate --check`: todas las migraciones aplicadas.
- `manage.py test usuarios --noinput`: **69 pruebas, OK**, en base temporal SQL
  Server; 40 anteriores y 29 nuevas. La ejecución final duró 28,371 segundos.
- Base temporal de pruebas eliminada al terminar.
- Migración 0007 aplicada en `AlquilerEquipos` después de backup `COPY_ONLY,
  CHECKSUM` y `RESTORE VERIFYONLY WITH CHECKSUM`.
- Todas las columnas originales de Categoria, Maquinaria, Unidad, Operador y
  Mantenimiento se compararon antes y después y conservaron exactamente sus
  valores. Recuentos respectivos: **4, 4, 4, 1, 0**.
- Se verificaron `TecnicoResponsableID`, las claves foráneas a `auth_user` y
  `Unidad`, los CHECK de costo/tipo y el grupo `Técnico`.
- Registro, historial, estado y permisos también comprobados en la tabla real
  con cliente Django dentro de una transacción revertida. No quedaron cuentas
  ni registros de prueba. Los saltos de IDs por pruebas revertidas son normales
  en columnas IDENTITY de SQL Server.

La suite cubre registro completo y costo cero, dos actividades de la misma
unidad, obligatorios y espacios, fecha inválida, costo negativo/no numérico/
fuera de precisión, longitud y tipo, unidad inexistente/inactiva/alquilada/de
baja, catálogo inactivo, selección por serie, aislamiento entre unidades del
mismo catálogo, historial y orden, responsable persistente e intentos de
suplantación. Comprueba GET y POST por rol, sesiones, CSRF, protecciones de
borrado y restricciones directas de SQL Server. Prueba fallos antes y después
del guardado, incluido un fallo real del CHECK al actualizar Unidad, y cambios
de disponibilidad o eliminación de la unidad entre validación y guardado.

Las pruebas de migración usan tablas aisladas: creación nueva, adopción con
valores legacy y técnico nulo, adopción con y sin FK existente, rechazo de
datos inválidos y columnas ausentes sin eliminar filas. HU-04, HU-05 y los
inicios de sesión de Administrador/Supervisor se incluyen en la suite anterior.

El intento anterior de revisión visual mediante control de Windows se detuvo
al no poder determinar con confianza la URL de Edge. El servidor de revisión
se cerró y su base temporal SQL Server se eliminó. Esta limitación de aquel
intento no sustituye el resultado manual posterior reportado a continuación.
No se ejecutaron pruebas de carga ni concurrencia simultánea entre procesos;
sí se probó la revalidación de cambios ocurridos entre validación y guardado.

## Controles previos a la publicación

Ejecución del 27 de octubre de 2026 para esta entrega:

| Control | Resultado |
| --- | --- |
| `git fetch origin` y comparación de base | Rama `feat/sprint3-hu07-mantenimiento`, basada en `origin/main` (`e01dd1a`), sin commits anteriores ajenos a HU-07. |
| `manage.py check` | Sin incidencias. |
| `manage.py makemigrations --check --dry-run` | Sin cambios pendientes. |
| `manage.py migrate --check` | Sin migraciones pendientes; no se aplicaron migraciones en la base de trabajo. |
| `manage.py test usuarios --noinput` | **69 pruebas, OK**, en SQL Server, en 28,444 segundos: 40 anteriores y 29 de HU-07. |
| `git diff --check` | Sin errores de espacios. |

La suite se invocó mediante `execute_from_command_line` con esos argumentos,
sobrescribiendo solo `connection.settings_dict['TEST']['NAME']` en el proceso
para usar una base temporal nueva con nombre `test_hu07_<identificador>`.
El primer intento no llegó a ejecutar las pruebas: un nombre temporal largo
provocó `AttributeError: 'NoneType' object has no attribute 'replace'` al
consultar la collation desde `mssql-django` durante la migración 0006. Se
eliminó esa base temporal y se repitió con un nombre de menos de 30 caracteres;
la suite completa pasó. Se confirmó también la eliminación de la segunda
base temporal. No se modificaron el backend ni la configuración privada.

## Revisión manual reportada por el usuario

El 27 de octubre de 2026 el usuario informó que la revisión manual terminó
**sin fallos reportados en los recorridos realizados**:

- Registro e historial de mantenimiento.
- Actualización del estado.
- Rechazo de costo negativo.
- Exclusión de unidades alquiladas o fuera de servicio.
- Permisos de Técnico y Supervisor.
- Regresión de HU-04 y HU-05.

Este resultado procede del reporte del usuario; no es una nueva ejecución
automatizada ni una revisión de navegador realizada por este agente. No se
dan por realizadas otras comprobaciones de la guía de capturas, pruebas de
carga o concurrencia, ni la recopilación de capturas para el documento Word.

## Capturas para el documento Word

La siguiente lista es una guía pendiente de recopilación de evidencias. No
constituye un listado de comprobaciones manuales realizadas.

Usar una unidad destinada a pruebas: registrar cambia su estado de manera
persistente. No usar credenciales reales ni capturar contraseñas.

1. **Migraciones y pruebas.** En terminal ejecutar los comandos del README.
   Capturar 0007 aplicada, `check` sin errores y las 69 pruebas con `OK`.
2. **Rol Técnico.** Crear/asignar la cuenta con `crear_tecnico`, establecer su
   contraseña e iniciar sesión. Capturar el panel «Panel de Técnico» y los
   enlaces de mantenimiento. También puede capturarse la asignación del grupo
   en Django Admin, sin mostrar datos personales de otras cuentas.
3. **Selección de unidad.** Abrir Registrar mantenimiento. Capturar el
   selector con código, nombre, serie e ID de unidad y el responsable mostrado
   como dato de sesión. Si hay varias unidades del mismo catálogo, mostrar
   series distintas.
4. **Registro completo.** Elegir una unidad disponible, fecha válida, tipo,
   descripción y costo, por ejemplo `1250.50`. Capturar el formulario antes
   de guardar.
5. **Confirmación e historial.** Guardar y capturar el mensaje de éxito,
   cabecera con serie/ID, estado «En mantenimiento» y los cinco datos del
   historial, incluido el responsable autenticado.
6. **Persistencia y asociación.** Volver a Mantenimientos, buscar por serie y
   reabrir Ver historial. Capturar el registro. Abrir otra unidad del mismo
   catálogo y mostrar que su estado e historial siguen independientes.
7. **Validaciones.** Enviar el formulario vacío y capturar los errores. Luego
   usar un costo `-1` o texto y capturar el error sin crear actividad. El HTML
   de tipo fecha puede impedir escribir una fecha inválida; esta validación
   del servidor ya está cubierta por la prueba automatizada.
8. **Estado del equipo.** Consultar el detalle y el listado de maquinaria,
   donde debe aparecer «En mantenimiento» para la serie elegida.
9. **Permisos directos actuales.** Entrar como Cliente y abrir
   `/mantenimientos/registrar/`: capturar Acceso denegado. Con Técnico abrir
   `/maquinaria/<id>/editar/`: capturar acceso denegado. `/operadores/` debe
   devolver 404 con cualquier rol.
   Las pruebas verifican también POST y usuarios sin rol/staff/inactivos.
10. **Regresión actual.** Entrar como Administrador, comprobar una edición HU-04
    y revisar las solicitudes de alquiler. Comprobar que las antiguas rutas de
    operadores devuelven 404. No registrar operadores: HU-05 está retirada.

Opcional en SSMS, después de un registro manual, capturar la asociación sin
mostrar contraseñas ni otras columnas de usuarios:

```sql
SELECT m.MantenimientoID, m.UnidadID, u.NumeroSerie,
       m.FechaInicio, m.Tipo, m.Descripcion, m.Costo,
       m.TecnicoResponsableID, a.username, u.Estado
FROM dbo.Mantenimiento m
JOIN dbo.Unidad u ON u.UnidadID = m.UnidadID
LEFT JOIN dbo.auth_user a ON a.id = m.TecnicoResponsableID
ORDER BY m.FechaInicio DESC, m.MantenimientoID DESC;
```

## Decisiones y pendientes

- **Unidad física:** el mantenimiento pertenece a Unidad, mientras el nombre y
  código vienen de Maquinaria. No se modifica el catálogo compartido.
- **Estados:** guardar deja `Mantenimiento`, etiqueta «En mantenimiento».
  Se admiten más actividades mientras permanezca en ese estado. No se
  sobrescriben unidades alquiladas, dadas de baja o inactivas.
- **Sin cierre:** HU-07 no define finalización. Se conserva `FechaFin` legacy,
  sin editarla ni ejecutar los procedimientos de inicio/finalización. Un
  proceso de cierre y retorno a Disponible requiere una historia posterior.
- **Responsable:** cuenta autenticada, relación PROTECT, sin campo editable.
  Puede registrar el Administrador según la política existente. No se inventan
  responsables para datos legacy y un cambio de rol no rompe la relación.
- **Datos antiguos:** conservar descripciones y responsables nulos anteriores.
  Los registros web nuevos los exigen. La migración se detiene ante datos o
  esquemas incompatibles; su corrección se analiza caso por caso, sin borrado.
- **Fuera del alcance:** HU-06, cierre de mantenimiento y documento Word.
- **Revisión manual:** finalizada según el reporte del usuario, únicamente
  para los recorridos enumerados en su sección. La recopilación de capturas y
  la actualización del documento Word siguen pendientes.
