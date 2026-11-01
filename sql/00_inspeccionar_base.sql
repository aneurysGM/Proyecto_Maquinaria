/* Solo lectura. Ejecutar antes de cualquier cambio. */
USE [AlquilerEquipos];
GO

/* Dependencias de operadores: no modificar ni eliminar objetos desde aquí. */
SELECT OBJECT_SCHEMA_NAME(c.object_id) AS Esquema,
       OBJECT_NAME(c.object_id) AS Objeto, c.name AS Columna
FROM sys.columns c
WHERE LOWER(c.name) LIKE '%operador%'
   OR LOWER(OBJECT_NAME(c.object_id)) LIKE '%operador%';

SELECT fk.name AS Relacion,
       OBJECT_SCHEMA_NAME(fk.parent_object_id) AS Esquema,
       OBJECT_NAME(fk.parent_object_id) AS Tabla,
       OBJECT_NAME(fk.referenced_object_id) AS Referencia
FROM sys.foreign_keys fk
WHERE fk.referenced_object_id = OBJECT_ID(N'dbo.Operador')
   OR fk.parent_object_id = OBJECT_ID(N'dbo.Operador');

SELECT OBJECT_SCHEMA_NAME(referencing_id) AS Esquema,
       OBJECT_NAME(referencing_id) AS Objeto,
       referenced_schema_name, referenced_entity_name
FROM sys.sql_expression_dependencies
WHERE referenced_id = OBJECT_ID(N'dbo.Operador')
   OR LOWER(referenced_entity_name) LIKE '%operador%';

SELECT OBJECT_SCHEMA_NAME(object_id) AS Esquema,
       OBJECT_NAME(object_id) AS Objeto, definition
FROM sys.sql_modules
WHERE LOWER(definition) LIKE '%operador%' OR definition IS NULL;

SELECT name, base_object_name FROM sys.synonyms
WHERE LOWER(base_object_name) LIKE '%operador%';
GO
SET NOCOUNT ON;

SELECT @@SERVERNAME AS Servidor,
       CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(50)) AS Version,
       DB_NAME() AS BaseActual;

SELECT t.name AS Tabla, SUM(p.rows) AS Filas
FROM sys.tables AS t
JOIN sys.partitions AS p
  ON p.object_id = t.object_id AND p.index_id IN (0, 1)
GROUP BY t.name
ORDER BY t.name;

SELECT t.name AS Tabla, c.column_id, c.name AS Columna, ty.name AS Tipo,
       c.max_length, c.precision, c.scale, c.is_nullable, c.is_identity
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id = t.object_id
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE t.name IN ('Categoria', 'Maquinaria', 'Unidad', 'Parametro',
                 'Alquiler', 'Cliente', 'AlquilerDetalle', 'HistorialEstadoUnidad',
                 'usuarios_solicitudalquiler', 'Mantenimiento', 'auth_user', 'django_migrations')
ORDER BY t.name, c.column_id;
GO
