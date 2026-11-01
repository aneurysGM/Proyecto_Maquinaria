"""Comprueba Django y ejecuta las pruebas en una base temporal con nombre único."""
import argparse
import os
import sys
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pruebas', nargs='*', help='Etiquetas Django; por defecto, usuarios.')
    parser.add_argument('--solo-comprobaciones', action='store_true', help='No crear una base de pruebas.')
    opciones = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    sello = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    carpeta = ROOT / 'tmp' / 'verificaciones'
    carpeta.mkdir(parents=True, exist_ok=True)
    log = carpeta / f'django_{sello}_{uuid.uuid4().hex[:6]}.log'
    codigo = 0
    try:
        with log.open('w', encoding='utf-8') as salida, redirect_stdout(salida), redirect_stderr(salida):
            import django
            django.setup()
            from django.core.management import call_command
            from django.db import connection
            call_command('check')
            call_command('makemigrations', check=True, dry_run=True)
            # Solo consulta la base de trabajo; nunca ejecuta sus migraciones.
            call_command('migrate', check=True, interactive=False)
            if not opciones.solo_comprobaciones:
                connection.settings_dict['TEST']['NAME'] = 'test_verif_' + uuid.uuid4().hex[:10]
                print('Base temporal:', connection.settings_dict['TEST']['NAME'], flush=True)
                call_command('test', *(opciones.pruebas or ['usuarios']), interactive=False, verbosity=1)
    except SystemExit as error:
        codigo = error.code if isinstance(error.code, int) else 1
    except Exception:
        import traceback
        with log.open('a', encoding='utf-8') as salida:
            traceback.print_exc(file=salida)
        codigo = 1
    print('Registro completo:', log)
    print('\n'.join(log.read_text(encoding='utf-8').splitlines()[-12:]))
    return codigo


if __name__ == '__main__':
    raise SystemExit(main())
