# Sistema de alquiler de equipos

Proyecto Django con inicio de sesión, panel por rol, registro, edición y consulta
de maquinaria y registro y consulta de operadores. La aplicación usa SQL Server
para cuentas, roles, sesiones, catálogo, unidades físicas y operadores.

## Requisitos

- Python 3.12 a 3.14 (este entorno usa Python 3.14).
- SQL Server 2017 o posterior; se probó con SQL Server 2025 Express.
- Microsoft ODBC Driver 18 for SQL Server.
- PowerShell y Git en Windows.

El backend `mssql-django==2.0.0` soporta Django 6.1 y Python 3.14.

## Instalación

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/configurar_desarrollo.py
```

El último comando crea o completa `config.local.json` sin cambiar secretos ya
existentes. Ese archivo está excluido de Git. La configuración de ejemplo usa
autenticación integrada de Windows contra `localhost\SQLEXPRESS` y la base
`AlquilerEquipos`:

```json
"DATABASE": {
  "ENGINE": "mssql",
  "NAME": "AlquilerEquipos",
  "HOST": "localhost\\SQLEXPRESS",
  "PORT": "",
  "USER": "",
  "PASSWORD": "",
  "OPTIONS": {
    "driver": "ODBC Driver 18 for SQL Server",
    "extra_params": "TrustServerCertificate=yes"
  }
}
```

Para autenticación SQL, escribe `USER` y `PASSWORD` solo en
`config.local.json`. También se admiten las variables `DJANGO_DB_ENGINE`,
`DJANGO_DB_NAME`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT`, `DJANGO_DB_USER`,
`DJANGO_DB_PASSWORD`, `DJANGO_DB_DRIVER` y `DJANGO_DB_EXTRA_PARAMS`.

## Preparar SQL Server

Crea una base vacía si todavía no existe:

```sql
CREATE DATABASE [AlquilerEquipos];
```

Antes de cambiar una base existente, ejecuta el inventario de solo lectura:

```powershell
sqlcmd -S ".\SQLEXPRESS" -E -C -i sql\00_inspeccionar_base.sql
```

Haz una copia desde SQL Server Management Studio o con `BACKUP DATABASE`. No
guardes archivos `.bak` en Git. Después aplica las migraciones. `--fake-initial`
reconoce `Categoria`, `Maquinaria` y `Unidad` si ya venían del script original;
en una base nueva las crea.

```powershell
.\.venv\Scripts\python.exe manage.py migrate --fake-initial
```

Las migraciones de Django son la fuente de verdad para el módulo implementado.
Los archivos siguientes conservan y corrigen por separado los objetos futuros
del script del compañero:

- `sql/01_completar_esquema_legacy.sql`: crea los objetos omitidos y corrige
  referencias de `Equipo` a `Maquinaria`.
- `sql/02_procedimientos_legacy_corregidos.sql`: procedimientos derivados del
  original con nombres corregidos y `CREATE OR ALTER`.
- `docs/revision-script-original.md`: hallazgos, diferencias y orden correcto.

Los scripts son aditivos. No eliminan ni reemplazan filas. El módulo web actual
no depende de los procedimientos de alquiler.

## Migrar datos locales anteriores

Conserva `db.sqlite3` y `data/maquinaria_provisional.json` como respaldo. Con la
conexión SQL Server activa, ejecuta:

```powershell
.\.venv\Scripts\python.exe manage.py migrar_datos_locales
```

El comando:

- copia usuarios sin recalcular sus contraseñas: conserva exactamente el hash;
- copia grupos, membresías y permisos compatibles;
- convierte el JSON en `Categoria`, `Maquinaria` y `Unidad`;
- no actualiza usuarios, códigos o números de serie que ya existan;
- verifica al final que usuarios, hashes, roles y unidades estén presentes;
- se puede repetir sin duplicar datos.

Se pueden indicar rutas distintas con `--sqlite` y `--json`.

## Roles y acceso

| Rol | Consultar, filtrar y ver detalles | Registrar | Django Admin |
| --- | --- | --- | --- |
| Administrador (`is_superuser`) | Sí | Sí | Sí |
| Supervisor (grupo `Supervisor`) | Sí | No | No |
| Sin rol | No | No | No |

La vista de registro comprueba el rol en el servidor. Un Supervisor recibe HTTP
403 aunque escriba directamente `/maquinaria/registrar/` o envíe un POST.

Para crear cuentas nuevas:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py crear_supervisor luis --nombre "Luis"
.\.venv\Scripts\python.exe manage.py changepassword luis
```

## Comprobar y ejecutar

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test usuarios
.\.venv\Scripts\python.exe manage.py runserver
```

Abre <http://127.0.0.1:8000/login/>. El administrador de Django está en
<http://127.0.0.1:8000/admin/>.

Las pruebas usan una base temporal `test_AlquilerEquipos` en la misma instancia
SQL Server y la eliminan al terminar. La cuenta configurada debe poder crear y
eliminar esa base de prueba.

## HU-02 y HU-03: fabricación y ubicación

El registro de una unidad exige año de fabricación (entero desde 1 hasta el año
actual) y ubicación actual (hasta 200 caracteres, sin aceptar solo espacios).
El año se valida al recibir el formulario y al validar el modelo. La ubicación
también se exige al validar un modelo nuevo, incluido el formulario de Django
Admin. El administrador registra y consulta; el supervisor solo consulta.

Se reutiliza `Unidad.UbicacionActual`. La migración
`usuarios/0004_anio_fabricacion_unidad` añade `Unidad.AnioFabricacion`, nullable
y sin valor predeterminado. No modifica las ubicaciones ni rellena años antiguos.
Ambos campos pertenecen a cada unidad física, ya que un mismo modelo de catálogo
puede tener unidades fabricadas en años distintos y en diferentes ubicaciones.
El detalle muestra ambos datos; el listado muestra la ubicación. Los datos
desconocidos aparecen como «No especificado/a» sin guardar ese texto en la base.

La página de acceso denegado usa un manejador 403 explícito y muestra un botón
para volver al panel. Conserva el estado HTTP 403 con `DEBUG=True` y `False`.

Verificación del 22 de octubre de 2026: 15 pruebas aprobadas en SQL Server,
incluyendo registro y lectura de los valores persistidos, validaciones, campos
en las plantillas, visualización de valores desconocidos y permisos por rol.
`manage.py check` y `makemigrations --check --dry-run` también pasaron.
La migración se aplicó en la base local y se compararon todas las columnas
anteriores, conservando los datos existentes y los valores desconocidos nulos.

## Archivos locales y Git

`.gitignore` excluye `config.local.json`, `.env`, claves, SQLite, `data/`,
respaldos, copias SQL originales, `tmp/`, `output/`, el entorno virtual y cachés.
No uses `git add -f` con esos archivos.

Antes de compartir cambios:

```powershell
git status --short
git diff --cached --stat
git diff --cached
```

Trabaja en una rama y usa un pull request para no sobrescribir cambios de otras
personas. Repositorio: <https://github.com/giorgioRD/Alquiler_maquinaria>.


## HU-04: actualizar información de maquinaria

El administrador puede abrir **Editar** desde el listado o **Editar maquinaria**
desde el detalle. El formulario carga los datos actuales y valida los mismos
campos obligatorios que el registro. El código de catálogo y el número de serie
pueden conservar sus valores propios, pero no tomar los de otro registro.
El supervisor y los usuarios sin rol reciben HTTP 403 ante GET y POST de edición.

Los datos del catálogo se comparten entre todas sus unidades. El formulario
advierte este alcance. La serie, ubicación, estado, año y horas de uso pertenecen
solo a la unidad seleccionada. Ambos grupos se guardan en una transacción:
un error revierte también los cambios de catálogo y cualquier categoría creada.

La migración 0005_fechas_modificacion_maquinaria_unidad añade columnas nullable
FechaModificacion a Maquinaria y Unidad. No inventa fechas para registros
existentes. La edición web registra una fecha solo en el objeto cuyos datos
cambian; abrir el formulario o guardar los mismos valores no modifica la fecha.
El detalle muestra ambas fechas en la zona horaria de República Dominicana.
Las fechas corresponden a la edición web HU-04, no a cambios directos por SQL.

Para aplicar esta HU en otra base SQL Server, comprobar primero el destino y
crear y verificar una copia de seguridad. Después ejecutar:

    .\.venv\Scripts\python.exe manage.py showmigrations usuarios --plan
    .\.venv\Scripts\python.exe manage.py sqlmigrate usuarios 0005
    .\.venv\Scripts\python.exe manage.py migrate usuarios 0005_fechas_modificacion_maquinaria_unidad --noinput
    .\.venv\Scripts\python.exe manage.py test usuarios --noinput
    .\.venv\Scripts\python.exe manage.py runserver

Prueba manual: entrar como administrador, abrir una unidad y editar su ubicación
y una tarifa. Guardar, comprobar el mensaje de éxito y las fechas, y volver a
consultar para verificar la persistencia. Intentar guardar un campo obligatorio
vacío y una serie de otra unidad. Por último, entrar como supervisor y comprobar
que la dirección de edición devuelve acceso denegado.

Validación del 26 de octubre de 2026: después de las 26 pruebas iniciales con
SQLite temporal, se aplicó la migración 0005 en `AlquilerEquipos` sobre SQL Server
Express. Antes se creó un backup `COPY_ONLY` con `CHECKSUM` y se comprobó mediante
`RESTORE VERIFYONLY WITH CHECKSUM`. El archivo del servidor es
`C:\Program Files\Microsoft SQL Server\MSSQL17.SQLEXPRESS\MSSQL\Backup\AlquilerEquipos_antes_HU04_0005_20261026T223842Z.bak`.

Se verificaron las dos columnas `FechaModificacion` de tipo `datetimeoffset`,
nullable, y el registro de la migración en `django_migrations`. Se conservaron
los recuentos de 4 catálogos y 4 unidades, todos con fecha de modificación `NULL`.
No quedaron migraciones pendientes. `check` y `makemigrations --check --dry-run`
pasaron sin incidencias.

Las 26 pruebas también pasaron en la base temporal SQL Server
`test_AlquilerEquipos`, aplicando toda la cadena de migraciones y eliminando la
base temporal al terminar. Cubren permisos GET/POST, edición, validaciones,
fechas y reversión de la transacción ante un fallo de guardado. No se encontraron
triggers en las tablas de maquinaria de la base revisada. Esta ejecución no
incluye pruebas de concurrencia entre editores ni una revisión visual en navegador;
la prueba manual descrita arriba queda como comprobación de aceptación.

## HU-05: registrar operador

El administrador activo (`is_superuser`) puede abrir **Registrar operador** en el
panel o **Operadores** en la navegación. Registro, listado y detalle comprueban
el rol en el servidor. Supervisor, personal `is_staff` sin ser superusuario y
usuarios sin rol reciben HTTP 403; las solicitudes anónimas van al inicio de
sesión. Un operador es un registro del negocio: no se crea una cuenta Django.

El formulario exige nombre completo, cédula, teléfono, dirección, tipo de
licencia y fecha de vencimiento. Rechaza valores vacíos o solo con espacios,
fechas inválidas y valores que excedan las columnas existentes. La licencia es
texto de hasta 10 caracteres; no se impone un catálogo de tipos ni una regla de
vigencia para asignaciones, que corresponde definir en la HU-06.

Se reutiliza `dbo.Operador`, encontrada vacía en la base revisada. La migración
`0006_integrar_operador` incorpora su modelo a Django y añade únicamente
`CedulaNormalizada`, una columna calculada persistida con un índice único.
Elimina guiones y espacios de la clave de comparación; los registros web nuevos
guardan la cédula como dígitos. La comprobación incluye operadores inactivos y
la restricción de SQL Server protege también inserciones fuera del formulario.
Las cédulas se validan como 1 a 20 dígitos, sin asumir un algoritmo nacional de
verificación no solicitado.

La tabla legacy conserva `Nombre` y `Apellido` (80 caracteres cada uno). El
formulario recibe un nombre completo y lo almacena sin truncarlo: usa `Nombre`
si cabe y divide nombres largos en un espacio entre ambas columnas. No infiere
apellidos; al consultar concatena ambas partes. Los nombres y apellidos de
registros previos y las demás columnas legacy se conservan. Los datos de contacto
y licencia siguen admitiendo `NULL` en el esquema para respetar registros antiguos,
pero son obligatorios para los registros nuevos de esta HU.

Los operadores nuevos reciben `Estado='Activo'` y fecha de creación. El detalle
y el listado muestran el estado; `operador.activo` y
`Operador.objects.filter(estado='Activo')` permiten identificar activos para la
futura HU-06. Todavía no se crean asignaciones ni relaciones con maquinaria.

En una instalación sin tabla de operadores, la misma migración la crea. Si hay
cédulas antiguas que coinciden al normalizar o quedan vacías, la migración se
detiene sin borrar filas para permitir su revisión. La adopción es irreversible
mediante `migrate` hacia atrás: no elimina una tabla que puede contener datos del
negocio. Antes de aplicarla en otra base, inspeccionar el esquema y verificar un
respaldo; después ejecutar:

```powershell
.\.venv\Scripts\python.exe manage.py migrate usuarios 0006_integrar_operador --plan
.\.venv\Scripts\python.exe manage.py migrate usuarios 0006_integrar_operador --noinput
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test usuarios --noinput
```

Validación del 26 de octubre de 2026: antes de aplicar 0006 en `AlquilerEquipos`,
se creó un backup `COPY_ONLY, CHECKSUM` y se verificó con
`RESTORE VERIFYONLY WITH CHECKSUM`. Archivo del servidor:
`C:\Program Files\Microsoft SQL Server\MSSQL17.SQLEXPRESS\MSSQL\Backup\AlquilerEquipos_antes_HU05_0006_20261026T230053Z.bak`.
Se compararon exactamente los valores previos y posteriores de las columnas
originales de Categoria, Maquinaria, Unidad y Operador: sin cambios. Se verificaron
la columna calculada persistida, su índice único y la ausencia de migraciones
pendientes. `check` y `makemigrations --check --dry-run` pasaron.

Pasaron 40 pruebas en SQL Server temporal: las 26 existentes y 14 nuevas de
operadores. Cubren registro, persistencia y consulta de todos los campos,
confirmación, obligatorios, fechas y longitudes, cédulas equivalentes, unicidad
directa en SQL Server, permisos GET/POST, acceso anónimo, prevención de cambios
de estado por POST y ausencia de cuentas de acceso nuevas. Las pruebas de la
migración crean tablas aisladas para comprobar creación, adopción conservando
valores legacy y rechazo de duplicados sin eliminar datos. La base temporal se
elimina al terminar. También se comprobó el flujo web sobre la tabla legacy real
dentro de una transacción revertida, sin dejar operadores de prueba guardados.

Comprobación visual pendiente de aceptación:

1. Ejecutar `.\.venv\Scripts\python.exe manage.py runserver` y entrar como
   administrador en <http://127.0.0.1:8000/login/>.
2. En el panel, abrir **Registrar operador**, completar los seis campos y guardar.
3. Revisar el mensaje de confirmación, todos los valores y el estado **Activo**
   en el detalle. Volver al listado y abrir otra vez **Ver detalles**.
4. Intentar registrar la misma cédula cambiando guiones por espacios: debe
   aparecer un error y mantenerse un solo operador.
5. Enviar el formulario vacío: cada campo debe mostrar su error.
6. Entrar como supervisor: no debe aparecer **Operadores** y acceder directamente
   a `/operadores/registrar/` debe devolver acceso denegado.
7. Volver al listado de maquinaria como administrador y comprobar que **Ver
   detalles** y **Editar** siguen separados horizontalmente.
