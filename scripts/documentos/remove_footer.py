from pathlib import Path
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

root=Path(__file__).resolve().parents[2]
target=root/'output/pdf/Muestra_sin_primera_hoja.pdf'
reader=PdfReader(target)
writer=PdfWriter()
for page in reader.pages:
    width,height=float(page.mediabox.width),float(page.mediabox.height)
    layer=BytesIO()
    drawing=canvas.Canvas(layer,pagesize=(width,height))
    drawing.setFillColor(colors.white)
    drawing.rect(0,0,width,35,stroke=0,fill=1)
    drawing.save()
    layer.seek(0)
    page.merge_page(PdfReader(layer).pages[0])
    writer.add_page(page)
writer.add_metadata({'/Title':'Sistema de alquiler de equipos'})
temporary=root/'tmp/pdfs/no_footer.pdf'
with temporary.open('wb') as stream:
    writer.write(stream)
temporary.replace(target)
print(f'Actualizadas {len(writer.pages)} páginas.')
