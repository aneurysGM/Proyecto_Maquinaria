from pathlib import Path
from html import escape
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION_START, WD_ORIENT
import subprocess

root=Path(__file__).resolve().parents[2]
out=root/'output/documentos'
src=Document(out/'Casos_de_uso_original.docx')
svg=[]
svg.append('<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1240" viewBox="0 0 1800 1240"><defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#475569"/></marker></defs><rect width="1800" height="1240" fill="white"/>')
def text(x,y,lines,size=22,bold=False):
    if isinstance(lines,str): lines=lines.split('\n')
    for i,t in enumerate(lines):
        svg.append(f'<text x="{x}" y="{y+i*(size+6)}" text-anchor="middle" font-family="Arial" font-size="{size}" font-weight="{700 if bold else 400}" fill="#172033">{escape(t)}</text>')
def box(x,y,w,h,label,kind='process',size=22):
    fill={'process':'#f4f6fa','end':'#e6edf7','decision':'#fff7e4','role':'#dce8f7'}[kind]
    if kind=='decision':
        svg.append(f'<polygon points="{x+w/2},{y} {x+w},{y+h/2} {x+w/2},{y+h} {x},{y+h/2}" fill="{fill}" stroke="#475569" stroke-width="2"/>')
    else:
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2 if kind=="end" else 7}" fill="{fill}" stroke="#475569" stroke-width="2"/>')
    lines=label.split('\n')
    text(x+w/2,y+h/2-(len(lines)-1)*(size+6)/2+size*.34,lines,size,kind=='role')
def arrow(points,label=None,lx=None,ly=None,dashed=False):
    pts=' '.join(f'{x},{y}' for x,y in points)
    svg.append(f'<polyline points="{pts}" fill="none" stroke="#475569" stroke-width="2.5" marker-end="url(#arrow)"'+(' stroke-dasharray="8 6"' if dashed else '')+'/>')
    if label: text(lx,ly,label,19)

text(900,45,'Diagrama de Flujo',34,True)
text(900,80,'Sistema de Gestión de Maquinaria Pesada y Alquileres',23)
box(35,145,130,52,'Inicio','end')
box(210,120,205,102,'¿Tiene\ncuenta?','decision',22)
arrow([(165,171),(210,171)])
box(485,140,240,62,'CU-02 Iniciar sesión')
arrow([(415,171),(485,171)],'Sí',449,155)
box(220,275,220,72,'CU-01 Registrarse\ny validar datos')
arrow([(312,222),(312,275)],'No',340,252)
arrow([(440,311),(605,311),(605,202)],'Registro válido',535,295)
text(330,378,'Si hay errores, corregir\ny repetir el registro',18)
box(795,115,240,112,'¿Credenciales\nválidas?','decision')
arrow([(725,171),(795,171)])
box(795,275,240,72,'Mostrar error\ny corregir datos')
arrow([(915,227),(915,275)],'No',942,252)
arrow([(795,311),(760,311),(760,237),(605,237),(605,202)])
box(1120,140,225,62,'Identificar rol')
arrow([(1035,171),(1120,171)],'Sí',1074,154)
arrow([(1345,171),(1750,171),(1750,410),(225,410)])
centers=[225,675,1125,1575]
roles=['Cliente','Administrador','Facturación','Técnico']
for cx,role in zip(centers,roles):
    arrow([(cx,410),(cx,450)])
    box(cx-190,450,380,56,role,'role',25)
    box(cx-190,540,380,58,'Seleccionar una operación',size=22)
    arrow([(cx,506),(cx,540)])

ops=[
    ['CU-07 Consultar maquinaria','CU-11 Solicitar alquiler','CU-13 Consultar estado del alquiler','CU-17 Consultar facturas'],
    ['CU-04 / 05 Registrar o consultar cliente','CU-06 / 07 Registrar o consultar equipo','CU-08 Actualizar estado de maquinaria','CU-09 / 10 Registrar o asignar operador','CU-12 Aprobar alquiler','CU-14 Registrar devolución','CU-20 / 21 Documentos y reportes'],
    ['CU-05 Consultar cliente','CU-15 Generar factura','CU-16 Registrar pago','CU-17 Consultar facturas'],
    ['CU-07 Consultar maquinaria','CU-18 Registrar mantenimiento','CU-19 Gestionar repuestos','CU-20 Gestionar documentos']
]
for cx,items in zip(centers,ops):
    box(cx-190,635,380,270,'\n'.join(items),size=18)
    arrow([(cx,598),(cx,635)])
    arrow([(cx,905),(cx,955)])
text(900,1210,'Cada bloque muestra opciones del rol; no exige ejecutarlas todas ni en ese orden.',18)
svg.append('<path d="M225 955 H1575" fill="none" stroke="#475569" stroke-width="2.5"/>')
box(760,982,280,93,'¿Otra operación?','decision',22)
arrow([(900,955),(900,982)])
arrow([(1040,1028),(1765,1028),(1765,520),(225,520)],'Sí',1700,1013)
for cx in centers:
    arrow([(cx,520),(cx,540)],dashed=True)
box(760,1110,280,55,'CU-03 Cerrar sesión','end',22)
arrow([(900,1075),(900,1110)],'No',930,1097)
box(1130,1110,130,55,'Fin','end')
arrow([(1040,1137),(1130,1137)])
text(385,1030,'Validar los datos de la operación.',19)
text(385,1060,'Si hay errores, corregir y volver a intentar.',19)
text(385,1090,'CU-21 Reportes según los permisos del rol.',19)
svg.append('</svg>')
svg_path=out/'Diagrama_de_Flujo.svg'
svg_path.write_text('\n'.join(svg),encoding='utf-8')
node=r'C:\Users\jorgu\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
sharp=r'C:/Users/jorgu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp'
subprocess.run([node,'-e',f"require('{sharp}')(process.argv[1],{{density:180}}).png().toFile(process.argv[2])",str(svg_path),str(out/'Diagrama_de_Flujo.png')],check=True)

# Conservar el contenido del compañero y dar a cada diagrama su propia página.
d=Document()
for st in d.styles:
    for border in st.element.xpath('.//w:pBdr'):
        border.getparent().remove(border)
    for rf in st.element.xpath('.//w:rFonts'):
        for attr in list(rf.attrib):
            if attr.endswith('Theme'):del rf.attrib[attr]
for name in ['Normal','Title','Heading 1','Heading 2']:
    st=d.styles[name];st.font.name='Times New Roman';st.font.color.rgb=RGBColor(0,0,0)
d.styles['Normal'].font.size=Pt(12)
d.styles['Normal'].paragraph_format.space_after=Pt(6)
d.styles['Normal'].paragraph_format.line_spacing=1.08
d.styles['Heading 1'].font.size=Pt(14)
d.styles['Heading 2'].font.size=Pt(12)
d.styles['Title'].font.size=Pt(18)
def setup(s,landscape=False):
    s.orientation=WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    s.page_width=Inches(11 if landscape else 8.5)
    s.page_height=Inches(8.5 if landscape else 11)
    s.top_margin=s.bottom_margin=Inches(.65)
    s.left_margin=s.right_margin=Inches(.7)
setup(d.sections[0])
for i in range(0,26):
    t=src.paragraphs[i].text.strip()
    if not t or t=='.':continue
    if i in [14,23]: t=t.rstrip() + '.'
    if i==17:d.add_page_break()
    if i==0: p=d.add_paragraph(t,'Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    elif i==1: p=d.add_paragraph(t);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    elif i in [4,7]: d.add_heading(t,1)
    elif i in [8,12,17,21]:d.add_heading(t,2)
    else:d.add_paragraph(t)
d.add_page_break()
d.add_heading('Índice de Casos de Uso',1)
for i in range(29,50):
    p=d.add_paragraph(src.paragraphs[i].text.strip());p.paragraph_format.space_after=Pt(4)
s=d.add_section(WD_SECTION_START.NEW_PAGE);setup(s,True)
# El título está integrado en el gráfico para conservarlo al compartir la imagen.
p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after=Pt(0)
p.add_run().add_picture(str(out/'Diagrama_de_Flujo.png'),width=Inches(9.6))
s=d.add_section(WD_SECTION_START.NEW_PAGE);setup(s)
role_specs=[
    ('1 Flujo del Cliente', '02_Flujo_del_Cliente.png'),
    ('2 Flujo del Administrador', '03_Flujo_del_Administrador.png'),
    ('3 Flujo del Encargado de Facturación', '04_Flujo_de_Facturacion.png'),
    ('4 Flujo del Técnico', '05_Flujo_del_Tecnico.png'),
]
for j,(title,img) in enumerate(role_specs):
    if j:d.add_page_break()
    d.add_heading(title,1)
    p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(out/'Diagramas_originales'/img),height=Inches(8.65))
d.add_page_break();d.add_heading('Conclusión',1)
for i in [113,114]:d.add_paragraph(src.paragraphs[i].text.strip())
d.save(out/'Casos_de_uso_mejorado.docx')
print(out/'Casos_de_uso_mejorado.docx')
