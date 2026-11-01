from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

root=Path(__file__).resolve().parents[2]
out=root/'output/pdf/Propuesta_Scrum_proyecto_final.pdf'
out.parent.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('TNR',r'C:\Windows\Fonts\times.ttf'))
pdfmetrics.registerFont(TTFont('TNR-Bold',r'C:\Windows\Fonts\timesbd.ttf'))
pdfmetrics.registerFontFamily('TNR',normal='TNR',bold='TNR-Bold')
body=ParagraphStyle('body',fontName='TNR',fontSize=12,leading=16,spaceAfter=8)
heading=ParagraphStyle('heading',fontName='TNR-Bold',fontSize=14,leading=18,spaceBefore=10,spaceAfter=7)
cell=ParagraphStyle('cell',fontName='TNR',fontSize=12,leading=15)
def p(text): return Paragraph(text,body)
def h(text): return Paragraph(text,heading)
story=[h('Propuesta de Scrum para el proyecto final'),p('<b>Proyecto:</b> sistema de alquiler de equipos.<br/><b>Equipo:</b> tres integrantes.<br/><b>Fecha de entrega:</b> 6 de diciembre de 2026.'),
 p('Esta propuesta organiza el trabajo desde el 7 de octubre hasta la entrega. Está pensada para un proyecto final de carrera cuyo resultado será un prototipo funcional que el equipo pueda demostrar y explicar. El alcance debe ajustarse a los requisitos de la asignatura y a las prioridades acordadas con el cliente.'),
 h('Objetivo y prioridades'),
 p('Desarrollar un sistema que permita consultar las características técnicas de los equipos, identificar sus unidades físicas y gestionar un flujo básico de alquiler. La ficha técnica tendrá prioridad por las necesidades expresadas por el cliente: capacidad, rendimiento, marca, implementos compatibles y mantenimiento.'),
 p('El alcance propuesto incluye equipos y unidades, búsqueda y estados, clientes, disponibilidad por fechas, alquileres, entregas y devoluciones. Pagos y mantenimiento se implementarán con un alcance básico. Los reportes avanzados y otras funciones adicionales dependerán del tiempo disponible y de los requisitos académicos.'),
 h('Organización de los tres integrantes'),
 p('Una distribución inicial del trabajo sería: un integrante se concentra en la base de datos; otro, en la interfaz; y el tercero, en la lógica del sistema y la integración. Los tres colaboran en la revisión, las pruebas y la presentación.'),
 p('Los tres forman el equipo de desarrollo. Uno asume además el rol de <b>Product Owner</b>: organiza el Product Backlog y mantiene las prioridades acordadas con el cliente. Otro asume el rol de <b>Scrum Master</b>: facilita las reuniones, ayuda a resolver obstáculos y acompaña la aplicación de Scrum. Los roles se asignarán por acuerdo del grupo.'),
 h('Cómo se trabajará en cada sprint'),
 p('<b>Planificación:</b> acordar el objetivo del sprint y seleccionar tareas según la capacidad real del equipo.<br/><b>Daily Scrum:</b> reunión diaria breve, de hasta 15 minutos, para revisar el avance y ajustar el trabajo.<br/><b>Revisión:</b> demostrar las funciones terminadas y recoger comentarios.<br/><b>Retrospectiva:</b> acordar mejoras en la forma de trabajar.'),
 PageBreak(),h('Cronograma propuesto')]
rows=[['Período','Objetivo y resultado esperado'],
 ['7–11 de octubre','Preparación: acordar el alcance, asignar roles y preparar el Product Backlog.'],
 ['Sprint 1\n12–25 de octubre','Registrar equipos y unidades; consultar la ficha técnica, buscar equipos y visualizar sus estados.'],
 ['Sprint 2\n26 de octubre–8 de noviembre','Registrar clientes, consultar disponibilidad por fechas y crear alquileres.'],
 ['Sprint 3\n9–22 de noviembre','Registrar entregas y devoluciones; incorporar pagos y mantenimiento básico.'],
 ['Sprint 4\n23 de noviembre–4 de diciembre','Completar la integración, corregir errores y preparar documentación y demostración. Entregar una versión funcional revisada.'],
 ['5 de diciembre','Revisión final, respaldo de los archivos y ensayo de la presentación.'],
 ['6 de diciembre','Entrega del proyecto final.']]
data=[[Paragraph(x.replace('\n','<br/>').replace('–','-'),cell) for x in row] for row in rows]
table=Table(data,colWidths=[155,373],hAlign='LEFT')
table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EEF1F5')),('GRID',(0,0),(-1,-1),.5,colors.HexColor('#BEC6D0')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
story.extend([table,Spacer(1,7),p('La preparación ocurre antes del primer sprint. Las fechas y el contenido son una propuesta: en cada planificación se seleccionará el trabajo que los tres integrantes puedan completar. Cada sprint debe producir una parte funcional y revisada del sistema; las comprobaciones se realizan durante todo el desarrollo.'),
 h('Evidencias de la aplicación de Scrum'),
 p('Conservar el <b>Product Backlog</b> ordenado por prioridad, el <b>Sprint Backlog</b> de cada sprint y un tablero con tareas pendientes, en proceso y terminadas. Registrar brevemente los acuerdos de planificación, seguimiento, revisión y retrospectiva, junto con capturas o demostraciones de los resultados.'),
 h('Cuándo se considera terminado el trabajo'),
 p('Una funcionalidad se considera terminada cuando cumple los criterios acordados, está integrada con la base de datos, cuenta con las validaciones necesarias, fue revisada y comprobada por el equipo y puede demostrarse funcionando. La documentación correspondiente debe reflejar su comportamiento.')])
SimpleDocTemplate(str(out),pagesize=letter,leftMargin=42,rightMargin=42,topMargin=35,bottomMargin=35,title='Propuesta Scrum para el proyecto final').build(story)
print(out)
