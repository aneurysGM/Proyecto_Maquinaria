# HU-09: registrar salida y retorno de maquinaria

Sprint 4. Validación del 30 de octubre de 2026, America/Santo_Domingo.
La implementación conserva el trabajo local anterior y no publica cambios en GitHub.
Esta guía describe HU-09. Los reportes posteriores de HU-10 se documentan en
[HU-10: reportes](hu10-reportes.md) y reutilizan estos movimientos.

## Flujo implementado

El Administrador activo abre **Solicitudes de alquiler** y, para una solicitud
aprobada con unidad activa, catálogo activo y estado Disponible, abre **Registrar
salida**. Confirma fecha y hora del movimiento. El servidor vuelve a comprobar
la aprobación, disponibilidad y ausencia de una salida anterior, registra la fecha
y el Administrador autenticado y cambia la unidad a **Alquilado**.

**Salidas y retornos** abre las entregas pendientes de devolución. Desde una entrega
se registra el retorno con fecha y hora. Debe tener salida previa, no tener retorno
y conservar el estado Alquilado. El servidor registra el Administrador receptor y
cambia la unidad a **Disponible**. No se permite repetir la salida, ni siquiera
después del retorno, ni repetir el retorno.

El historial completo y el filtro Devueltas conservan Cliente, unidad física,
solicitud, fechas, responsables y estado de entrega. Las cuentas se relacionan
con PROTECT; cambiar el rol o desactivar una cuenta no elimina su historia.
El retorno de una unidad desactivada sigue siendo posible si conserva estado
Alquilado; la desactivación no se revierte y el historial no se oculta.

Cliente, Técnico, personal is_staff sin ser Administrador y usuarios sin rol
reciben 403 ante GET/POST directos. Las sesiones anónimas se redirigen al login
y las cuentas inactivas no adquieren permisos. Las pantallas comprueban permisos
antes de consultar los registros; los servicios transaccionales también los validan.

Los formularios solo aceptan fechas de movimiento. Cliente, unidad y solicitud
proceden del registro existente; los responsables proceden de la sesión y no de
campos enviados por el navegador. GET no escribe; solo POST confirma movimientos,
con protección CSRF. PUT y DELETE no se admiten.

## Estructuras reutilizadas e inspección SQL

Se inspeccionaron tablas, columnas, relaciones, CHECK y definiciones SQL en
`Thechosenone\SQLEXPRESS`, base `AlquilerEquipos`, antes de editar el esquema.

- `usuarios_solicitudalquiler` ya relaciona Cliente Django y Unidad y conserva
  la aprobación. Se reutiliza como registro de entrega: una solicitud permite una
  sola salida y un solo retorno. No se duplican Cliente, unidad ni cabecera de alquiler.
- `Unidad.Estado` ya admite Disponible y Alquilado; se reutilizan esos valores.
- `Alquiler` y `AlquilerDetalle` legacy están vacías, se relacionan con la tabla
  Cliente legacy y contienen tarifas, depósitos, ITBIS y otras cifras financieras.
  No representan directamente al usuario Django de la solicitud actual.
- `sp_EntregarAlquiler` exige una reserva y depósito del flujo legacy;
  `sp_DevolverAlquiler` calcula mora/daños y puede crear mantenimiento. Se preservan
  y no se ejecutan desde HU-09. No se inventan importes, depósitos o identidades
  para poder usarlos.
- `HistorialEstadoUnidad` no tiene solicitud, Cliente ni administradores responsables;
  se conserva como antecedente. El historial HU-09 usa los movimientos de la solicitud.

El estado de entrega se deriva de sus fechas: **Sin entregar**, **Pendiente de
devolución** o **Devuelta**. No se mantiene otro campo de estado que pueda
contradecir esas fechas. La aprobación de la solicitud sigue siendo Aprobada.

## Migración y conservación de datos

Aplicada: **`0012_salida_retorno_maquinaria`**. Las migraciones anteriores no se
modifican. Añade a la tabla existente cuatro campos nullable, sin asignar movimientos
a solicitudes anteriores:

| Campo | Contenido |
| --- | --- |
| `fecha_salida` | Fecha y hora físicas de salida, datetimeoffset. |
| `entregado_por` | FK al Administrador que confirma la salida. |
| `fecha_retorno` | Fecha y hora físicas de retorno, datetimeoffset. |
| `recibido_por` | FK al Administrador que confirma el retorno. |

Las restricciones de SQL Server exigen fecha y responsable juntos, salida solo
para Aprobada y retorno con salida previa y fecha igual o posterior. El índice
único filtrado `UQ_Entrega_Unidad_Pendiente` admite una sola entrega pendiente por
unidad. Los dos CHECK quedaron habilitados y confiables tras la aplicación real.

La comparación de todos los valores originales de **25 tablas**, excluyendo la
nueva fila de `django_migrations`, dio huellas SHA-256 idénticas. Incluye los
4 usuarios, 4 categorías, 4 catálogos, 4 unidades y 1 mantenimiento. Las tablas
legacy y sus datos, las sesiones, logs, grupos, permisos, FK anteriores y módulos
SQL se conservaron. La tabla de solicitudes estaba vacía y sigue sin registros
de prueba; no se crearon entregas en la base de trabajo.

## Transacciones y concurrencia

Los servicios de `usuarios/entregas.py` releen y bloquean unidad y solicitud dentro
de `transaction.atomic`, siguiendo el orden usado por la aprobación. Solo después
validan y guardan el movimiento y el estado. Un fallo en cualquiera de los
guardados revierte ambos. El índice filtrado protege además la unicidad en SQL.

La edición de maquinaria y su validación de modelo impiden cambiar una unidad con
entrega pendiente a un estado diferente de Alquilado. Se debe registrar el retorno.
Aunque una escritura SQL externa altere el estado, el servicio comprueba que no
exista otra entrega pendiente. Si el estado de una unidad entregada se cambia
externamente a Mantenimiento u otro valor, el retorno se detiene para revisión;
no sobrescribe silenciosamente ese estado.

Las pruebas concurrentes usan dos conexiones SQL independientes: misma solicitud,
solicitudes distintas para una unidad y dos retornos. En cada caso solo se registra
una operación y la otra se rechaza. Son pruebas funcionales de contención;
no constituyen una prueba de carga prolongada.

## Fechas y alcance

- Entrada y visualización en **America/Santo_Domingo**, sin cambiar la configuración
  global de los flujos existentes. SQL conserva fecha y hora con zona horaria.
- La fecha por defecto es el momento actual; pueden registrarse movimientos pasados,
  pero no futuros. El retorno puede coincidir exactamente con la salida.
- No se exige que la salida coincida con el rango planificado de la solicitud:
  HU-09 registra el hecho físico sobre una aprobación existente. No se modifican
  automáticamente las fechas solicitadas ni la política anterior de solapamientos.
- No se emiten contratos o facturas ni se calculan mora, daños, pagos o depósitos.
  HU-10 añade reportes de lectura por separado; no se invocan los procedimientos
  financieros legacy desde estos flujos.

## Respaldos y evidencias

Los dos respaldos completos se crearon con COPY_ONLY y CHECKSUM y se verificaron
con `RESTORE VERIFYONLY WITH CHECKSUM, STOP_ON_ERROR` antes de alterar el esquema.
Están en el directorio del servicio SQL Server:

```text
C:\Program Files\Microsoft SQL Server\MSSQL17.SQLEXPRESS\MSSQL\Backup\
AlquilerEquipos_pre_hu09_20261031T002809Z_cc3e43fb.bak
AlquilerEquipos_pre_hu09_migracion_20261031T003542Z_9c243474.bak
```

Los nombres usan UTC: corresponden al **30 de octubre**, 20:28 y 20:35, en Santo
Domingo. No se realizó una restauración completa a otra base.

La copia del código y cambios locales anteriores está en
`respaldos_locales/hu09_20261031T002644Z/codigo_antes.zip`. El diff, inventario,
respaldo, huellas y log de aplicación están en
`evidencias_locales/hu09_20261031T002644Z/`, fuera de Git.

## Verificaciones

- `check` sin incidencias, `makemigrations --check --dry-run` sin cambios y
  `migrate --check` sin migraciones pendientes. Las doce migraciones de usuarios
  figuran aplicadas. `git diff --check` sin errores.
- Suite completa SQL Server: **106 pruebas aprobadas**: 80 existentes y 26 de HU-09.
  Ejecución final en `tmp/verificaciones/django_20261031T003755Z_5506d9.log`;
  detalle inicial de HU-09 en su carpeta de evidencias.
- Salida y retorno, identificación de cliente/unidad/solicitud, responsables de
  sesión, fechas inválidas/futuras, orden de fechas y conversión horaria.
- Duplicados de salida y retorno; reutilización de la unidad en otra solicitud
  después de devolverla; entrega pendiente aunque se altere el estado externamente.
- Acceso directo por rol, sesión, CSRF, métodos y GET sin escrituras.
- Rollback ante fallo del primer guardado, CHECK real al actualizar unidad y fallo
  posterior a ambos guardados, tanto para salida como para retorno.
- Mantenimiento y solicitudes rechazan la unidad entregada; edición no la libera.
- Migración sobre solicitudes anteriores en los tres estados: conserva valores y
  deja los cuatro campos nuevos en NULL. Unicidad y CHECK también probados mediante
  escrituras ORM que omiten formularios.
- Tres pruebas de concurrencia real en SQL Server, con un éxito y un rechazo por
  operación competidora. Se eliminan las bases temporales al terminar.

## Aplicar en otro equipo

Con la aplicación sin escrituras, revisar la configuración local y ejecutar:

```powershell
.\.venv\Scripts\python.exe manage.py respaldar_sqlserver --motivo pre_hu09
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe -B scripts/verificar_proyecto.py
```

No continuar si falla el respaldo o su verificación. La cuenta SQL necesita
permisos de respaldo, verificación, modificación del esquema y creación/eliminación
de la base de pruebas. No hace falta ejecutar de nuevo los scripts SQL legacy.

## Prueba manual

Usar una unidad destinada a pruebas; las confirmaciones cambian su estado real.
Iniciar con `manage.py runserver` y abrir <http://127.0.0.1:8000/login/>.

1. **Cliente:** desde Consultar maquinaria, solicitar una unidad Disponible.
   Usar fechas de solicitud válidas. Cerrar sesión.
2. **Administrador:** abrir Solicitudes de alquiler, aprobar la solicitud y abrir
   Registrar salida. Comprobar Cliente y número de serie. Mantener la fecha y hora
   actuales de Santo Domingo y confirmar.
3. Verificar el mensaje de salida, la unidad Alquilado en el catálogo y la entrega
   en Salidas y retornos → Pendientes de devolución. Actualizar la página o volver
   a abrir la URL de salida y reenviar: debe rechazar la repetición sin cambiar datos.
4. Abrir Registrar retorno y probar una fecha anterior a la salida: debe mostrar
   error y conservar la unidad Alquilado. Introducir la hora actual y confirmar.
   Puede confirmar un Administrador distinto para comprobar ambos responsables.
5. Verificar la unidad Disponible, la entrega fuera de Pendientes y el registro
   completo en Devueltas/Historial completo. Repetir el retorno: debe rechazarlo.
6. **Cliente y Técnico:** intentar `/entregas/`,
   `/solicitudes/<id>/salida/` y `/solicitudes/<id>/retorno/`: deben recibir 403
   y no tener los enlaces de gestión. Comprobar que mantienen sus funciones previas.

Referencias técnicas: [transacciones de mssql-django](https://learn.microsoft.com/en-us/sql/connect/python/mssql-django/transactions?view=sql-server-ver17),
[select_for_update de Django](https://docs.djangoproject.com/en/6.0/ref/models/querysets/#select-for-update)
y [CREATE INDEX de SQL Server](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-index-transact-sql?view=sql-server-ver17).
