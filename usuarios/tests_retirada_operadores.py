"""Pruebas SQL reales de retirada, respaldo y protección de otros módulos."""
from importlib import import_module
from io import StringIO
from unittest import skipUnless
from unittest.mock import patch

from django.apps import apps
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, connection
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase

from .models import Mantenimiento, SolicitudAlquiler, Unidad
from .tests import crear_unidad


@skipUnless(connection.vendor == 'microsoft', 'Requiere SQL Server, incluido BACKUP y RESTORE VERIFYONLY')
class RetiradaOperadorSQLTests(TransactionTestCase):
    def setUp(self):
        self.migracion = import_module('usuarios.migrations.0011_eliminar_operador_sql')
        self.estado = ProjectState.from_apps(apps)
        self.unidad = crear_unidad()
        self.usuario = get_user_model().objects.create_user(username='cuenta_anterior', password='ClaveExistente123!')
        self.usuario.groups.add(Group.objects.create(name='Supervisor'))
        self.ct, _ = ContentType.objects.get_or_create(app_label='usuarios', model='operador')
        self.permiso = Permission.objects.create(content_type=self.ct, codename='view_operador', name='Consultar operador')
        self.usuario.user_permissions.add(self.permiso)
        self.log = LogEntry.objects.create(user=self.usuario, content_type=self.ct, object_id='1', object_repr='Registro histórico', action_flag=ADDITION)
        Mantenimiento.objects.create(unidad=self.unidad, tecnico=self.usuario, fecha='2026-01-01', tipo='Preventivo', descripcion='Conservar', costo=10)
        SolicitudAlquiler.objects.create(cliente=self.usuario, unidad=self.unidad, fecha_inicio='2026-11-01', fecha_fin='2026-11-02')
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE [dbo].[Operador] ([IdOperador] int PRIMARY KEY, [Nombre] nvarchar(80))')
            cursor.execute("INSERT INTO [dbo].[Operador] VALUES (1, N'Operador de prueba')")

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute('DROP VIEW IF EXISTS dbo.RetiradaVistaPrueba')
            cursor.execute('DROP TABLE IF EXISTS dbo.RetiradaReferenciaPrueba')
            cursor.execute('DROP TABLE IF EXISTS dbo.Operador')
        super().tearDown()

    def retirar(self):
        with connection.schema_editor(atomic=False) as editor:
            self.migracion.retirar_operador(self.estado.apps, editor)

    def valores_ajenos(self):
        return [list(modelo.objects.order_by('pk').values()) for modelo in (
            get_user_model(), Unidad, Mantenimiento, SolicitudAlquiler, LogEntry,
        )]

    def assert_operador_conservado(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT Nombre FROM dbo.Operador ORDER BY IdOperador')
            self.assertEqual([r[0] for r in cursor.fetchall()], ['Operador de prueba'])

    def test_respaldo_real_retira_tabla_permisos_y_roles_conservando_cuentas_y_negocio(self):
        antes = self.valores_ajenos()
        permiso_ajeno = Permission.objects.get(codename='add_user')
        self.usuario.user_permissions.add(permiso_ajeno)
        with patch('sys.stdout', new_callable=StringIO) as salida:
            self.retirar()
        self.assertIn('verificado con CHECKSUM:', salida.getvalue())
        self.assertNotIn('Operador', connection.introspection.table_names())
        self.assertFalse(Permission.objects.filter(pk=self.permiso.pk).exists())
        self.assertTrue(self.usuario.user_permissions.filter(pk=permiso_ajeno.pk).exists())
        self.assertTrue(ContentType.objects.filter(pk=self.ct.pk).exists())
        self.assertFalse(Group.objects.filter(name__in=['Supervisor', 'Operador']).exists())
        self.assertEqual(self.valores_ajenos(), antes)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('ClaveExistente123!'))
        self.assertFalse(self.usuario.groups.exists())
        # Repetir una ejecución parcial no necesita otro respaldo ni toca datos.
        with patch.object(self.migracion, 'respaldar_y_verificar') as respaldo:
            self.retirar()
        respaldo.assert_not_called()
        self.assertEqual(self.valores_ajenos(), antes)

    def test_fk_de_otro_modulo_detiene_retirada_sin_borrar_relacion_o_datos(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE dbo.RetiradaReferenciaPrueba (id int PRIMARY KEY, operador_id int REFERENCES dbo.Operador(IdOperador))')
            cursor.execute('INSERT INTO dbo.RetiradaReferenciaPrueba VALUES (1, 1)')
        with patch.object(self.migracion, 'respaldar_y_verificar') as respaldo:
            with self.assertRaisesMessage(RuntimeError, 'dependencias SQL'):
                self.retirar()
        respaldo.assert_not_called()
        self.assert_operador_conservado()
        with connection.cursor() as cursor:
            cursor.execute('SELECT operador_id FROM dbo.RetiradaReferenciaPrueba')
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_vista_dependiente_se_conserva_y_detiene_retirada(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE VIEW dbo.RetiradaVistaPrueba AS SELECT IdOperador FROM dbo.Operador')
        with self.assertRaisesMessage(RuntimeError, 'RetiradaVistaPrueba'):
            self.retirar()
        self.assert_operador_conservado()

    def test_columna_externa_sin_fk_requiere_revision_y_no_se_elimina(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE dbo.RetiradaReferenciaPrueba (id int PRIMARY KEY, OperadorID int)')
            cursor.execute('INSERT INTO dbo.RetiradaReferenciaPrueba VALUES (1, 1)')
        with self.assertRaisesMessage(RuntimeError, 'OperadorID'):
            self.retirar()
        self.assert_operador_conservado()

    def test_fallo_de_respaldo_o_verificacion_no_borra_tabla_permisos_ni_cuentas(self):
        antes = self.valores_ajenos()
        with patch.object(self.migracion, 'respaldar_y_verificar', side_effect=DatabaseError('Respaldo no verificado')):
            with self.assertRaisesMessage(DatabaseError, 'no verificado'):
                self.retirar()
        self.assert_operador_conservado()
        self.assertTrue(Permission.objects.filter(pk=self.permiso.pk).exists())
        self.assertTrue(Group.objects.filter(name='Supervisor').exists())
        self.assertEqual(self.valores_ajenos(), antes)

    def test_escritura_durante_respaldo_detiene_el_borrado(self):
        def escritura(connection):
            with connection.cursor() as cursor:
                cursor.execute("UPDATE dbo.Operador SET Nombre=N'Cambio concurrente' WHERE IdOperador=1")
        with patch.object(self.migracion, 'respaldar_y_verificar', side_effect=escritura):
            with self.assertRaisesMessage(RuntimeError, 'cambió durante el respaldo'):
                self.retirar()
        with connection.cursor() as cursor:
            cursor.execute('SELECT Nombre FROM dbo.Operador')
            self.assertEqual(cursor.fetchone()[0], 'Cambio concurrente')
