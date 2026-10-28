/* Solo lectura. Ejecutar antes de cualquier cambio. */
USE [AlquilerEquipos];
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
                 'AlquilerDetalle', 'Mantenimiento', 'auth_user', 'django_migrations')
ORDER BY t.name, c.column_id;
GO
