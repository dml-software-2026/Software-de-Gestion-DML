import os
from io import BytesIO

from flask import current_app
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image

from CODIGO_FUENTE.extensions import get_db


def generar_ficha_pdf(ficha_id):
    """Genera un PDF con la ficha de reparación completa - idéntico a la vista web.

    NOTA: usada por el endpoint /dml/<id>/pdf (descarga on-demand).
    Existe otra función similar, generate_ficha_pdf, usada por
    /dml/<id>/generar-ficha. Son dos generadores distintos que evolucionaron
    por separado - no se unificaron en este refactor, solo se movieron tal
    cual estaban. Vale la pena que el equipo decida si conviene unificarlos.
    """
    db = get_db()

    # Obtener datos de la ficha
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (ficha_id,)).fetchone()
    if not ficha:
        return None

    raypac = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (ficha['raypac_id'],)).fetchone()
    partes = db.execute("SELECT * FROM dml_partes WHERE ficha_id = ?", (ficha_id,)).fetchall()
    repuestos = db.execute("SELECT * FROM dml_repuestos WHERE ficha_id = ?", (ficha_id,)).fetchall()

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
    return buffer


def generate_ficha_pdf(ficha_id):
    """Genera PDF idéntico al Excel CAMPOS DE INGRESO DML.

    NOTA: usada por el endpoint /dml/<id>/generar-ficha (marcar como lista
    para retirar). Ver nota en generar_ficha_pdf sobre la duplicación.
    """
    try:
        db = get_db()
        ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (ficha_id,)).fetchone()

        if not ficha:
            raise ValueError(f"No se encontró ficha con ID {ficha_id}")

        # Obtener datos relacionados
        raypac = None
        if ficha['raypac_id']:
            raypac = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (ficha['raypac_id'],)).fetchone()

        partes = db.execute("SELECT * FROM dml_partes WHERE ficha_id = ? ORDER BY id", (ficha_id,)).fetchall()
        repuestos = db.execute("SELECT * FROM dml_repuestos WHERE ficha_id = ? ORDER BY id", (ficha_id,)).fetchall()

        # Crear PDF
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter,
                               topMargin=0.5*inch, bottomMargin=0.5*inch,
                               leftMargin=0.5*inch, rightMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()

        # Estilos
        title_style = ParagraphStyle('Title', parent=styles['Normal'], fontSize=14,
                                     fontName='Helvetica-Bold', alignment=1)
        normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10)
        label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9,
                                    fontName='Helvetica-Bold')
        small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8)

        gray_bg = colors.HexColor('#d9d9d9')

        # ===== ENCABEZADO =====
        # Cargar logo
        logo_path = os.path.join(current_app.static_folder, 'raypac_logo.png')
        logo_img = None
        if os.path.exists(logo_path):
            try:
                logo_img = Image(logo_path, width=1.5*inch, height=0.6*inch)
            except:
                pass

        header_data = [[
            Paragraph(f"<b>Nº Ficha</b><br/>{ficha['numero_ficha']:07d}", normal_style),
            logo_img if logo_img else "",
            Paragraph("<b><u>INFORME DML SOBRE EL<br/>EQUIPO EN REVISION</u></b>", title_style)
        ]]
        header_table = Table(header_data, colWidths=[1.5*inch, 2*inch, 3.5*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (2, 0), (2, 0), 1, colors.black),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.1*inch))

        # Servicio Técnico
        elements.append(Paragraph("<b>Servicio Técnico</b>", title_style))
        elements.append(Spacer(1, 0.15*inch))

        # ===== DATOS PRINCIPALES + ESTADO DEL EQUIPO =====
        info_data = [
            [Paragraph("<b>Fecha de recepción Raypac:</b>", label_style),
             Paragraph(str(raypac['fecha_recepcion'] if raypac else ''), normal_style)],
            [Paragraph("<b>Comercial responsable:</b>", label_style),
             Paragraph(str(raypac['comercial'] if raypac else ''), normal_style)],
            [Paragraph("<b>Nombre del Cliente:</b>", label_style),
             Paragraph(str(raypac['cliente'] if raypac else ''), normal_style)],
            [Paragraph("<b>Equipo Recibido:</b>", label_style),
             Paragraph(f"{raypac['modelo_maquina'] if raypac else ''}     <b>Serie N°:</b> {raypac['numero_serie'] if raypac else ''}", normal_style)],
            [Paragraph("<b>Fecha de ingreso DML:</b>", label_style),
             Paragraph(f"{ficha['fecha_ingreso']}     <b>Bat N°:</b> {raypac['numero_bateria'] if raypac else 'NO APLICA'}", normal_style)],
            [Paragraph("<b>Fecha de egreso DML:</b>", label_style),
             Paragraph(f"{ficha['fecha_egreso'] or ''}     <b>Cargador N°:</b> {raypac['numero_cargador'] if raypac else 'NO APLICA'}", normal_style)],
        ]

        # Columna derecha: Estado del Equipo
        estado_data = [[Paragraph("<b>ESTADO DEL EQUIPO</b>", label_style), ""]]
        for parte in partes:
            estado_data.append([
                Paragraph(f"<b>{parte['nombre_parte']}</b>", small_style),
                Paragraph(str(parte['estado'] or 'BUENO'), small_style)
            ])

        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))

        estado_table = Table(estado_data, colWidths=[1.5*inch, 1*inch])
        estado_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), gray_bg),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))

        main_table = Table([[info_table, estado_table]], colWidths=[5*inch, 2.5*inch])
        elements.append(main_table)
        elements.append(Spacer(1, 0.15*inch))

        # ===== DIAGNÓSTICO DEL DEPARTAMENTO TÉCNICO =====
        elements.append(Paragraph("<para alignment='center' backColor='#d9d9d9'><b>DIAGNOSTICO DEL DEPARTAMENTO TECNICO</b></para>", normal_style))
        elements.append(Spacer(1, 0.05*inch))
        diag_box = Paragraph(ficha['diagnostico_inicial'] or '', normal_style)
        elements.append(diag_box)
        elements.append(Spacer(1, 0.15*inch))

        # ===== OBSERVACIONES =====
        elements.append(Paragraph("<para alignment='center' backColor='#d9d9d9'><b>OBSERVACIONES</b></para>", normal_style))
        elements.append(Spacer(1, 0.05*inch))
        obs_box = Paragraph(ficha['observaciones'] or '', normal_style)
        elements.append(obs_box)
        elements.append(Spacer(1, 0.15*inch))

        # ===== DIAGNÓSTICO DE REPARACIÓN =====
        elements.append(Paragraph("<para alignment='center' backColor='#d9d9d9'><b>DIAGNOSTICO DE REPARACIÓN</b></para>", normal_style))
        elements.append(Spacer(1, 0.05*inch))
        diag_rep_box = Paragraph(ficha['diagnostico_reparacion'] or '', normal_style)
        elements.append(diag_rep_box)
        elements.append(Spacer(1, 0.15*inch))

        # ===== REPUESTOS COLOCADOS =====
        elements.append(Paragraph("<para alignment='center' backColor='#d9d9d9'><b>REPUESTOS COLOCADOS</b></para>", normal_style))
        elements.append(Spacer(1, 0.05*inch))

        repuestos_data = [[
            Paragraph("<b>Cantidad</b>", small_style),
            Paragraph("<b>Codigo</b>", small_style),
            Paragraph("<b>DESCRIPCION</b>", small_style),
            Paragraph("<b>EN STOCK</b>", small_style),
            Paragraph("<b>EN FALTA</b>", small_style)
        ]]

        for repuesto in repuestos[:8]:  # Máximo 8
            repuestos_data.append([
                Paragraph(str(repuesto['cantidad_utilizada'] or repuesto['cantidad']), small_style),
                Paragraph(str(repuesto['codigo_repuesto']), small_style),
                Paragraph(str(repuesto['descripcion']), small_style),
                Paragraph("✓" if repuesto['en_stock'] else "", small_style),
                Paragraph("✗" if repuesto['en_falta'] else "", small_style)
            ])

        # Rellenar hasta 8 filas
        for _ in range(len(repuestos), 8):
            repuestos_data.append([
                Paragraph("0", small_style),
                Paragraph("0", small_style),
                Paragraph("", small_style),
                Paragraph("", small_style),
                Paragraph("", small_style)
            ])

        repuestos_table = Table(repuestos_data, colWidths=[0.7*inch, 1*inch, 3.5*inch, 0.8*inch, 0.8*inch])
        repuestos_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), gray_bg),
            ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ('ALIGN', (3, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(repuestos_table)
        elements.append(Spacer(1, 0.15*inch))

        # ===== N° DE CICLOS =====
        ciclos_data = [[
            Paragraph("<b>N° DE CICLOS DE LA MÁQUINA CON LAS QUE SALE DE ST</b>", label_style),
            Paragraph(str(ficha['n_ciclos'] or 0), normal_style)
        ]]
        ciclos_table = Table(ciclos_data, colWidths=[4.5*inch, 2.5*inch])
        ciclos_table.setStyle(TableStyle([
            ('BOX', (1, 0), (1, 0), 0.5, colors.black),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ]))
        elements.append(ciclos_table)
        elements.append(Spacer(1, 0.1*inch))

        # ===== MARCAR CON UNA CRUZ =====
        elements.append(Paragraph("<para alignment='center' backColor='#d9d9d9'><b>MARCAR CON UNA CRUZ LO QUE CORRESPONDA</b></para>", normal_style))
        elements.append(Spacer(1, 0.05*inch))

        info_final = [
            ["TIPO DE MAQUINA QUE INGRESO AL ST", raypac['tipo_maquina'] if raypac else 'A BATERIA'],
            ["El módulo reparación Base es de tres (3hs)", ""],
            ["HORAS ADICIONALES DE TRABAJO", ficha['horas_adic'] or 'NO APLICA'],
            ["MECANIZADO ADICIONAL REALIZADO A LA MAQUINA", ficha['mecanizado_adic'] or 'NO APLICA'],
            ["TIPO DE TRABAJO REALIZADO", "REPARACIÓN"],
            ["TÉCNICO RESPONSABLE DEL ST DE DML", ficha['tecnico_resp'] or '']
        ]

        for item in info_final:
            row_data = [[Paragraph(f"<b>{item[0]}</b>", label_style), Paragraph(str(item[1]), normal_style)]]
            row_table = Table(row_data, colWidths=[4.5*inch, 2.5*inch])
            row_table.setStyle(TableStyle([
                ('BOX', (1, 0), (1, 0), 0.5, colors.black),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ]))
            elements.append(row_table)
            elements.append(Spacer(1, 0.05*inch))

        # ===== FOOTER =====
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("<para alignment='center'><b>SERVICIO TÉCNICO- DML ELECTRICIDAD INDUSTRIAL SRL</b></para>", normal_style))

        # Construir PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        return pdf_buffer

    except Exception as e:
        print(f"ERROR en generate_ficha_pdf_new: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
