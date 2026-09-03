from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from CODIGO_FUENTE.extensions import get_db


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
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.4*inch, bottomMargin=0.4*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    story = []

    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle('HeadingBox', parent=styles['Heading2'], fontSize=11,
                                   textColor=colors.darkblue, spaceAfter=3, fontName='Helvetica-Bold')
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=9)
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8)

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
    story.append(header_table)
    story.append(Spacer(1, 0.08*inch))
    story.append(Paragraph("<b>Servicio Técnico</b>", ParagraphStyle('Center', parent=normal_style, alignment=1)))
    story.append(Spacer(1, 0.15*inch))

    # INFORMACIÓN GENERAL (IZQUIERDA) + ESTADO DEL EQUIPO (DERECHA)
    info_rows = [
        ["Ficha N°:", f"{ficha['numero_ficha']:07d}"],
        ["Ticket N°:", ficha['numero_ticket'] or ""],
        ["Fecha Ingreso DML:", ficha['fecha_ingreso']],
        ["Fecha Egreso DML:", ficha['fecha_egreso'] or ""],
        ["Técnico Responsable:", ficha['tecnico_resp'] or ""],
        ["Estado:", ficha['estado_reparacion']],
    ]

    if raypac:
        info_rows.extend([
            ["Fecha recepción Raypac:", raypac['fecha_recepcion']],
            ["Cliente:", raypac['cliente'] or ""],
            ["N° Serie:", raypac['numero_serie'] or ""],
            ["Modelo:", raypac['modelo_maquina'] or ""],
            ["Tipo Máquina:", raypac['tipo_maquina'] or ""],
            ["Comercial responsable:", raypac['comercial'] or ""],
            ["Batería N°:", raypac['numero_bateria'] or ""],
            ["Cargador N°:", raypac['numero_cargador'] or ""],
        ])

    left_table = Table(info_rows, colWidths=[2.6*inch, 2.7*inch])
    left_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ]))

    # Columna derecha: estado del equipo (partes)
    parts_rows = [["PARTE", "Estado"]]
    if partes:
        for p in partes:
            parts_rows.append([p['nombre_parte'] or "", p['estado'] or "POR INSPECCIONAR"])
    else:
        for i in range(12):
            parts_rows.append(["", ""])

    right_table = Table(parts_rows, colWidths=[1.5*inch, 1.8*inch])
    right_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    # Combinar columnas en una tabla de dos columnas
    combo_table = Table([[left_table, right_table]], colWidths=[5.3*inch, 3.3*inch])
    combo_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(combo_table)
    story.append(Spacer(1, 0.15*inch))

    # DIAGNÓSTICO INICIAL
    story.append(Paragraph("DIAGNÓSTICO DEL DEPARTAMENTO TÉCNICO", heading_style))
    diag_data = [[ficha['diagnostico_inicial'] or "Pendida de potencia, cuchilla gastada"]]
    diag_table = Table(diag_data, colWidths=[6*inch])
    diag_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('MINHEIGHT', (0, 0), (-1, -1), 0.5*inch),
    ]))
    story.append(diag_table)
    story.append(Spacer(1, 0.15*inch))

    # OBSERVACIONES
    story.append(Paragraph("OBSERVACIONES", heading_style))
    obs_data = [[ficha['observaciones'] or "Ingreso reciente, pendiente inspección inicial"]]
    obs_table = Table(obs_data, colWidths=[6*inch])
    obs_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('MINHEIGHT', (0, 0), (-1, -1), 0.5*inch),
    ]))
    story.append(obs_table)
    story.append(Spacer(1, 0.15*inch))

    # DIAGNÓSTICO DE REPARACIÓN
    story.append(Paragraph("DIAGNÓSTICO DE REPARACIÓN", heading_style))
    rep_diag_data = [[ficha['diagnostico_reparacion'] or "Pendiente"]]
    rep_diag_table = Table(rep_diag_data, colWidths=[6*inch])
    rep_diag_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('MINHEIGHT', (0, 0), (-1, -1), 0.5*inch),
    ]))
    story.append(rep_diag_table)
    story.append(Spacer(1, 0.15*inch))

    # REPUESTOS COLOCADOS
    story.append(Paragraph("REPUESTOS COLOCADOS", heading_style))
    rep_rows = [["Cantidad", "Código", "DESCRIPCION", "ESTADO", "EN STOCK", "EN FALTA"]]
    if repuestos:
        for rep in repuestos:
            rep_rows.append([
                str(rep['cantidad_utilizada'] or 1),
                rep['codigo_repuesto'] or "",
                (rep['descripcion'] or '')[:25],
                rep['estado_repuesto'] or "",
                "✓" if rep['en_stock'] else "",
                "✗" if rep['en_falta'] else ""
            ])
    # Relleno hasta 10 filas
    while len(rep_rows) < 11:
        rep_rows.append(["", "", "", "", "", ""])

    rep_table = Table(rep_rows, colWidths=[0.7*inch, 1.0*inch, 2.0*inch, 0.9*inch, 0.8*inch, 0.7*inch])
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
    story.append(Spacer(1, 0.15*inch))

    # FILA SEPARADA - Ciclos
    story.append(Spacer(1, 0.05*inch))
    ciclos_rows = [["N° DE CICLOS DE LA MÁQUINA CON LAS QUE SALE DE ST", str(ficha['n_ciclos'] or 0)]]
    ciclos_table = Table(ciclos_rows, colWidths=[5.3*inch, 1.2*inch])
    ciclos_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
    ]))
    story.append(ciclos_table)
    story.append(Spacer(1, 0.15*inch))

    # MARCAR CON UNA CRUZ LO QUE CORRESPONDA
    story.append(Paragraph("MARCAR CON UNA CRUZ LO QUE CORRESPONDA", heading_style))
    marca_rows = [
        ["TIPO DE MÁQUINA QUE INGRESO AL ST", raypac['tipo_maquina'] if raypac else "A BATERIA"],
        ["El módulo reparación Base es de tres (3hs)", "A DEFINIR"],
        ["HORAS ADICIONALES DE TRABAJO", ficha['horas_adic'] or "NO APLICA"],
        ["MECANIZADO ADICIONAL REALIZADO A LA MAQUINA", ficha['mecanizado_adic'] or "NO APLICA"],
        ["TIPO DE TRABAJO REALIZADO", "REPARACIÓN"],
        ["TÉCNICO RESPONSABLE DEL ST DE DML", ficha['tecnico_resp'] or ""],
    ]
    marca_table = Table(marca_rows, colWidths=[5.3*inch, 1.2*inch])
    marca_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(marca_table)

    # Generar PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
