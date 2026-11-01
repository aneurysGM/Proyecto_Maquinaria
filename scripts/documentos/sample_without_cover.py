from pathlib import Path
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

root=Path(__file__).resolve().parents[2]
source=root/'output/pdf/Contexto_sistema_alquiler_equipos.pdf'
target=root/'output/pdf/Muestra_sin_primera_hoja.pdf'
pdfmetrics.registerFont(TTFont('TNR',r'C:\Windows\Fonts\times.ttf'))
reader=PdfReader(source)
writer=PdfWriter()
for number,page in enumerate(reader.pages[1:],1):
    w,h=float(page.mediabox.width),float(page.mediabox.height)
    overlay=BytesIO()
    c=canvas.Canvas(overlay,pagesize=(w,h))
    c.setFillColor(colors.white)
    c.rect(0,0,w,34,stroke=0,fill=1)
    c.setStrokeColor(colors.HexColor('#DCE3EC'))
    c.setLineWidth(.5)
    c.line(38,31,w-38,31)
    c.setFillColor(colors.HexColor('#596B80'))
    c.setFont('TNR',12)
    c.drawString(40,15,'CONTEXTO DEL PROYECTO  |  Sistema de alquiler de equipos')
    c.drawRightString(w-40,15,str(number))
    c.save()
    overlay.seek(0)
    page.merge_page(PdfReader(overlay).pages[0])
    writer.add_page(page)
writer.add_metadata({'/Title':'Sistema de alquiler de equipos - muestra sin primera hoja'})
with target.open('wb') as f: writer.write(f)
print(target)
print('Páginas:',len(writer.pages))
