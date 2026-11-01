from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH

root=Path(__file__).resolve().parents[2]
out=root/'output/documentos'
folder=out/'Diagramas_originales'
folder.mkdir(exist_ok=True)
names=['01_Diagrama_de_Flujo','02_Flujo_del_Cliente','03_Flujo_del_Administrador','04_Flujo_de_Facturacion','05_Flujo_del_Tecnico']
for name in names:
    if not (folder/f'{name}.png').is_file():
        raise FileNotFoundError(folder/f'{name}.png')
with ZipFile(out/'Diagramas_originales.zip','w',ZIP_DEFLATED) as z:
    for name in names:z.write(folder/f'{name}.png',f'{name}.png')
d=Document(out/'Casos_de_uso_mejorado.docx')
section=d.sections[1]
section.orientation=WD_ORIENT.PORTRAIT
section.page_width=Inches(8.5)
section.page_height=Inches(11)
picture=next(p for p in d.paragraphs if p._p.xpath('.//a:blip'))
heading=picture.insert_paragraph_before('Diagrama de Flujo','Heading 1')
heading.alignment=WD_ALIGN_PARAGRAPH.CENTER
heading.paragraph_format.keep_with_next=True
heading.paragraph_format.space_before=Pt(0)
heading.paragraph_format.space_after=Pt(6)
picture.clear()
picture.alignment=WD_ALIGN_PARAGRAPH.CENTER
picture.paragraph_format.space_after=Pt(0)
picture.add_run().add_picture(str(folder/'01_Diagrama_de_Flujo.png'),height=Inches(8.7))
d.save(out/'Casos_de_uso_diagramas_originales.docx')
context=out/'Contexto_casos_de_uso.md'
with context.open('a',encoding='utf-8') as f:
    f.write('\n## Actualización solicitada por el usuario\n\nSe restauró el primer diagrama original, conservando su estructura y colocando el título Diagrama de Flujo arriba. La versión vigente es `Casos_de_uso_diagramas_originales.docx`; el diagrama se ajusta proporcionalmente a una página vertical, sin deformación. Los cinco PNG originales están en `Diagramas_originales` y en `Diagramas_originales.zip`. Son imágenes del documento fuente, sin formas ni conectores editables por separado. La vista general simplificada de `Casos_de_uso_mejorado.docx` quedó como una versión anterior, no como la versión vigente.\n')
print(out/'Casos_de_uso_diagramas_originales.docx')
