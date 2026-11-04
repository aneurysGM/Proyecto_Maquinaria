"""Genera vistas PNG de un PDF conservando el documento de origen."""
import argparse
import os
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--dpi', type=int, default=120)
    parser.add_argument('--poppler-bin', type=Path, help='Carpeta de pdftoppm; también admite POPPLER_BIN.')
    parser.add_argument('--primera', type=int, default=1)
    parser.add_argument('--ultima', type=int)
    parser.add_argument('--contacto', action='store_true', help='Genera además contact.png; requiere Pillow.')
    opciones = parser.parse_args()
    if not opciones.pdf.is_file():
        parser.error('No existe el PDF de entrada.')
    if opciones.dpi <= 0 or opciones.primera < 1 or (opciones.ultima and opciones.ultima < opciones.primera):
        parser.error('Revisa la resolución y el intervalo de páginas.')
    carpeta = opciones.poppler_bin or os.environ.get('POPPLER_BIN')
    programa = shutil.which('pdftoppm', path=str(carpeta) if carpeta else None)
    if not programa:
        # Caché instalada en este equipo; el parámetro permite usar otra ubicación.
        cache = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin'
        programa = shutil.which('pdftoppm', path=str(cache))
    if not programa:
        parser.error('No se encontró pdftoppm. Instala Poppler o indica --poppler-bin.')
    if opciones.contacto:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            parser.error('--contacto requiere Pillow en el intérprete utilizado.')
    opciones.output_dir.mkdir(parents=True, exist_ok=True)
    comando = [programa, '-png', '-r', str(opciones.dpi), '-f', str(opciones.primera)]
    if opciones.ultima:
        comando.extend(['-l', str(opciones.ultima)])
    comando.extend([str(opciones.pdf.resolve()), str(opciones.output_dir.resolve() / 'page')])
    subprocess.run(comando, check=True)
    if opciones.contacto:
        paginas = sorted(opciones.output_dir.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
        lienzo = Image.new('RGB', (1280, 460 * ((len(paginas) + 3) // 4)), 'white')
        for indice, pagina in enumerate(paginas):
            with Image.open(pagina) as imagen:
                imagen.thumbnail((300, 430))
                miniatura = Image.new('RGB', (320, 460), '#dddddd')
                miniatura.paste(imagen, ((320 - imagen.width) // 2, 22))
                ImageDraw.Draw(miniatura).text((10, 4), str(indice + opciones.primera), fill='black')
                lienzo.paste(miniatura, ((indice % 4) * 320, (indice // 4) * 460))
        lienzo.save(opciones.output_dir / 'contact.png')
    print('Vistas generadas en:', opciones.output_dir.resolve())


if __name__ == '__main__':
    main()
