from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, PageBreak
from pypdf import PdfReader, PdfWriter

root=Path(__file__).resolve().parents[2]
target=root/'output/pdf/Contexto_sistema_alquiler_equipos.pdf'
tmp=root/'tmp/pdfs'
tmp.mkdir(parents=True,exist_ok=True)
for name,file in [('TNR','times.ttf'),('TNR-Bold','timesbd.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(Path(r'C:\Windows\Fonts')/file)))
navy=colors.HexColor('#14243A')
body=ParagraphStyle('body',fontName='TNR',fontSize=12,leading=15,textColor=colors.HexColor('#263445'),spaceAfter=8)
heading=ParagraphStyle('heading',fontName='TNR-Bold',fontSize=14,leading=17,textColor=navy,spaceAfter=6)
qa=[
('¿Qué información técnica considera indispensable al presentar un equipo de maquinaria pesada para alquiler o venta?', 'Se debe presentar la capacidad del equipo, su rendimiento, vida útil, resistencia y durabilidad. También deben indicarse sus características técnicas según las especificaciones del fabricante.'),
('¿Qué capacidad de carga, capacidad del cubo y rendimiento debe tener el equipo para realizar los trabajos de su empresa?', 'Es necesario informar la capacidad del equipo en toneladas y, si se trata de una retroexcavadora, la capacidad de su cubo. Estos datos permiten determinar si el equipo puede realizar el trabajo requerido. El cliente mencionó distintas capacidades como ejemplos, aunque algunas cifras no quedaron claras en la transcripción.'),
('¿En qué terrenos y con qué materiales trabajaría el equipo?', 'El equipo podría utilizarse en zonas rocosas, trabajos con caliche y extracción de agregados. Por eso, se debe explicar su capacidad y rendimiento frente a los diferentes terrenos y materiales.'),
('¿Qué accesorios o implementos necesitaría y para qué trabajos los utilizaría?', 'El cliente mencionó el uso de un martillo para trabajos de extracción de agregados. Se debe informar qué implementos puede utilizar el equipo y cuáles son adecuados para cada trabajo.'),
('¿Qué importancia tienen la vida útil, la durabilidad y la resistencia del equipo al momento de elegirlo?', 'Son características que deben presentarse al ofrecer el equipo. La empresa necesita conocer cuánto puede durar y qué resistencia ofrece, tomando como referencia las especificaciones del fabricante.'),
('¿Cómo influye en su elección que el equipo utilice orugas o ruedas?', 'Se debe especificar si el equipo utiliza orugas o ruedas, porque esta característica forma parte de su configuración y de su capacidad para trabajar en distintos terrenos.'),
('¿Cada cuánto tiempo debería realizarse el mantenimiento preventivo y qué información necesita conocer sobre este?', 'Al presentar el equipo, se debe indicar cada cuánto tiempo necesita mantenimiento preventivo. El cliente no estableció un intervalo concreto; señaló que esa información debe proporcionarse según el equipo.'),
('¿Qué tendría que ofrecer una marca menos reconocida para que su empresa la elija frente a marcas conocidas?', 'Se debe demostrar la calidad y funcionalidad del equipo y explicar qué ventajas ofrece frente a marcas reconocidas, como Caterpillar y John Deere. Si la marca es poco conocida en el país, la empresa necesita razones claras para elegirla frente a las opciones que ya tienen reconocimiento en el mercado.'),
('¿Qué disponibilidad de repuestos y suplidores locales espera encontrar para mantener el equipo en funcionamiento?', 'Es importante que los repuestos puedan conseguirse con facilidad y que existan suplidores locales. El cliente mencionó componentes de recambio como mangueras, rodamientos y tornillos, y señaló que debe conocerse dónde adquirirlos.'),
('¿Qué apoyo técnico y capacitación necesita para utilizar y mantener el equipo?', 'El equipo debería contar con un sistema de diagnóstico que permita conectarlo a una computadora y detectar fallas rápidamente. También se necesita un manual para capacitar a los operadores. Al adquirir el equipo, la empresa podría solicitar que un especialista del extranjero imparta capacitación sobre su uso, manejo y operación.')
]
original=PdfReader(target)
start=3
def footer(canvas,doc):
    canvas.saveState()
    w,h=letter
    canvas.setFillColor(navy); canvas.rect(0,h-7,w,7,fill=1,stroke=0)
    canvas.setStrokeColor(colors.HexColor('#DCE3EC')); canvas.line(38,31,w-38,31)
    canvas.setFont('TNR',12); canvas.setFillColor(colors.HexColor('#596B80'))
    canvas.drawString(40,15,'CONTEXTO DEL PROYECTO  |  Sistema de alquiler de equipos')
    canvas.drawRightString(w-40,15,str(start+doc.page))
    canvas.restoreState()
story=[Paragraph('Preguntas y aportes del cliente',heading),Paragraph('Las siguientes preguntas se reconstruyeron a partir de las dos transcripciones compartidas. Debajo de cada una se presenta un resumen de lo expresado por el cliente.',body),Spacer(1,6)]
for i,(question,answer) in enumerate(qa,1):
    if i == 6:
        story.append(PageBreak())
    story.append(KeepTogether([Paragraph(f'{i}. {question}',heading),Paragraph(answer,body),Spacer(1,7)]))
appendix=tmp/'client_pages.pdf'
SimpleDocTemplate(str(appendix),pagesize=letter,leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=45).build(story,onFirstPage=footer,onLaterPages=footer)
writer=PdfWriter()
writer.append(original,pages=(0,3))
writer.append(PdfReader(appendix))
writer.add_metadata({'/Title':'Contexto del sistema de alquiler de equipos','/Author':'Documento de contexto del proyecto'})
new=tmp/'updated.pdf'
with new.open('wb') as f: writer.write(f)
new.replace(target)
check=PdfReader(target)
print(f'PDF actualizado: {len(check.pages)} páginas; {len(check.pages)-start} páginas añadidas.')
print('Preguntas incorporadas:',len(qa))
