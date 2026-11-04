"""Importa de forma aditiva cuentas SQLite y maquinaria JSON a SQL Server."""

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from usuarios.models import Categoria, Maquinaria, Unidad


GRUPOS_RETIRADOS = frozenset({'Supervisor', 'Operador'})


class Command(BaseCommand):
    help = (
        'Copia cuentas, hashes, roles y maquinaria local sin reemplazar registros '
        'que ya existan en la base de destino.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--sqlite',
            type=Path,
            default=settings.BASE_DIR / 'db.sqlite3',
            help='Base SQLite de origen.',
        )
        parser.add_argument(
            '--json',
            type=Path,
            default=settings.BASE_DIR / 'data' / 'maquinaria_provisional.json',
            help='Archivo JSON de maquinaria de origen.',
        )

    def handle(self, *args, **options):
        origen_sqlite = options['sqlite'].resolve()
        origen_json = options['json'].resolve()
        if connection.vendor == 'sqlite':
            raise CommandError('El destino activo es SQLite; configura SQL Server primero.')
        if not origen_sqlite.exists():
            raise CommandError(f'No existe la base SQLite: {origen_sqlite}')
        if not origen_json.exists():
            raise CommandError(f'No existe el archivo JSON: {origen_json}')

        with transaction.atomic():
            cuentas = self._migrar_cuentas(origen_sqlite)
            maquinaria = self._migrar_maquinaria(origen_json)
            self._verificar(origen_sqlite, origen_json)

        self.stdout.write(self.style.SUCCESS(
            'Migración aditiva completada: '
            f'{cuentas[0]} usuarios creados, {cuentas[1]} existentes; '
            f'{maquinaria[0]} unidades creadas, {maquinaria[1]} existentes.'
        ))
        self.stdout.write(self.style.SUCCESS(
            'Verificación correcta: usuarios, hashes, roles vigentes y unidades coinciden con el origen. '
            'Los roles retirados Supervisor y Operador no se importan.'
        ))

    def _migrar_cuentas(self, ruta):
        User = get_user_model()
        creados = existentes = 0
        with closing(sqlite3.connect(ruta)) as origen:
            origen.row_factory = sqlite3.Row
            tablas = {
                fila['name']
                for fila in origen.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            requeridas = {'auth_user', 'auth_group', 'auth_user_groups'}
            if not requeridas.issubset(tablas):
                faltantes = ', '.join(sorted(requeridas - tablas))
                raise CommandError(f'La base SQLite no contiene: {faltantes}')

            grupos = {}
            for fila in origen.execute('SELECT id, name FROM auth_group'):
                if fila['name'] in GRUPOS_RETIRADOS:
                    continue
                grupos[fila['id']], _ = Group.objects.get_or_create(name=fila['name'])

            usuarios = {}
            for fila in origen.execute('SELECT * FROM auth_user ORDER BY id'):
                usuario, creado = User.objects.get_or_create(
                    username=fila['username'],
                    defaults={
                        'password': fila['password'],
                        'last_login': self._fecha_hora(fila['last_login']),
                        'is_superuser': bool(fila['is_superuser']),
                        'first_name': fila['first_name'],
                        'last_name': fila['last_name'],
                        'email': fila['email'],
                        'is_staff': bool(fila['is_staff']),
                        'is_active': bool(fila['is_active']),
                        'date_joined': self._fecha_hora(fila['date_joined']),
                    },
                )
                usuarios[fila['id']] = usuario
                if creado:
                    creados += 1
                else:
                    existentes += 1
                    if usuario.password != fila['password']:
                        self.stderr.write(
                            f'Usuario {usuario.username}: ya existía; se conservó su hash destino.'
                        )

            for fila in origen.execute(
                'SELECT user_id, group_id FROM auth_user_groups'
            ):
                if fila['group_id'] in grupos:
                    usuarios[fila['user_id']].groups.add(grupos[fila['group_id']])

            if {'auth_permission', 'django_content_type'}.issubset(tablas):
                permisos = self._mapa_permisos(origen)
                if 'auth_group_permissions' in tablas:
                    for fila in origen.execute(
                        'SELECT group_id, permission_id FROM auth_group_permissions'
                    ):
                        permiso = permisos.get(fila['permission_id'])
                        if permiso and fila['group_id'] in grupos:
                            grupos[fila['group_id']].permissions.add(permiso)
                if 'auth_user_user_permissions' in tablas:
                    for fila in origen.execute(
                        'SELECT user_id, permission_id FROM auth_user_user_permissions'
                    ):
                        permiso = permisos.get(fila['permission_id'])
                        if permiso:
                            usuarios[fila['user_id']].user_permissions.add(permiso)
        return creados, existentes

    @staticmethod
    def _fecha_hora(valor):
        fecha = parse_datetime(valor) if valor else None
        if fecha is not None and timezone.is_naive(fecha):
            fecha = timezone.make_aware(fecha, timezone.get_default_timezone())
        return fecha

    @staticmethod
    def _mapa_permisos(origen):
        mapa = {}
        consulta = '''
            SELECT p.id, p.codename, c.app_label, c.model
            FROM auth_permission p
            JOIN django_content_type c ON c.id = p.content_type_id
        '''
        for fila in origen.execute(consulta):
            if fila['app_label'] == 'usuarios' and fila['model'] == 'operador':
                continue
            permiso = Permission.objects.filter(
                codename=fila['codename'],
                content_type__app_label=fila['app_label'],
                content_type__model=fila['model'],
            ).first()
            if permiso:
                mapa[fila['id']] = permiso
        return mapa

    def _migrar_maquinaria(self, ruta):
        try:
            registros = json.loads(ruta.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as error:
            raise CommandError(f'No se pudo leer {ruta}: {error}') from error
        if not isinstance(registros, list):
            raise CommandError('El JSON de maquinaria debe contener una lista.')

        creadas = existentes = 0
        campos_requeridos = {
            'codigo', 'nombre', 'categoria', 'costo_adquisicion',
            'tarifa_diaria', 'tarifa_semanal', 'tarifa_mensual',
            'deposito_garantia', 'numero_serie', 'estado', 'horas_uso',
        }
        for indice, datos in enumerate(registros, start=1):
            faltantes = campos_requeridos - datos.keys()
            if faltantes:
                raise CommandError(
                    f'Registro JSON {indice}: faltan {", ".join(sorted(faltantes))}.'
                )
            categoria = Categoria.objects.filter(
                nombre__iexact=datos['categoria']
            ).first()
            if categoria is None:
                categoria = Categoria.objects.create(nombre=datos['categoria'])

            maquinaria = Maquinaria.objects.filter(
                codigo__iexact=datos['codigo']
            ).first()
            if maquinaria is None:
                maquinaria = Maquinaria.objects.create(
                    categoria=categoria,
                    codigo=datos['codigo'],
                    nombre=datos['nombre'],
                    marca=datos.get('marca') or None,
                    modelo=datos.get('modelo') or None,
                    costo_adquisicion=Decimal(str(datos['costo_adquisicion'])),
                    tarifa_diaria=Decimal(str(datos['tarifa_diaria'])),
                    tarifa_semanal=Decimal(str(datos['tarifa_semanal'])),
                    tarifa_mensual=Decimal(str(datos['tarifa_mensual'])),
                    deposito_garantia=Decimal(str(datos['deposito_garantia'])),
                )

            unidad = Unidad.objects.filter(
                numero_serie__iexact=datos['numero_serie']
            ).first()
            if unidad is not None:
                existentes += 1
                self.stderr.write(
                    f'Unidad {datos["numero_serie"]}: ya existía; se conservó sin cambios.'
                )
                continue

            fecha = datos.get('fecha_adquisicion') or None
            Unidad.objects.create(
                maquinaria=maquinaria,
                numero_serie=datos['numero_serie'],
                estado=datos['estado'],
                horas_uso=Decimal(str(datos['horas_uso'])),
                fecha_adquisicion=date.fromisoformat(fecha) if fecha else None,
                identificador_legacy=(
                    uuid.UUID(datos['id']) if datos.get('id') else None
                ),
            )
            creadas += 1
        return creadas, existentes

    def _verificar(self, origen_sqlite, origen_json):
        User = get_user_model()
        errores = []
        with closing(sqlite3.connect(origen_sqlite)) as origen:
            origen.row_factory = sqlite3.Row
            for fila in origen.execute(
                'SELECT id, username, password, is_superuser, is_staff, is_active '
                'FROM auth_user'
            ):
                usuario = User.objects.filter(username=fila['username']).first()
                if usuario is None:
                    errores.append(f'falta el usuario {fila["username"]}')
                    continue
                if usuario.password != fila['password']:
                    errores.append(f'no coincide el hash de {fila["username"]}')
                if (
                    usuario.is_superuser != bool(fila['is_superuser'])
                    or usuario.is_staff != bool(fila['is_staff'])
                    or usuario.is_active != bool(fila['is_active'])
                ):
                    errores.append(f'no coinciden los atributos de {fila["username"]}')
                grupos_origen = {
                    grupo['name']
                    for grupo in origen.execute(
                        '''SELECT g.name FROM auth_group g
                           JOIN auth_user_groups ug ON ug.group_id = g.id
                           WHERE ug.user_id = ?''',
                        (fila['id'],),
                    )
                    if grupo['name'] not in GRUPOS_RETIRADOS
                }
                grupos_destino = set(
                    usuario.groups.values_list('name', flat=True)
                )
                if not grupos_origen.issubset(grupos_destino):
                    errores.append(f'faltan roles de {fila["username"]}')

        registros = json.loads(origen_json.read_text(encoding='utf-8'))
        for datos in registros:
            unidad = Unidad.objects.select_related(
                'maquinaria__categoria'
            ).filter(numero_serie__iexact=datos['numero_serie']).first()
            if unidad is None:
                errores.append(f'falta la unidad {datos["numero_serie"]}')
                continue
            valores_esperados = {
                'codigo': datos['codigo'],
                'nombre': datos['nombre'],
                'categoria': datos['categoria'],
                'marca': datos.get('marca') or '',
                'modelo': datos.get('modelo') or '',
                'estado': datos['estado'],
            }
            valores_destino = {
                'codigo': unidad.maquinaria.codigo,
                'nombre': unidad.maquinaria.nombre,
                'categoria': unidad.maquinaria.categoria.nombre,
                'marca': unidad.maquinaria.marca or '',
                'modelo': unidad.maquinaria.modelo or '',
                'estado': unidad.estado,
            }
            decimales_iguales = all(
                Decimal(str(destino)) == Decimal(str(datos[origen]))
                for destino, origen in (
                    (unidad.maquinaria.costo_adquisicion, 'costo_adquisicion'),
                    (unidad.maquinaria.tarifa_diaria, 'tarifa_diaria'),
                    (unidad.maquinaria.tarifa_semanal, 'tarifa_semanal'),
                    (unidad.maquinaria.tarifa_mensual, 'tarifa_mensual'),
                    (unidad.maquinaria.deposito_garantia, 'deposito_garantia'),
                    (unidad.horas_uso, 'horas_uso'),
                )
            )
            fecha_esperada = (
                date.fromisoformat(datos['fecha_adquisicion'])
                if datos.get('fecha_adquisicion') else None
            )
            if (
                any(
                    valores_destino[campo].casefold()
                    != valores_esperados[campo].casefold()
                    for campo in valores_esperados
                )
                or not decimales_iguales
                or unidad.fecha_adquisicion != fecha_esperada
            ):
                errores.append(f'no coincide la unidad {datos["numero_serie"]}')
        if errores:
            raise CommandError('Verificación fallida: ' + '; '.join(errores))
