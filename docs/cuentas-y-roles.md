# Cuentas y roles vigentes

Todas las cuentas utilizan `/login/` y llegan a `/dashboard/`. El nombre completo
se muestra cuando está disponible; el inicio de sesión siempre usa el username.

| Función | Administrador | Cliente | Técnico de mantenimiento |
| --- | --- | --- | --- |
| Consultar maquinaria | Sí | Sí | Sí |
| Registrar y editar maquinaria | Sí | No | No |
| Enviar solicitudes de alquiler | No | Sí | No |
| Consultar solicitudes | Todas | Solo las propias | No |
| Aprobar o rechazar solicitudes | Sí | No | No |
| Registrar salida y retorno, pendientes e historial de entregas | Sí | No | No |
| Registrar y consultar mantenimiento | Sí | No | Sí |
| Consultar reportes y descargar Excel (.xlsx) | Sí | No | No |
| Django Admin | Sí, con is_staff | No | No |

El administrador es un superusuario activo; Cliente y Técnico corresponden a los
grupos `Cliente` y `Técnico`. `is_staff` por sí solo no otorga permisos de negocio.
Los permisos se validan en el servidor. Una cuenta sin rol puede entrar al panel,
pero no consultar ni modificar datos de negocio. Las cuentas inactivas no acceden.
Si una cuenta tiene ambos grupos, prevalece Técnico y no puede solicitar alquileres.
Los comandos de asignación retiran el otro grupo para mantener roles separados.

## Operadores y supervisores retirados

Ya no existen modelo activo, formulario, vistas, enlaces ni rutas de operadores.
Las antiguas direcciones `/operadores/`, `/operadores/registrar/` y
`/operadores/<id>/` responden 404. No se implementa la asignación de operadores.

Las migraciones históricas `0006` y `0007` se conservan para mantener el historial
de instalaciones existentes. `0008_roles_cliente` crea Cliente y Técnico y elimina
los grupos Supervisor y Operador. Preserva las cuentas y contraseñas, sin copiar
permisos de los grupos retirados ni convertir empleados en clientes. Las cuentas
que solo pertenecían a esos grupos quedan sin rol; el administrador les asigna
un rol vigente cuando corresponda.

`0009_retirar_operador` retira Operador del estado de Django. La nueva migración
`0011_eliminar_operador_sql` completa la retirada física: comprueba dependencias,
crea un respaldo completo COPY_ONLY con CHECKSUM, lo verifica y elimina únicamente
`dbo.Operador` y sus permisos Django. Conserva el ContentType como referencia
de auditoría, sin permisos activos ni modelo registrado. Se detiene ante FK,
columnas externas, módulos SQL o sinónimos que requieran revisión, ante fallo del
respaldo o ante cambios en los datos durante este. No elimina relaciones ajenas.
Ver [procedimiento y evidencias](retirada-operadores.md).

## Solicitudes de alquiler

`0010_solicitudes_alquiler` crea la nueva tabla de solicitudes. El Cliente elige
una unidad disponible desde su detalle, indica inicio y fin y envía la solicitud.
Solo puede consultar sus propias solicitudes. La cuenta y la unidad se toman
del usuario autenticado y de la ruta, nunca de campos ocultos del formulario.

El Administrador consulta todas y puede aprobar o rechazar solicitudes pendientes.
Se registra quién y cuándo revisó cada una. Se rechazan fechas inválidas o pasadas,
duplicados pendientes y aprobaciones con fechas solapadas para la misma unidad.
Antes de aprobar se comprueba nuevamente la disponibilidad y se bloquea la unidad
en una transacción para serializar aprobaciones sobre ella.

Aprobar confirma las fechas solicitadas; no emite contratos o facturas ni cambia
la unidad a Alquilado. HU-09 añade la salida física y el retorno como operaciones
separadas, exclusivas del Administrador. La salida cambia la unidad a Alquilado
y el retorno la devuelve a Disponible. Ver [HU-09](hu09-salida-retorno.md).
No se pueden volver a resolver solicitudes ya aprobadas o rechazadas.

Las entregas pendientes y el historial se consultan en `/entregas/`. El registro
conserva la solicitud, Cliente, unidad, fechas y administradores responsables.
Las fechas de movimiento se introducen en hora de Santo Domingo; no pueden ser
futuras y el retorno no puede preceder a la salida. Una entrega pendiente impide
liberar la unidad mediante la edición de maquinaria.

## Reportes (HU-10)

El Administrador puede abrir Reportes desde su panel o menú. Los cuatro reportes
reutilizan registros de maquinaria, solicitudes, salidas/retornos y mantenimientos.
Cada uno permite consultar filtros y descargar exactamente ese conjunto filtrado
en Excel (.xlsx). Los filtros inválidos no generan descargas ni resultados sin filtrar.
Cliente, Técnico y personal is_staff sin ser Administrador reciben 403 también
al solicitar directamente la descarga. Ver [HU-10: reportes](hu10-reportes.md).

Los reportes no registran movimientos ni cambian HU-09. El total de mantenimiento
usa costos existentes y no representa ingresos, pagos ni importes de alquiler.

## Aplicar los cambios

Con SQL Server disponible, realizar y verificar un respaldo antes de migrar la base
existente. Después, desde la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test usuarios
```

La comprobación anterior en SQLite y el error de conexión 08001 corresponden a
la sesión previa. SQL Server está accesible en esta revisión; los resultados
actuales y las migraciones aplicadas se registran en
[retirada de operadores](retirada-operadores.md).

## Crear o asignar cuentas

```powershell
.\.venv\Scripts\python.exe manage.py crear_cliente cliente1 --nombre "Luis"
.\.venv\Scripts\python.exe manage.py changepassword cliente1
.\.venv\Scripts\python.exe manage.py crear_tecnico tecnico1 --nombre "Ana"
.\.venv\Scripts\python.exe manage.py changepassword tecnico1
```

Los comandos conservan la contraseña y el estado activo de cuentas existentes;
rechazan cuentas con privilegios administrativos. Las cuentas nuevas necesitan
`changepassword` antes de iniciar sesión. Se puede asignar el grupo a una cuenta
desde Django Admin, dejando is_staff e is_superuser desmarcados para Cliente y Técnico.
Para crear el Administrador se utiliza `manage.py createsuperuser`.

HU-05 y HU-06 quedan retiradas. Sus reemplazos no se redactan todavía.

La importación `migrar_datos_locales` conserva cuentas y hashes, pero excluye los
grupos retirados y los permisos de Operador. Repetirla no recupera esos accesos
ni convierte a las cuentas antiguas en clientes.

## Antecedente: verificación de la sesión previa en SQLite

- 64 pruebas funcionales aprobadas en SQLite temporal: maquinaria, edición,
  autenticación, roles, mantenimiento y solicitudes de alquiler.
- Migraciones 0008–0010 verificadas en SQLite temporal sobre el estado 0007,
  con un operador y una cuenta de Supervisor de prueba: conserva todos los
  campos del operador, la cuenta y su contraseña, retira el grupo y crea la
  tabla de solicitudes. Solo se omitió la operación T-SQL histórica de 0003,
  cuya columna ya está presente en el esquema inicial.
- Los tests funcionales de SQLite sincronizaron los modelos actuales en una
  base en memoria. Las pruebas de adopción de tablas legacy específicas de
  SQL Server no se ejecutaron en SQLite.
- `manage.py check`, `makemigrations --check --dry-run` y `git diff --check`: OK.
- En aquella sesión no se aplicaron migraciones ni se modificaron filas de la
  base SQL Server real. La retirada física y la ejecución SQL Server de esta
  revisión se documentan por separado en el enlace anterior.
