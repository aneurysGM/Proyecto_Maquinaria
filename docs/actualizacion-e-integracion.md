# Actualización e integración de la entrega

Entrega del 31 de octubre de 2026. Rama: `feat/roles-alquileres-entregas-reportes`.
El pull request tiene como destino `main`; su fusión corresponde al responsable
del proyecto. El compañero debe tener acceso al repositorio privado.

Incluye Administrador, Cliente y Técnico, retirada de Supervisor y Operador,
solicitudes de alquiler, salidas y retornos, mantenimiento y cuatro reportes
administrativos con descarga únicamente en Excel (`.xlsx`).

## Obtener el código

Para una copia nueva:

```powershell
git clone --branch feat/roles-alquileres-entregas-reportes https://github.com/giorgioRD/Alquiler_maquinaria.git
cd Alquiler_maquinaria
```

En una copia existente, revisar primero `git status`. Conservar los cambios
propios en un commit de una rama de trabajo o mediante un stash que incluya los
archivos nuevos (`git stash push -u`). No usar `reset --hard` ni `clean` para
actualizar. Con el árbol limpio:

```powershell
git fetch origin
git switch --track origin/feat/roles-alquileres-entregas-reportes
```

Si ya existe la rama local, usar `git switch feat/roles-alquileres-entregas-reportes`
y `git pull --ff-only`. Los cambios guardados en un stash se recuperan después
de revisar su compatibilidad; no se aplican automáticamente sobre esta entrega.
Después de fusionar el PR, también se podrá obtener desde `main` mediante
`git switch main` y `git pull --ff-only`.

## Preparar el entorno y conservar la configuración

Se requieren Python 3.12–3.14, SQL Server 2017 o posterior y Microsoft ODBC
Driver 18 for SQL Server. La validación de esta entrega usa Python 3.14 y SQL
Server Express. `requirements.txt` fija las dependencias de ejecución, incluida
`openpyxl==3.1.5` para las descargas Excel.

Si no existe el entorno virtual:

```powershell
py -m venv .venv
```

Instalar las dependencias en el entorno del compañero:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

En una instalación existente, conservar `config.local.json` y la clave privada
propia. En una instalación nueva, generar la configuración:

```powershell
.\.venv\Scripts\python.exe scripts/configurar_desarrollo.py
```

El generador crea una clave privada cuando no existe la entrada `SECRET_KEY`.
No copiar una configuración ajena ni dejar la clave vacía del archivo de ejemplo.
Configurar localmente `DATABASE` para el servidor y la base correctos. Las
variables `DJANGO_*` tienen prioridad sobre el archivo; revisar que no apunten a
otra base. No compartir credenciales, bases, respaldos ni el entorno virtual.

## Actualizar una base existente

Detener `runserver` y las demás aplicaciones o procesos que escriban en esa base.
Revisar el inventario de solo lectura `sql/00_inspeccionar_base.sql` y confirmar
servidor/base antes de continuar. Para bases del script original sin historial de
migraciones, seguir primero la sección **Preparar SQL Server** del
[README](../README.md): `--fake-initial` solo procede tras comprobar el esquema
inicial existente; no sustituye la revisión de compatibilidad.

Crear un respaldo completo **antes de aplicar cualquier migración pendiente**:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py showmigrations usuarios
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py respaldar_sqlserver --motivo pre_integracion
```

Continuar solo si el respaldo termina verificado. El comando usa `COPY_ONLY,
CHECKSUM` y `RESTORE VERIFYONLY WITH CHECKSUM, STOP_ON_ERROR`; imprime la ruta
del `.bak` en el servidor SQL, que puede ser otra máquina. Conservar el archivo
y registrar su ubicación. Para una base con datos valiosos, comprobar también
su restauración en una base separada y ejecutar primero allí la actualización.
La cuenta SQL necesita permisos de inspección (`VIEW DEFINITION`), respaldo,
verificación y cambios de esquema. El servicio SQL Server necesita acceso al
directorio de respaldos.

| Migración | Efecto y conservación de datos |
| --- | --- |
| `0001`–`0007` | Historial conservado; maquinaria y mantenimiento se crean o integran según su migración. |
| `0008_roles_cliente` | Crea Cliente y Técnico; elimina los grupos Supervisor/Operador y sus membresías. Conserva cuentas, contraseñas y actividad; no asigna otro rol automáticamente. |
| `0009_retirar_operador` | Retira el modelo del estado de Django; todavía conserva la tabla SQL. |
| `0010_solicitudes_alquiler` | Crea la tabla de solicitudes; no reemplaza las tablas legacy de alquiler. |
| `0011_eliminar_operador_sql` | Elimina físicamente `dbo.Operador` y sus permisos tras crear y verificar otro respaldo. Los registros de operadores se conservan en ese respaldo. |
| `0012_salida_retorno_maquinaria` | Añade fechas/responsables nullable y restricciones de entrega a las solicitudes. Conserva solicitudes previas sin inventar movimientos. |

El respaldo previo a `0008` conserva también las membresías originales;
el respaldo automático de `0011` ocurre después de retirarlas. La eliminación
de operadores es deliberada y no tiene reversión automática. Sus datos dejan
de estar en la aplicación y solo se recuperan desde el respaldo. Se conservan
maquinaria, cuentas, mantenimiento, solicitudes y las tablas ajenas al módulo.
Ver el [procedimiento de retirada](retirada-operadores.md).

Aplicar y comprobar:

```powershell
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe -B scripts/verificar_proyecto.py
```

Si `0011` detecta referencias a operadores, un esquema incompatible o un fallo
de respaldo, detener la actualización y revisar el diagnóstico. No borrar
dependencias, la base, datos ni el historial `django_migrations`; tampoco usar
`--fake` para omitir el bloqueo. Algunas migraciones anteriores pueden haber
quedado aplicadas. No ejecutar migraciones hacia atrás para intentar recuperar
operadores: revisar el respaldo en una base aparte y planificar la recuperación.

No volver a ejecutar los scripts SQL legacy ni `migrar_datos_locales` como parte
de una actualización normal. Este último solo corresponde a la importación
inicial documentada de SQLite/JSON, con los originales conservados.

## Instalación con base nueva

Crear una base SQL Server vacía, configurar su conexión y ejecutar:

```powershell
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe -B scripts/verificar_proyecto.py
.\.venv\Scripts\python.exe manage.py createsuperuser
```

La cadena histórica crea temporalmente la tabla Operador y después la retira;
por ello también exige los permisos de respaldo de `0011` en una base nueva.
No se entregan cuentas ni contraseñas predefinidas.

## Comprobar y ejecutar

`verificar_proyecto.py` ejecuta `check`, `makemigrations --check --dry-run` y
`migrate --check`. Después crea una base `test_verif_<identificador>` única,
aplica las migraciones, ejecuta la suite completa y elimina esa base al terminar.
Necesita permisos para crear/eliminar bases de prueba; los respaldos de las
pruebas permanecen en el servidor SQL. Los logs se guardan localmente en
`tmp/verificaciones/`, excluido de Git. La base de trabajo solo se consulta.
`--solo-comprobaciones` permite ejecutar las comprobaciones sin crear una base
de pruebas cuando no se dispone de esos permisos.

En una instalación existente, comparar los recuentos y registros de negocio
con el inventario anterior y comprobar las cuentas antes de reabrir escrituras.
Administrador es una cuenta Django activa con `is_superuser=True`; Cliente y
Técnico usan sus grupos correspondientes. Las cuentas de roles retirados
conservan su contraseña y quedan sin acceso de negocio hasta que se les asigne
explícitamente un rol vigente.

Para crear cuentas nuevas de prueba, sin contraseñas compartidas:

```powershell
.\.venv\Scripts\python.exe manage.py crear_cliente cliente_prueba
.\.venv\Scripts\python.exe manage.py changepassword cliente_prueba
.\.venv\Scripts\python.exe manage.py crear_tecnico tecnico_prueba
.\.venv\Scripts\python.exe manage.py changepassword tecnico_prueba
.\.venv\Scripts\python.exe manage.py runserver
```

Abrir <http://127.0.0.1:8000/login/>. En una copia de prueba, validar Cliente →
solicitud → aprobación administrativa → salida (unidad Alquilado) → retorno
(unidad Disponible). Comprobar mantenimiento como Técnico y los cuatro
reportes como Administrador: filtros y descarga `.xlsx`; no se ofrece CSV ni PDF.
Las pruebas manuales escriben datos: usar cuentas y unidades destinadas a pruebas.

Guías funcionales: [roles](cuentas-y-roles.md),
[salidas y retornos](hu09-salida-retorno.md), [reportes Excel](hu10-reportes.md)
y [utilidades](../scripts/README.md).

## Validación de la entrega

Comprobada el 31 de octubre de 2026 en Santo Domingo con Python 3.14.8:
`pip check`, `check`, coherencia de modelos/migraciones y ausencia de migraciones
pendientes, sin incidencias. La suite completa pasó **139 pruebas en SQL Server**
sin omisiones, en una base temporal única eliminada al terminar. Incluye
concurrencia de salidas/retornos, conservación de datos, respaldos reales y
exportaciones XLSX. Las migraciones históricas `0001`–`0007` se conservan intactas.
También se comprobó sintaxis Python/PowerShell y `git diff --check`.

La revisión de publicación no encontró secretos en los archivos candidatos;
la configuración privada, bases de datos, respaldos, entorno virtual, evidencias
y temporales están excluidos de Git. La suite automatizada no sustituye la
prueba manual anterior en la instalación del compañero.
