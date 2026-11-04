# Retirada de operadores y Supervisor

Validación: 30 de octubre de 2026, America/Santo_Domingo. Cambios locales,
sin commit, push ni publicación en GitHub.

## Alcance conservado y retirado

Se revisaron `git status`, el diff y los archivos nuevos de la sesión anterior.
Se conservaron sus cambios de roles, solicitudes y plantillas. El diff inicial
y una copia de sus archivos nuevos están en
`evidencias_locales/retirada_operadores_20261030/`, ignorado por Git
(trasladado desde `tmp` durante la limpieza del proyecto).

- Roles vigentes: Administrador, Cliente y Técnico de mantenimiento. La matriz
  de permisos está en [cuentas y roles](cuentas-y-roles.md).
- Operadores: retirados modelo activo, formulario, vistas, rutas, plantillas,
  navegación, permisos y acceso desde el panel. No hay registro, consulta ni
  asignación. Las antiguas rutas devuelven 404, incluso para Administrador.
- Supervisor: retirado como grupo y como fuente de permisos. La administración
  permanece en el Administrador. Las cuentas, hashes y atributos existentes se
  conservan; una cuenta que solo tenía un rol retirado queda sin rol.
- Se conservan las solicitudes añadidas localmente: Cliente solicita y consulta
  las propias; Administrador consulta todas, aprueba o rechaza y queda identificado
  como revisor. Técnico consulta maquinaria y registra/consulta mantenimiento.
- La importación desde SQLite no vuelve a crear Supervisor, Operador ni sus
  permisos. Se corrigió también el cierre de sus conexiones de lectura en Windows.
- HU-05 y HU-06 quedan **retiradas**, sin redactar reemplazos. Los documentos
  anteriores se identifican como antecedentes y las instrucciones vigentes se
  actualizan. No se modifica el documento Word.

## Migraciones

Las migraciones históricas `0001`–`0007` se conservaron sin modificar.

| Migración nueva | Resultado en `AlquilerEquipos` |
| --- | --- |
| `0008_roles_cliente` | Aplicada. Crea los grupos vigentes y retira Supervisor/Operador sin reasignar ni elevar cuentas. |
| `0009_retirar_operador` | Aplicada. Retira el modelo del estado de Django; conserva inicialmente la tabla SQL. |
| `0010_solicitudes_alquiler` | Aplicada. Crea la tabla de solicitudes ya preparada localmente. |
| `0011_eliminar_operador_sql` | Aplicada. Respalda y verifica antes de eliminar `dbo.Operador`; elimina sus permisos Django. |

`0011` comprueba FK entrantes, dependencias declaradas, definiciones de módulos
SQL (incluido texto de SQL dinámico), sinónimos y columnas externas que mencionen
operadores. Exige visibilidad completa mediante VIEW DEFINITION. Si encuentra
dependencias o no puede inspeccionarlas, se detiene para revisión sin eliminar
columnas o relaciones de alquileres, maquinaria o mantenimiento.

La operación crea automáticamente un respaldo completo en el directorio de
respaldos de la instancia, con `COPY_ONLY, CHECKSUM`, y ejecuta
`RESTORE VERIFYONLY ... WITH CHECKSUM, STOP_ON_ERROR`. Después bloquea la tabla,
revisa otra vez las dependencias y compara una huella de sus datos con la
anterior al respaldo. Si cambiaron, se detiene sin borrarlos. No tiene reversión
automática: recuperar operadores requiere restaurar su respaldo de forma controlada.
En SQLite solo admite retirar una tabla vacía; ante datos exige revisión.

El ContentType histórico de Operador se mantiene únicamente como metadato de
auditoría para no alterar logs. No conserva permisos, modelo activo ni rutas.

## Respaldo y comprobación de datos reales

Servidor revisado: `Thechosenone\SQLEXPRESS`, base `AlquilerEquipos`.
No había FK externas, vistas, funciones, procedimientos ni sinónimos que
dependieran de Operador. Solo figuraba la dependencia interna de su columna
calculada de cédula. No se encontraron columnas de operadores en otras tablas.

Directorio de los respaldos verificados:

```text
C:\Program Files\Microsoft SQL Server\MSSQL17.SQLEXPRESS\MSSQL\Backup\
```

| Momento | Archivo |
| --- | --- |
| Antes de `0008`, conserva también las membresías anteriores | `AlquilerEquipos_pre_retirada_operadores_20261030T223255Z_b1259734.bak` |
| Automático de `0011`, antes del DROP | `AlquilerEquipos_pre_retirada_operadores_20261030T223255Z_7cb186f9.bak` |

Ambos terminaron con verificación CHECKSUM correcta. Los nombres usan UTC;
la ejecución corresponde a las 18:32:55 del 30 de octubre en Santo Domingo.
No se realizó una restauración completa de estos archivos a otra base.

Se compararon nombres de columnas, recuentos y huellas SHA-256 de todos los
valores de las tablas ajenas antes y después. Resultado:

- **3 cuentas**: todas sus columnas, hashes, flags y actividad intactos.
- **4 categorías, 4 catálogos y 4 unidades**: sin cambios.
- **1 mantenimiento**, incluido su responsable: sin cambios.
- Alquiler y AlquilerDetalle: conservadas, ambas con 0 filas; también permanecen
  Cliente, Pago, Repuesto, MovimientoRepuesto, HistorialEstadoUnidad, Parametro,
  TipoDocumento y Reporte con sus datos originales.
- Sesiones y logs administrativos: sin cambios.
- Todas las FK anteriores y las definiciones de los módulos SQL: conservadas.
- Las membresías vigentes permanecen; solo se retiran las de los grupos retirados.
  No se asigna automáticamente Cliente ni Administrador.
- Se retira la tabla de **2 operadores**, recuperables desde los respaldos.
  La nueva tabla de solicitudes queda vacía, sin solicitudes de prueba en la base real.

El inventario sin datos personales, las huellas, el log de migraciones y el
resultado detallado están en `evidencias_locales/retirada_operadores_20261030/`,
fuera de Git.

## Verificaciones

- `manage.py check`: sin incidencias. `makemigrations --check --dry-run`: sin
  cambios pendientes. `migrate --check`: sin migraciones pendientes. Las once
  migraciones de usuarios figuran aplicadas. `git diff --check`: sin errores.
- Suite en SQL Server: **77 pruebas, OK**. Se aplica toda la cadena de migraciones
  en una base temporal, incluido el respaldo y la verificación reales de `0011`.
- Cobertura: autenticación, permisos por rol, maquinaria, mantenimiento, aislamiento
  de solicitudes por cliente, revisión administrativa, fechas, solapamientos,
  CSRF, ausencia de rutas de operadores y conservación de cuentas.
- Las pruebas nuevas comprueban el respaldo real y la retirada con datos,
  conservación de logs/permisos ajenos, repetición tras retirada, rechazo de FK,
  vistas y columnas externas sin FK, fallo de respaldo/verificación y cambios
  durante el respaldo. Los fallos se simulan cuando corresponde; la retirada
  correcta usa BACKUP y RESTORE VERIFYONLY reales.
- La prueba de importación verifica cuentas, hashes y actividad sin recrear
  roles retirados ni conceder sus permisos.
- Las bases temporales se eliminan al terminar. Sus respaldos de prueba quedan
  en el directorio SQL de respaldo y no se incluyen en Git.
- No quedaron migraciones ni pruebas de SQL Server sin ejecutar. Las pruebas
  no sustituyen una carga concurrente entre procesos ni una revisión visual del navegador.

## Repetir en otra instalación

1. Detener las escrituras y comprobar el destino en `config.local.json`, sin
   compartir credenciales. Ejecutar `sql/00_inspeccionar_base.sql` como consulta.
2. Crear y verificar un respaldo completo **antes de `0008`** para conservar
   también roles y membresías originales. Ejemplo para SSMS, ajustando una ruta
   nueva y accesible por el servicio SQL Server:

   ```sql
   BACKUP DATABASE [AlquilerEquipos]
   TO DISK = N'C:\ruta\nueva\AlquilerEquipos_antes_retiro.bak'
   WITH COPY_ONLY, CHECKSUM;
   RESTORE VERIFYONLY
   FROM DISK = N'C:\ruta\nueva\AlquilerEquipos_antes_retiro.bak'
   WITH CHECKSUM, STOP_ON_ERROR;
   ```

3. Usar una cuenta SQL con permisos de inspección, respaldo, verificación y
   migración. Aplicar:

   ```powershell
   .\.venv\Scripts\python.exe manage.py migrate --plan
   .\.venv\Scripts\python.exe manage.py migrate --noinput
   .\.venv\Scripts\python.exe manage.py check
   .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
   .\.venv\Scripts\python.exe manage.py migrate --check
   .\.venv\Scripts\python.exe manage.py test usuarios --noinput
   ```

4. Conservar la ruta del respaldo impresa por `0011` y comparar los datos ajenos.
   Si hay dependencias, revisar su significado antes de preparar otra migración;
   no usar `--fake` ni eliminar relaciones para eludir el bloqueo. Las migraciones
   previas pueden haber quedado aplicadas; no deshacerlas borrando datos.

## Prueba manual

Iniciar con `manage.py runserver` y abrir <http://127.0.0.1:8000/login/>.
Para cuentas de prueba, usar `crear_cliente cliente_prueba` y
`crear_tecnico tecnico_prueba`, después `changepassword` para cada cuenta.
Usar una unidad destinada a pruebas; registrar mantenimiento cambia su estado.

1. **Administrador:** consultar y editar maquinaria, consultar/registrar mantenimiento
   y abrir Gestionar solicitudes. Debe poder aprobar o rechazar las pendientes.
2. **Cliente:** consultar maquinaria, abrir una unidad Disponible, solicitar fechas
   futuras y revisar Mis solicitudes. No debe ver solicitudes de otro cliente ni
   poder editar maquinaria o acceder a mantenimiento por URL.
3. **Administrador:** aprobar la solicitud; el cliente debe ver el nuevo estado.
   Una segunda solicitud para fechas solapadas no se debe poder aprobar. La
   aprobación no emite contratos ni cambia por sí sola el estado a Alquilado.
4. **Técnico:** consultar maquinaria, registrar mantenimiento y reabrir su historial,
   verificando responsable y estado En mantenimiento. No debe gestionar solicitudes
   ni editar maquinaria.
5. **Cuenta anterior solo Supervisor/Operador:** debe conservar su acceso con la
   misma contraseña y mostrar Sin rol asignado; los datos de negocio devuelven 403.
   La asignación de un rol nuevo corresponde al Administrador.
6. Con cualquier rol, `/operadores/`, `/operadores/registrar/` y `/operadores/1/`
   deben devolver 404 y no aparecer enlaces de operadores en el panel.

Referencias del mecanismo de respaldo: [BACKUP de Microsoft](https://learn.microsoft.com/en-us/sql/t-sql/statements/backup-transact-sql?view=sql-server-ver17)
y [RESTORE VERIFYONLY](https://learn.microsoft.com/en-us/sql/t-sql/statements/restore-statements-verifyonly-transact-sql?view=sql-server-ver17).
