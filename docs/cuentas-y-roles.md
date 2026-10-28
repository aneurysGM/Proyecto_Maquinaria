# Cuentas y roles

Todas las cuentas usan `/login/` y llegan a `/dashboard/`. El nombre mostrado
es el nombre y apellido guardados en Django; si están vacíos, se muestra el
nombre de usuario. La cuenta administrativa existente se conserva separada.

| Cuenta o rol | Panel | Consultar y filtrar maquinaria / detalles | Registrar maquinaria | Django Admin |
| --- | --- | --- | --- | --- |
| Administrador (`is_superuser=True`, `is_staff=True`) | Administrador | Sí | Sí | Sí |
| Grupo `Supervisor` | Supervisor | Sí | No | No, con `is_staff=False` |
| Grupo `Técnico` | Técnico | Sí | No | No, con `is_staff=False` |
| Usuario sin rol | Sin rol asignado | No | No | No, con `is_staff=False` |

El acceso de Supervisor se ha definido como solo consulta para las funciones
actualmente implementadas. La política de la aplicación está en
`usuarios/roles.py`: pertenecer al grupo `Supervisor` habilita consulta y ser
superusuario habilita registro de maquinaria y operadores. Técnico permite
registrar y consultar mantenimiento por unidad; Supervisor no obtiene ese acceso.
No se necesitan permisos individuales de Django.
Las vistas comprueban esa política antes de consultar o escribir datos.

## Cuenta de supervisión

La cuenta local originalmente llamada `supervisor` se renombró a `luis` y
muestra el nombre Luis. Conserva su contraseña y grupo; no hace falta crear otra.
Las cuentas no se incluyen en Git: en una instalación nueva se crean después
de ejecutar las migraciones.

Se crea con este comando, desde la carpeta de `manage.py` en PowerShell:

```powershell
.\.venv\Scripts\python.exe manage.py crear_supervisor luis --nombre "Luis"
```

Crea `luis`, añade el grupo `Supervisor` y mantiene `is_staff=False` e
`is_superuser=False`. Una cuenta nueva tiene la contraseña inutilizable hasta
que su propietario establezca una. Para establecerla de forma interactiva:

```powershell
.\.venv\Scripts\python.exe manage.py changepassword luis
```

Después inicia sesión en `/login/` con `luis` y esa contraseña.

Para guardar el nombre real que se mostrará en pantalla:

```powershell
.\.venv\Scripts\python.exe manage.py crear_supervisor luis --nombre "Luis"
```

El comando se puede repetir: conserva una contraseña ya establecida. Si el
nombre corresponde a un usuario con privilegios administrativos, rechaza la
operación para no modificar esa cuenta. Si se omite el nombre de usuario,
el comando usa `supervisor`; para conservar el usuario local `luis`, indícalo
explícitamente como en los ejemplos.

## Otras cuentas de supervisión

```powershell
.\.venv\Scripts\python.exe manage.py crear_supervisor supervisor2 --nombre "Luis" --apellido "García"
.\.venv\Scripts\python.exe manage.py changepassword supervisor2
```

También puedes usar Django Admin con la cuenta del administrador: crea un
usuario, asigna su nombre y contraseña y selecciona el grupo `Supervisor`.
Deja **Activo** marcado y **Es staff** y **Estado de superusuario** desmarcados.
No asignes permisos individuales ni otros grupos administrativos. El supervisor
entra por `/login/`; la gestión de usuarios permanece en la cuenta administrativa.

## Cuenta de Técnico (HU-07)

La migración 0007 crea el grupo `Técnico`. Para crear una cuenta o asignar una
existente sin reemplazar su contraseña ni sus otros grupos:

```powershell
.\.venv\Scripts\python.exe manage.py crear_tecnico tecnico1 --nombre "Ana" --apellido "Pérez"
.\.venv\Scripts\python.exe manage.py changepassword tecnico1
```

`changepassword` es necesario para una cuenta nueva; si ya tiene contraseña,
puede conservarla omitiendo ese comando. La cuenta debe estar activa. El comando
no reactiva cuentas inactivas ni modifica cuentas `is_staff` o `is_superuser`.
Desde Django Admin también puede asignarse el grupo a una cuenta activa sin
marcar staff ni superusuario. La migración no crea cuentas personales.

Técnico puede consultar maquinaria, registrar mantenimiento y consultar el
historial de todas las unidades, incluso las desactivadas. No puede registrar
ni editar maquinaria, consultar operadores ni acceder a Django Admin.
El Administrador también puede registrar y consultar mantenimiento. La actividad
queda vinculada al usuario autenticado que la registra, aunque después cambie
su grupo. La eliminación de ese usuario queda protegida mientras tenga registros.

Los grupos son aditivos: una cuenta Supervisor a la que se añada Técnico
conserva los dos grupos; el panel muestra Técnico. Ninguna asignación de Técnico
quita permisos anteriores ni concede privilegios de administración.
