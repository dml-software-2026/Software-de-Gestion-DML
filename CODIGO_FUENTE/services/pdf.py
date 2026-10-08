import os
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from CODIGO_FUENTE.config import BASE_DIR
from CODIGO_FUENTE.extensions import get_db

# Mismo logo que usa la navbar de la app (INTERFAZ/static/logo.png) - #263.
LOGO_PATH = os.path.join(BASE_DIR, "INTERFAZ", "static", "logo.png")


def _cell(text, style):
    """Envuelve el valor de una celda en un Paragraph para que reportlab haga
    word-wrap dentro del ancho de columna. Texto plano en una Table de
    reportlab NO hace wrap por sí solo - si no entra en el ancho de la
    columna, se superpone con la celda de al lado en vez de bajar de
    renglón (#263 - reportado con "MOTOR DE ARRASTRE", "RUEDA DE ARRASTRE",
    y el estado nuevo del #260, más largo que el resto)."""
    valor = "" if text is None else str(text)
    return Paragraph(xml_escape(valor), style)


def generar_pdf_ficha(ficha_id: int) -> bytes:
    """Genera un PDF con la ficha de reparación completa - idéntico a la vista web.
    Función canónica de generación de PDF de ficha, usada por todos los
    endpoints que necesitan el PDF (issue #75). Reemplaza a las antiguas
    generar_ficha_pdf, generate_ficha_pdf y generate_ficha_pdf_new.
    """
    db = get_db()

    # Obtener datos de la ficha
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (ficha_id,)).fetchone()
    if not ficha:
        return None

    raypac = db.execute("SELECT * FROM raypac_entries WHERE id = %s", (ficha['raypac_id'],)).fetchone()
    partes = db.execute("SELECT * FROM dml_partes WHERE ficha_id = %s", (ficha_id,)).fetchall()
    repuestos = db.execute("SELECT * FROM dml_repuestos WHERE ficha_id = %s", (ficha_id,)).fetchall()

    # Crear PDF
    buffer = BytesIO()
    # #263: margen de 1,5 cm al borde en los 4 lados (pedido de David)
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    story = []

    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle('HeadingBox', parent=styles['Heading2'], fontSize=11,
                                   textColor=colors.darkblue, spaceAfter=3, fontName='Helvetica-Bold')
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=9)
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8)
    # Estilos de celda para _cell() - reemplazan el texto plano del resto de
    # las tablas para que hagan wrap en vez de superponerse (#263).
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8.5, leading=10)
    cell_style_bold = ParagraphStyle('CellBold', parent=cell_style, fontName='Helvetica-Bold')
    parts_header_style = ParagraphStyle('PartsHeader', parent=cell_style_bold, fontSize=8.5)
    parts_cell_style = ParagraphStyle('PartsCell', parent=styles['Normal'], fontSize=8, leading=9.5)

    # ENCABEZADO: N° Ficha | número | INFORME DML SOBRE EL EQUIPO EN REVISION
    header_data = [[
        Paragraph("<b>N° Ficha</b>", small_style),
        Paragraph(f"<b>{ficha['numero_ficha']:07d}</b>", small_style),
        Paragraph("<b>INFORME DML SOBRE EL<br/>EQUIPO EN REVISIÓN</b>", ParagraphStyle('Centered', parent=small_style, alignment=1))
    ]]
    header_table = Table(header_data, colWidths=[1.2*inch, 1.2*inch, 3.6*inch])
    header_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))

    # Logo de DML arriba a la derecha (mismo archivo que la navbar de la
    # app, INTERFAZ/static/logo.png). Ese archivo pesa ~480KB (resolución
    # pensada para la navbar) - se reescala acá a un tamaño chico y se
    # recomprime a JPEG antes de embeberlo, si no cada PDF quedaba +600KB
    # más pesado por una imagen que en la hoja se ve del tamaño de una
    # estampilla. Si el archivo no está o algo falla al procesarlo, se
    # sigue sin el logo en vez de romper la descarga del PDF.
    logo_cell = ""
    try:
        if os.path.exists(LOGO_PATH):
            pil_logo = PILImage.open(LOGO_PATH).convert("RGB")
            ancho_px = 330
            alto_px = round(ancho_px * pil_logo.height / pil_logo.width)
            pil_logo = pil_logo.resize((ancho_px, alto_px), PILImage.LANCZOS)
            logo_buffer = BytesIO()
            pil_logo.save(logo_buffer, format="JPEG", quality=88)
            logo_buffer.seek(0)
            logo_cell = Image(logo_buffer, width=1.1*inch, height=1.1*inch * alto_px / ancho_px)
    except Exception:
        logo_cell = ""

    # Ancho total de 7.1in: deja hueco visible dentro del frame de ~7.32in que
    # dejan los márgenes de 1.5cm (#263) - mismo ancho total que combo_table/
    # obs_table/rep_diag_table/marca_table/rep_table más abajo, para que todas
    # las tablas del PDF queden alineadas al mismo margen en los 4 lados.
    header_row = Table([[header_table, logo_cell]], colWidths=[6.0*inch, 1.1*inch])
    header_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(header_row)
    story.append(Spacer(1, 0.08*inch))
    story.append(Paragraph("<b>Servicio Técnico</b>", ParagraphStyle('Center', parent=normal_style, alignment=1)))
    story.append(Spacer(1, 0.15*inch))

    # INFORMACIÓN GENERAL (IZQUIERDA) + ESTADO DEL EQUIPO (DERECHA)
    # #263: valores envueltos con _cell() - texto como el estado nuevo del
    # #260 ("A LA ESPERA DE APROBACIÓN DE PRESUPUESTO") no entraba en una
    # sola línea de 2.2in y se superponía con la columna de al lado.
    info_rows = [
        [_cell("Ficha N°:", cell_style_bold), _cell(f"{ficha['numero_ficha']:07d}", cell_style)],
        [_cell("Ticket N°:", cell_style_bold), _cell(ficha['numero_ticket'] or "", cell_style)],
        [_cell("Fecha Ingreso DML:", cell_style_bold), _cell(ficha['fecha_ingreso'], cell_style)],
        [_cell("Fecha Egreso DML:", cell_style_bold), _cell(ficha['fecha_egreso'] or "", cell_style)],
        [_cell("Técnico Responsable:", cell_style_bold), _cell(ficha['tecnico_resp'] or "", cell_style)],
        [_cell("Estado:", cell_style_bold), _cell(ficha['estado_reparacion'], cell_style)],
    ]

    if raypac:
        info_rows.extend([
            [_cell("Fecha recepción Raypac:", cell_style_bold), _cell(raypac['fecha_recepcion'], cell_style)],
            [_cell("Cliente:", cell_style_bold), _cell(raypac['cliente'] or "", cell_style)],
            [_cell("N° Serie:", cell_style_bold), _cell(raypac['numero_serie'] or "", cell_style)],
            [_cell("Modelo:", cell_style_bold), _cell(raypac['modelo_maquina'] or "", cell_style)],
            [_cell("Tipo Máquina:", cell_style_bold), _cell(raypac['tipo_maquina'] or "", cell_style)],
            [_cell("Comercial responsable:", cell_style_bold), _cell(raypac['comercial'] or "", cell_style)],
            [_cell("Batería N°:", cell_style_bold), _cell(raypac['numero_bateria'] or "", cell_style)],
            [_cell("Cargador N°:", cell_style_bold), _cell(raypac['numero_cargador'] or "", cell_style)],
        ])

    left_table = Table(info_rows, colWidths=[2.2*inch, 2.2*inch])
    left_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ]))

    # Columna derecha: estado del equipo (partes). #263: nombres como "MOTOR
    # DE ARRASTRE"/"RUEDA DE ARRASTRE" no entraban en 1.2in de ancho en una
    # sola línea - _cell() los envuelve para que bajen de renglón en vez de
    # superponerse con la columna "Estado".
    parts_rows = [[_cell("PARTE", parts_header_style), _cell("Estado", parts_header_style)]]
    if partes:
        for p in partes:
            parts_rows.append([
                _cell(p['nombre_parte'] or "", parts_cell_style),
                _cell(p['estado'] or "POR INSPECCIONAR", parts_cell_style),
            ])
    else:
        for i in range(12):
            parts_rows.append([_cell("", parts_cell_style), _cell("", parts_cell_style)])

    right_table = Table(parts_rows, colWidths=[1.2*inch, 1.5*inch])
    right_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    # Combinar columnas en una tabla de dos columnas. #263: left_table (4.4in)
    # + right_table (2.7in) = 7.1in - antes sumaban 8.6in, más ancho que la
    # hoja entera (8.5in), así que esta tabla se comía el margen entero sin
    # importar qué valor tuviera topMargin/bottomMargin/leftMargin/rightMargin.
    combo_table = Table([[left_table, right_table]], colWidths=[4.4*inch, 2.7*inch])
    combo_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(combo_table)
    story.append(Spacer(1, 0.15*inch))

    # OBSERVACIONES - texto libre que puede ser largo (varias oraciones);
    # _cell() lo envuelve en líneas en vez de desbordar hacia afuera de la
    # tabla en una sola línea gigante.
    story.append(Paragraph("OBSERVACIONES", heading_style))
    obs_data = [[_cell(ficha['observaciones'] or "Ingreso reciente, pendiente inspección inicial", cell_style)]]
    obs_table = Table(obs_data, colWidths=[7.1*inch])
    obs_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('MINHEIGHT', (0, 0), (-1, -1), 0.5*inch),
    ]))
    story.append(obs_table)
    story.append(Spacer(1, 0.15*inch))

    # DIAGNÓSTICO DE REPARACIÓN - mismo motivo que OBSERVACIONES.
    story.append(Paragraph("DIAGNÓSTICO DE REPARACIÓN", heading_style))
    rep_diag_data = [[_cell(ficha['diagnostico_reparacion'] or "Pendiente", cell_style)]]
    rep_diag_table = Table(rep_diag_data, colWidths=[7.1*inch])
    rep_diag_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('MINHEIGHT', (0, 0), (-1, -1), 0.5*inch),
    ]))
    story.append(rep_diag_table)
    story.append(Spacer(1, 0.15*inch))

    # CICLOS Y DATOS FINALES
    story.append(Paragraph("CICLOS Y DATOS FINALES", heading_style))
    marca_rows = [
        [_cell("N° DE CICLOS DE LA MÁQUINA CON LAS QUE SALE DE ST", cell_style_bold), _cell(ficha['n_ciclos'] or 0, cell_style)],
        [_cell("TIPO DE MÁQUINA QUE INGRESO AL ST", cell_style_bold), _cell(raypac['tipo_maquina'] if raypac else "A BATERIA", cell_style)],
        [_cell("HORAS ADICIONALES DE TRABAJO", cell_style_bold), _cell(ficha['horas_adic'] or "NO APLICA", cell_style)],
        [_cell("MECANIZADO ADICIONAL REALIZADO A LA MAQUINA", cell_style_bold), _cell(ficha['mecanizado_adic'] or "NO APLICA", cell_style)],
        [_cell("TIPO DE TRABAJO REALIZADO", cell_style_bold), _cell(raypac['tipo_solicitud'] if raypac else "", cell_style)],
        [_cell("TÉCNICO RESPONSABLE DEL ST DE DML", cell_style_bold), _cell(ficha['tecnico_resp'] or "", cell_style)],
    ]

    marca_table = Table(marca_rows, colWidths=[5.8*inch, 1.3*inch])
    marca_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(marca_table)

    # REPUESTOS COLOCADOS (siempre en página 2+)
    story.append(PageBreak())
    story.append(Paragraph("REPUESTOS COLOCADOS", heading_style))

    if repuestos:
        rep_rows = [["Cantidad", "Código", "DESCRIPCION", "ESTADO", "EN STOCK", "EN FALTA"]]
        for rep in repuestos:
            rep_rows.append([
                str(rep['cantidad_utilizada'] or 1),
                rep['codigo_repuesto'] or "",
                (rep['descripcion'] or '')[:25],
                rep['estado_repuesto'] or "",
                "✓" if rep['en_stock'] else "",
                "✗" if rep['en_falta'] else ""
            ])

        rep_table = Table(rep_rows, colWidths=[0.8*inch, 1.2*inch, 2.3*inch, 1.0*inch, 0.9*inch, 0.9*inch])
        rep_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#808080')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8.5),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(rep_table)
    else:
        story.append(Paragraph("No se registraron repuestos en esta ficha.",
                                ParagraphStyle('Italic', parent=normal_style, fontName='Helvetica-Oblique')))

    story.append(Spacer(1, 0.15*inch))

    # Generar PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

    # Generar PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
