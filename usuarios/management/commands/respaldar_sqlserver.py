"""Respaldo completo verificable, sin cambiar el esquema ni los datos de negocio."""
import re
import uuid
from datetime import datetime, timezone
from pathlib import PureWindowsPath

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Crea un respaldo COPY_ONLY con CHECKSUM y ejecuta RESTORE VERIFYONLY.'

    def add_arguments(self, parser):
        parser.add_argument('--motivo', default='manual', help='Etiqueta breve para identificar el respaldo.')

    def handle(self, *args, **options):
        motivo = options['motivo']
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', motivo):
            raise CommandError('El motivo debe tener de 1 a 40 letras, números, guiones o guiones bajos.')
        if connection.vendor != 'microsoft':
            raise CommandError('Este comando requiere SQL Server.')
        if connection.in_atomic_block or not connection.get_autocommit():
            raise CommandError('El respaldo requiere una conexión sin transacción activa.')
        with connection.cursor() as cursor:
            cursor.execute("SELECT DB_NAME(), CONVERT(nvarchar(4000), SERVERPROPERTY('InstanceDefaultBackupPath'))")
            base, directorio = cursor.fetchone()
            if not directorio:
                raise CommandError('SQL Server no informa su directorio de respaldos.')
            nombre = re.sub(r'[^\w.-]', '_', base)
            sello = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            fichero = f'{nombre}_{motivo}_{sello}_{uuid.uuid4().hex[:8]}.bak'
            archivo = (
                str(PureWindowsPath(directorio) / fichero) if '\\' in directorio
                else directorio.rstrip('/') + '/' + fichero
            )
            cursor.execute(
                'BACKUP DATABASE ' + connection.ops.quote_name(base)
                + ' TO DISK = %s WITH COPY_ONLY, CHECKSUM', [archivo],
            )
            while cursor.nextset():
                pass
            cursor.execute('RESTORE VERIFYONLY FROM DISK = %s WITH CHECKSUM, STOP_ON_ERROR', [archivo])
            while cursor.nextset():
                pass
        self.stdout.write(self.style.SUCCESS('Respaldo verificado con CHECKSUM:'))
        return archivo
