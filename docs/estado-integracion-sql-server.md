# Estado de la integración con SQL Server

Fecha de validación: 20 de octubre de 2026.

Este documento conserva la validación inicial. Actualización del 27 de octubre
de 2026: maquinaria, operadores y registro/historial de mantenimiento ya están
implementados en Django. Consultar README y `hu07-mantenimiento.md` para la
migración 0007 y las 69 pruebas actuales.

## Comprobado en este equipo

- SQL Server 2025 Express `17.0.1000.7`, instancia
  `Thechosenone\SQLEXPRESS`, accesible con autenticación integrada.
- Base existente `AlquilerEquipos` inspeccionada antes de cambios: estaba en
  línea y sus tablas de negocio no tenían filas.
- Respaldo SQL `COPY_ONLY` creado y validado con `RESTORE VERIFYONLY` en
  `C:\Program Files\Microsoft SQL Server\MSSQL17.SQLEXPRESS\MSSQL\Backup\AlquilerEquipos_pre_django_20261020_2125.bak`.
- Respaldos locales de `config.local.json`, `db.sqlite3` y el JSON creados en
  `tmp/backups/20261020-211605/` (ruta ignorada por Git).
- Backend `mssql-django==2.0.0` instalado con ODBC Driver 18.
- Migraciones aplicadas con `--fake-initial`: las tablas existentes se
  conservaron y las tablas de Django se añadieron.
- Correcciones legacy aplicadas: `AlquilerDetalle`, funciones, vistas y ocho
  procedimientos almacenados compilados con referencias a `Maquinaria`.
- Traslado aditivo: 2 usuarios, sus hashes y roles, y 2 unidades. Una segunda
  ejecución creó 0 registros y verificó que hashes, roles y unidades coinciden.
- `manage.py check` y `makemigrations --check --dry-run` sin errores.
- 10 pruebas pasaron sobre la base temporal SQL Server
  `test_AlquilerEquipos`: conexión, migraciones, login, roles, prohibición de
  registro por URL para Supervisor, registro por Administrador, filtros y
  detalles.

## Pendiente en cada equipo de un compañero

- Instalar SQL Server y ODBC Driver 18 si todavía no están presentes.
- Crear su `config.local.json` y ajustar instancia/autenticación local.
- Respaldar e inspeccionar su propia base antes de ejecutar migraciones.
- Ejecutar las migraciones y la importación si conserva datos SQLite/JSON.
- Ejecutar las pruebas para comprobar que su cuenta tiene permisos para crear la
  base temporal de pruebas.

No quedan comprobaciones de SQL Server pendientes en este entorno. Los módulos
de alquiler, pagos y reportes todavía no están implementados en
Django; sus objetos SQL corregidos se conservan como base para historias de
usuario futuras.
