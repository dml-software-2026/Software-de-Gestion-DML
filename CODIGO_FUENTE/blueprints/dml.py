from datetime import datetime

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from CODIGO_FUENTE.decorators import (
    get_current_user,
    log_action,
    login_required,
    permission_required,
    role_required,
)
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.mail import send_mail
from CODIGO_FUENTE.services.numeracion import crear_ticket, generate_ficha_number
from CODIGO_FUENTE.services.pdf import generar_ficha_pdf, generate_ficha_pdf
from CODIGO_FUENTE.services.stock import (
    actualizar_estadistica_repuesto,
    ajustar_stock_ubicacion,
    verificar_alerta_stock,
)

dml_bp = Blueprint("dml", __name__, url_prefix="/dml")


@dml_bp.route("")
@login_required
@permission_required(read_roles=["RAYPAC", "DML_REPUESTOS"], write_roles=["DML_ST"])
def dml_list(readonly=False):
    user = get_current_user()
    db = get_db()
    fichas = db.execute("""
        SELECT f.*, r.cliente, r.numero_serie
        FROM dml_fichas f
        LEFT JOIN raypac_entries r ON f.raypac_id = r.id
        WHERE f.is_closed = FALSE
        ORDER BY f.created_at DESC
    """).fetchall()

    return render_template("dml_list.html", fichas=fichas, user_role=user['role'], readonly=readonly)


@dml_bp.route("/entregadas")
@login_required
@role_required("ADMIN", "DML_ST", "RAYPAC")
def dml_entregadas():
    user = get_current_user()
    db = get_db()
    fichas = db.execute("""
        SELECT f.*, r.cliente, r.numero_serie, r.contacto_cliente, r.email_cliente
        FROM dml_fichas f
        LEFT JOIN raypac_entries r ON f.raypac_id = r.id
        WHERE f.estado_reparacion LIKE '%ENTREGAD%' OR f.is_closed = TRUE
        ORDER BY f.fecha_entrega_cliente DESC, f.updated_at DESC
    """).fetchall()

    return render_template("dml_entregadas.html", fichas=fichas, user_role=user['role'])


@dml_bp.route("/new/<int:raypac_id>", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def dml_new(raypac_id):
    user = get_current_user()
    db = get_db()

    raypac = db.execute("SELECT * FROM raypac_entries WHERE id = %s", (raypac_id,)).fetchone()
    if not raypac:
        flash("Ingreso RAYPAC no encontrado.", "error")
        return redirect(url_for("raypac.raypac_list"))

    # Buscar si existe un ticket asociado a este RAYPAC (nuevo flujo)
    ticket = db.execute("SELECT * FROM tickets WHERE raypac_id = %s AND ficha_id IS NULL", (raypac_id,)).fetchone()

    # #55: la ficha solo se puede crear despues de generar el ticket. El
    # boton "Crear Ficha" ya esta oculto en la UI hasta que exista ticket
    # (raypac_list.html, raypac_view.html), pero eso no alcanzaba si alguien
    # pegaba esta URL directo - habia un "flujo antiguo" que creaba la ficha
    # igual y recien despues el ticket, salteando la inspeccion visual y el
    # mail al comercial. Se saca esa rama y se bloquea acá tambien.
    if not ticket:
        flash("Debe crear un ticket primero antes de generar la ficha.", "error")
        return redirect(url_for("raypac.raypac_view", id=raypac_id))

    if request.method == "POST":
        try:
            fecha_ingreso = request.form.get("fecha_ingreso") or datetime.now().strftime("%Y-%m-%d")
            tecnico = request.form.get("tecnico")
            # CAMBIO DAVID: No usar diagnostico_inicial, ya viene de RAYPAC (diagnostico_ingreso)
            observaciones = request.form.get("observaciones")
            n_ciclos = request.form.get("n_ciclos") or 0
            tecnico_resp = request.form.get("tecnico_resp")

            # Validar que exista al menos un técnico (tecnico o tecnico_resp)
            if not tecnico and not tecnico_resp:
                flash("Completa los campos obligatorios: debe indicar un técnico responsable.", "error")
                return render_template("dml_form.html", raypac=raypac, ticket=ticket)

            # Asegurar que ambos campos tengan valor (tecnico es NOT NULL en BD)
            if not tecnico_resp:
                tecnico_resp = tecnico
            if not tecnico:
                tecnico = tecnico_resp

            numero_ficha = generate_ficha_number()

            # Ya se validó arriba que el ticket existe - se asocia la ficha con él
            row = db.execute("""
                INSERT INTO dml_fichas
                (numero_ficha, raypac_id, ticket_id, numero_ticket, fecha_ingreso, tecnico,
                 observaciones, n_ciclos, tecnico_resp,
                 estado_reparacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (numero_ficha, raypac_id, ticket['id'], ticket['numero_ticket'], fecha_ingreso, tecnico,
                  observaciones, n_ciclos, tecnico_resp, 'A LA ESPERA DE REVISIÓN')).fetchone()

            ficha_id = row['id']

            # Actualizar ticket con el ficha_id
            db.execute("UPDATE tickets SET ficha_id = %s WHERE id = %s", (ficha_id, ticket['id']))

            numero_ticket = ticket['numero_ticket']

            db.commit()

            # Crear partes estándar
            partes_nombres = [
                "ESTADO DEL EQUIPO", "CARCAZA", "CUBRE FEEDWHEEL", "MANGO",
                "BOTONES", "MOTOR DE ARRASTRE", "MOTOR DE SELLADO", "CUCHILLA",
                "SERVO", "RUEDA DE ARRASTRE", "RESORTE DE MANIJA", "OTROS"
            ]

            # Usar los estados del equipo completados en el ticket (inspección visual)
            ticket_to_parte = {
                'estado_equipo': 'ESTADO DEL EQUIPO',
                'carcaza': 'CARCAZA',
                'cubre_feedwheel': 'CUBRE FEEDWHEEL',
                'mango': 'MANGO',
                'botones': 'BOTONES',
                'motor_arrastre': 'MOTOR DE ARRASTRE',
                'motor_sellado': 'MOTOR DE SELLADO',
                'cuchilla': 'CUCHILLA',
                'servo': 'SERVO',
                'rueda_arrastre': 'RUEDA DE ARRASTRE',
                'resorte_manija': 'RESORTE DE MANIJA',
                'otros': 'OTROS'
            }

            for parte_nombre in partes_nombres:
                # Buscar el estado correspondiente en el ticket
                estado = "POR INSPECCIONAR"
                for ticket_col, parte_map in ticket_to_parte.items():
                    if parte_map == parte_nombre and ticket_col in ticket.keys() and ticket[ticket_col]:
                        estado = ticket[ticket_col]
                        break

                db.execute(
                    "INSERT INTO dml_partes (ficha_id, nombre_parte, estado) VALUES (%s, %s, %s)",
                    (ficha_id, parte_nombre, estado)
                )

            db.commit()

            log_action(user['id'], "CREATE", "dml_fichas", ficha_id, None,
                      f"Ficha DML #{numero_ficha} - Ticket: {numero_ticket}")

            # CAMBIO DAVID: Redirigir directamente a EDICIÓN en lugar de vista
            flash(f"Ficha #{numero_ficha} creada correctamente. Ticket: {numero_ticket}", "success")
            return redirect(url_for("dml.dml_edit", id=ficha_id))
        except Exception as e:
            flash(f"Error: {e!s}", "error")
            return render_template("dml_form.html", raypac=raypac, ticket=ticket)

    return render_template("dml_form.html", raypac=raypac, ticket=ticket)


@dml_bp.route("/<int:id>")
@login_required
@permission_required(read_roles=["RAYPAC", "DML_REPUESTOS"], write_roles=["DML_ST"])
def dml_view(id, readonly=False):
    user = get_current_user()
    db = get_db()
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()

    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_list"))

    # Obtener datos de RAYPAC
    raypac = None
    if ficha['raypac_id']:
        raypac = db.execute(
            "SELECT * FROM raypac_entries WHERE id = %s",
            (ficha['raypac_id'],)
        ).fetchone()

    partes = db.execute(
        "SELECT * FROM dml_partes WHERE ficha_id = %s ORDER BY id",
        (id,)
    ).fetchall()

    repuestos = db.execute(
        "SELECT * FROM dml_repuestos WHERE ficha_id = %s ORDER BY id",
        (id,)
    ).fetchall()

    return render_template("dml_view.html", ficha=ficha, raypac=raypac, partes=partes, repuestos=repuestos,
                           user_role=user['role'], readonly=readonly)


@dml_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def dml_edit(id):
    user = get_current_user()
    db = get_db()
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()

    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_list"))

    if ficha['is_closed'] and not request.form.get("unfreeze_code"):
        flash("Esta ficha está cerrada. Requiere código para editar.", "error")
        return redirect(url_for("dml.dml_view", id=id))

    if request.method == "POST":
        try:
            unfreeze_code = request.form.get("unfreeze_code")
            # TODO SEGURIDAD (Épica 2): código hardcodeado "ADMIN2024", mismo
            # que en raypac_edit. Se repite en al menos 2 lugares del código -
            # candidato claro para centralizar en una sola variable de entorno.
            if ficha['is_closed'] and unfreeze_code != "ADMIN2024":
                flash("Código incorrecto.", "error")
                return redirect(url_for("dml.dml_view", id=id))

            # Capturar SOLO los campos editables (no los de RAYPAC)
            fecha_ingreso = request.form.get("fecha_ingreso")
            fecha_egreso = request.form.get("fecha_egreso")

            estado = request.form.get("estado_reparacion")
            # CAMBIO DAVID: No usar diagnostico_inicial, ya viene de RAYPAC
            diagnostico_rep = request.form.get("diagnostico_reparacion")
            observaciones = request.form.get("observaciones")
            n_ciclos_raw = request.form.get("n_ciclos")
            try:
                n_ciclos = int(n_ciclos_raw) if n_ciclos_raw else None
            except ValueError:
                n_ciclos = None  # texto no numérico (ej. "NO APLICA")
            mecanizado = request.form.get("mecanizado_adic") or "NO APLICA"
            horas_raw = request.form.get("horas_adic")
            try:
                horas = float(horas_raw) if horas_raw else None
            except ValueError:
                horas = None  # texto no numérico (ej. "NO APLICA")
            numero_remito = request.form.get("numero_remito_salida")
            tecnico_resp = request.form.get("tecnico_resp") or ""

            # Validación de flujo lógico de estados según documento David
            # Orden lógico: A LA ESPERA DE REVISIÓN → EN REPARACIÓN → [A LA ESPERA DE REPUESTOS] → MÁQUINA LISTA PARA RETIRAR → MÁQUINA ENTREGADA
            estados_orden = {
                'A LA ESPERA DE REVISIÓN': 0,
                'REVISION_INICIAL': 0,  # alias legado, ver #44 - fichas creadas antes del fix
                'EN REPARACIÓN': 1,
                'EN REPARACION': 1,  # alias sin tilde, ver #44 - encoding legado en datos viejos
                'A LA ESPERA DE REPUESTOS': 1,  # Mismo nivel que EN REPARACIÓN (puede ir y volver)
                'REPARACIÓN COMPLETADA': 2,
                'MÁQUINA LISTA PARA RETIRAR': 3,
                'MÁQUINA ENTREGADA': 4,
                'FINALIZADO': 5
            }

            estado_actual_nivel = estados_orden.get(ficha['estado_reparacion'], 0)
            estado_nuevo_nivel = estados_orden.get(estado, 0)

            # Prevenir retrocesos ilógicos (salvo entre EN REPARACIÓN y A LA ESPERA DE REPUESTOS)
            if estado_actual_nivel >= 3 and estado_nuevo_nivel < estado_actual_nivel:
                # No permitir retrocesos desde MÁQUINA LISTA o posterior
                flash(f"⚠️ No se puede retroceder de '{ficha['estado_reparacion']}' a '{estado}'. Para cambios contacte al administrador.", "error")
                return redirect(url_for("dml.dml_edit", id=id))

            # Actualizar SOLO los campos que existen en dml_fichas
            db.execute("""
                UPDATE dml_fichas
                SET fecha_ingreso=%s, fecha_egreso=%s,
                    estado_reparacion=%s, diagnostico_reparacion=%s, observaciones=%s,
                    n_ciclos=%s, mecanizado_adic=%s, horas_adic=%s, numero_remito_salida=%s,
                    tecnico_resp=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id = %s
            """, (fecha_ingreso, fecha_egreso,
                  estado, diagnostico_rep, observaciones,
                  n_ciclos, mecanizado, horas, numero_remito,
                  tecnico_resp, id))
            db.commit()

            # Actualizar partes
            partes = db.execute("SELECT id FROM dml_partes WHERE ficha_id = %s ORDER BY id", (id,)).fetchall()
            for idx, parte in enumerate(partes):
                estado_parte = request.form.get(f"parte_{idx}")
                if estado_parte:
                    db.execute(
                        "UPDATE dml_partes SET estado = %s WHERE id = %s",
                        (estado_parte, parte['id'])
                    )
            db.commit()

            log_action(user['id'], "UPDATE", "dml_fichas", id, None, "Actualización ficha")

            flash("Ficha actualizada correctamente.", "success")
            return redirect(url_for("dml.dml_view", id=id))
        except Exception as e:
            db.rollback()  # Revertir la transacción en caso de error
            flash(f"Error: {e!s}", "error")

    partes = db.execute("SELECT * FROM dml_partes WHERE ficha_id = %s", (id,)).fetchall()
    repuestos = db.execute("SELECT * FROM dml_repuestos WHERE ficha_id = %s", (id,)).fetchall()

    # Convertir Row a dict para serialización JSON
    partes = [dict(p) for p in partes]
    repuestos = [dict(r) for r in repuestos]
    ficha = dict(ficha)

    return render_template("dml_edit.html", ficha=ficha, partes=partes, repuestos=repuestos)


# ======================== REPUESTOS ========================

@dml_bp.route("/<int:id>/repuestos/agregar", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def agregar_repuesto(id):
    user = get_current_user()
    db = get_db()

    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_edit", id=id))

    # Validar cantidad máxima (15 repuestos)
    count = db.execute("SELECT COUNT(*) as cnt FROM dml_repuestos WHERE ficha_id = %s", (id,)).fetchone()
    if count['cnt'] >= 15:
        flash("Máximo 15 repuestos por ficha.", "error")
        return redirect(url_for("dml.dml_edit", id=id))

    codigo = request.form.get("codigo_repuesto", "").strip().upper()
    cantidad_utilizada = int(request.form.get("cantidad_utilizada", 1))

    # Validar campos obligatorios
    if not codigo or not cantidad_utilizada:
        flash("Código y cantidad son obligatorios.", "error")
        return redirect(url_for("dml.dml_edit", id=id))

    # Buscar repuesto en matriz
    repuesto = db.execute(
        "SELECT * FROM matriz_repuestos WHERE codigo_repuesto = %s",
        (codigo,)
    ).fetchone()

    if not repuesto:
        flash(f"Repuesto '{codigo}' no encontrado en la matriz de repuestos.", "error")
        return redirect(url_for("dml.dml_edit", id=id))

    # Verificar stock AUTOMÁTICAMENTE en ubicación DML
    stock = db.execute(
        "SELECT cantidad FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = 'DML'",
        (codigo,)
    ).fetchone()

    # Determinar estado automáticamente según stock
    if stock and stock['cantidad'] >= cantidad_utilizada:
        en_stock = 1
        en_falta = 0
        estado_repuesto = "EN STOCK"
        # Descontar del stock en DML usando ajustar_stock_ubicacion
        ajustar_stock_ubicacion(codigo, "DML", -cantidad_utilizada)
    else:
        en_stock = 0
        en_falta = 1
        estado_repuesto = "EN FALTA"

    # Insertar repuesto
    db.execute("""
        INSERT INTO dml_repuestos
        (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada, estado_repuesto, en_stock, en_falta)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (id, codigo, repuesto['item'], cantidad_utilizada, cantidad_utilizada, estado_repuesto, en_stock, en_falta))
    db.commit()

    # Actualizar estadísticas de uso
    actualizar_estadistica_repuesto(codigo, cantidad_utilizada)

    # Verificar alerta de stock después de descontar
    if en_stock:
        verificar_alerta_stock(codigo)

    log_action(user['id'], "ADD_PART", "dml_repuestos", id, None,
              f"{codigo} x{cantidad_utilizada} ({estado_repuesto})")

    if en_stock:
        flash(f"Repuesto '{codigo}' agregado (disponible en stock, descontado automáticamente).", "success")
    else:
        flash(f"Repuesto '{codigo}' agregado (⚠️ NO hay stock disponible - marcado EN FALTA).", "warning")

    return redirect(url_for("dml.dml_edit", id=id))


@dml_bp.route("/<int:id>/marcar-falta/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS")
def marcar_repuesto_falta(id, repuesto_id):
    db = get_db()

    repuesto = db.execute(
        "SELECT * FROM dml_repuestos WHERE id = %s AND ficha_id = %s",
        (repuesto_id, id)
    ).fetchone()

    if not repuesto:
        return jsonify({"error": "Repuesto no encontrado"}), 404

    db.execute(
        "UPDATE dml_repuestos SET en_falta = 1, en_stock = 0 WHERE id = %s",
        (repuesto_id,)
    )
    db.commit()

    return jsonify({"success": True}), 200


@dml_bp.route("/<int:id>/marcar-llegada/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS")
def marcar_repuesto_llegada(id, repuesto_id):
    db = get_db()
    user = get_current_user()

    repuesto = db.execute(
        "SELECT * FROM dml_repuestos WHERE id = %s AND ficha_id = %s",
        (repuesto_id, id)
    ).fetchone()

    if not repuesto:
        return jsonify({"error": "Repuesto no encontrado"}), 404

    # Cambiar estado
    db.execute(
        "UPDATE dml_repuestos SET en_falta = 0, en_stock = 1, estado_repuesto = 'EN STOCK' WHERE id = %s",
        (repuesto_id,)
    )

    # Descontar del stock en ubicación DML
    ajustar_stock_ubicacion(repuesto['codigo_repuesto'], "DML", -repuesto['cantidad_utilizada'])

    # Actualizar estadísticas
    actualizar_estadistica_repuesto(repuesto['codigo_repuesto'], repuesto['cantidad_utilizada'])

    db.commit()

    # Verificar alerta de stock después de descontar
    verificar_alerta_stock(repuesto['codigo_repuesto'])

    log_action(user['id'], "PART_ARRIVED", "dml_repuestos", repuesto_id, None,
              f"{repuesto['codigo_repuesto']}")

    return jsonify({"success": True}), 200


@dml_bp.route("/<int:ficha_id>/repuestos/mover-a-stock/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS")
def mover_repuesto_a_stock(ficha_id, repuesto_id):
    """
    Mueve un repuesto de EN FALTA a EN STOCK cuando llega nueva disponibilidad.
    Descuenta del inventario y actualiza el estado.
    """
    user = get_current_user()
    db = get_db()

    # Obtener el repuesto
    repuesto = db.execute("""
        SELECT dr.*, m.item as descripcion
        FROM dml_repuestos dr
        LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = dr.codigo_repuesto
        WHERE dr.id = %s AND dr.ficha_id = %s
    """, (repuesto_id, ficha_id)).fetchone()

    if not repuesto:
        flash("Repuesto no encontrado.", "error")
        return redirect(url_for("dml.dml_edit", id=ficha_id))

    # Verificar stock actual
    stock = db.execute("""
        SELECT cantidad FROM stock_ubicaciones
        WHERE codigo_repuesto = %s AND ubicacion = 'DML'
    """, (repuesto['codigo_repuesto'],)).fetchone()

    if not stock or stock['cantidad'] < repuesto['cantidad_utilizada']:
        flash(f"⚠️ No hay stock suficiente de {repuesto['codigo_repuesto']}. Disponible: {stock['cantidad'] if stock else 0}, Necesario: {repuesto['cantidad_utilizada']}", "error")
        return redirect(url_for("dml.dml_edit", id=ficha_id))

    # Actualizar estado a EN STOCK
    db.execute("""
        UPDATE dml_repuestos
        SET en_stock = 1, en_falta = 0, estado_repuesto = 'COLOCADO'
        WHERE id = %s
    """, (repuesto_id,))

    # Descontar del stock
    db.execute("""
        UPDATE stock_ubicaciones
        SET cantidad = cantidad - %s, updated_at = CURRENT_TIMESTAMP
        WHERE codigo_repuesto = %s AND ubicacion = 'DML'
    """, (repuesto['cantidad_utilizada'], repuesto['codigo_repuesto']))

    # Actualizar matriz_repuestos
    db.execute("""
        UPDATE matriz_repuestos
        SET cantidad_actual = cantidad_actual - %s
        WHERE codigo_repuesto = %s
    """, (repuesto['cantidad_utilizada'], repuesto['codigo_repuesto']))

    db.commit()

    log_action(user['id'], "MOVER_REPUESTO_A_STOCK", "dml_repuestos", repuesto_id,
              "EN FALTA", f"EN STOCK - {repuesto['codigo_repuesto']}")

    flash(f"✅ Repuesto {repuesto['codigo_repuesto']} movido a EN STOCK y descontado del inventario.", "success")
    return redirect(url_for("dml.dml_edit", id=ficha_id))


@dml_bp.route("/<int:ficha_id>/repuestos/eliminar/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def eliminar_repuesto(ficha_id, repuesto_id):
    user = get_current_user()
    db = get_db()

    repuesto = db.execute("SELECT * FROM dml_repuestos WHERE id = %s AND ficha_id = %s", (repuesto_id, ficha_id)).fetchone()
    if not repuesto:
        flash("Repuesto no encontrado.", "error")
        return redirect(url_for("dml.dml_edit", id=ficha_id))

    # Si el repuesto estaba en stock, devolverlo a ubicación DML
    if repuesto['en_stock']:
        ajustar_stock_ubicacion(repuesto['codigo_repuesto'], "DML", repuesto['cantidad_utilizada'])

        # Restar de estadísticas (reversar el uso)
        db.execute("""
            UPDATE estadisticas_repuestos
            SET total_usos = total_usos - %s, updated_at = CURRENT_TIMESTAMP
            WHERE codigo_repuesto = %s
        """, (repuesto['cantidad_utilizada'], repuesto['codigo_repuesto']))

    # Eliminar repuesto
    db.execute("DELETE FROM dml_repuestos WHERE id = %s", (repuesto_id,))
    db.commit()

    log_action(user['id'], "DELETE", "dml_repuestos", repuesto_id, None,
              f"Repuesto {repuesto['codigo_repuesto']} eliminado de ficha {ficha_id}")

    flash("Repuesto eliminado correctamente.", "success")
    return redirect(url_for("dml.dml_edit", id=ficha_id))


# ======================== TICKETS (asociados a ficha) ========================

@dml_bp.route("/<int:id>/crear-ticket", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def crear_ticket_endpoint(id):
    """Crea un ticket de seguimiento para una ficha DML."""
    user = get_current_user()
    db = get_db()

    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_list"))

    # Verificar si ya existe ticket
    if ficha['numero_ticket']:
        flash(f"Ya existe ticket creado: {ficha['numero_ticket']}", "info")
        return redirect(url_for("dml.dml_view", id=id))

    try:
        # Obtener número de serie desde RAYPAC
        raypac = db.execute(
            "SELECT numero_serie, mail_comercial FROM raypac_entries WHERE id = %s",
            (ficha['raypac_id'],)
        ).fetchone()

        if not raypac:
            flash("No se encontró información de RAYPAC.", "error")
            return redirect(url_for("dml.dml_view", id=id))

        # Crear ticket
        numero_ticket = crear_ticket(id, raypac['numero_serie'])

        # Enviar ticket por email
        if raypac['mail_comercial']:
            html_body = f"""
            <html>
            <head><style>
                body {{ font-family: Arial, sans-serif; }}
                .ticket-box {{ border: 2px solid #2c3e50; padding: 20px; border-radius: 5px; }}
                .ticket-num {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
                .info-row {{ margin: 10px 0; }}
                .label {{ font-weight: bold; color: #555; }}
            </style></head>
            <body>
            <h2>🎫 TICKET DE SEGUIMIENTO GENERADO</h2>
            <div class="ticket-box">
                <div class="ticket-num">{numero_ticket}</div>
                <div class="info-row"><span class="label">Número de Ficha:</span> {ficha['numero_ficha']}</div>
                <div class="info-row"><span class="label">Número de Serie:</span> {raypac['numero_serie']}</div>
                <div class="info-row"><span class="label">Estado:</span> {ficha['estado_reparacion']}</div>
                <div class="info-row"><span class="label">Fecha de Ingreso:</span> {ficha['fecha_ingreso']}</div>
            </div>
            <p>Puede usar este número de ticket para hacer seguimiento de su equipo.</p>
            <p style="color: #999; font-size: 12px;">DML Electricidad Industrial SRL</p>
            </body>
            </html>
            """
            send_mail(raypac['mail_comercial'],
                     f"🎫 Ticket de Seguimiento: {numero_ticket}",
                     html_body)

        log_action(user['id'], "CREATE_TICKET", "tickets", id, None, numero_ticket)
        flash(f"✅ Ticket creado exitosamente: {numero_ticket}", "success")

    except Exception as e:
        flash(f"Error al crear ticket: {e!s}", "error")

    return redirect(url_for("dml.dml_view", id=id))


@dml_bp.route("/<int:id>/close", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def dml_close(id):
    """Cierra/finaliza una ficha DML y notifica al comercial."""
    user = get_current_user()
    db = get_db()

    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_list"))

    if ficha['is_closed']:
        flash("Esta ficha ya está cerrada.", "info")
        return redirect(url_for("dml.dml_view", id=id))

    # VALIDACIONES OBLIGATORIAS antes de cerrar
    errores = []

    # 1. Validar remito de salida
    if not ficha['numero_remito_salida']:
        errores.append("Número de remito de salida")

    # 2. Validar diagnóstico de reparación
    if not ficha['diagnostico_reparacion'] or len(ficha['diagnostico_reparacion'].strip()) < 10:
        errores.append("Diagnóstico de reparación (mínimo 10 caracteres)")

    # 3. Validar técnico responsable
    if not ficha['tecnico_resp']:
        errores.append("Técnico responsable")

    # 4. Validar que tenga al menos un repuesto registrado o partes inspeccionadas
    repuestos_count = db.execute("SELECT COUNT(*) as cnt FROM dml_repuestos WHERE ficha_id = %s", (id,)).fetchone()['cnt']
    partes_inspeccionadas = db.execute(
        "SELECT COUNT(*) as cnt FROM dml_partes WHERE ficha_id = %s AND estado != 'POR INSPECCIONAR'",
        (id,)
    ).fetchone()['cnt']

    if repuestos_count == 0 and partes_inspeccionadas == 0:
        errores.append("Debe inspeccionar al menos una parte o agregar repuestos utilizados")

    if errores:
        flash("⚠️ No se puede cerrar la ficha. Campos requeridos faltantes:", "error")
        for error in errores:
            flash(f"• {error}", "error")
        return redirect(url_for("dml.dml_edit", id=id))

    try:
        # Cerrar la ficha y marcar como ENTREGADA
        fecha_egreso = datetime.now().strftime("%Y-%m-%d")
        db.execute("""
            UPDATE dml_fichas
            SET is_closed = TRUE, fecha_egreso = %s, estado_reparacion = 'ENTREGADA'
            WHERE id = %s
        """, (fecha_egreso, id))

        # Cerrar el ticket asociado (ya cumplió su función de seguimiento)
        if ficha['numero_ticket']:
            db.execute("""
                UPDATE tickets
                SET estado = 'CERRADO', fecha_cierre = %s
                WHERE numero_ticket = %s
            """, (fecha_egreso, ficha['numero_ticket']))

        db.commit()

        # Obtener info para email
        raypac = db.execute(
            "SELECT numero_serie, cliente, comercial, mail_comercial FROM raypac_entries WHERE id = %s",
            (ficha['raypac_id'],)
        ).fetchone()

        # Enviar email "Máquina Lista" al comercial
        if raypac and raypac['mail_comercial']:
            html_body = f"""
            <html>
            <head><style>
                body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; }}
                .email-container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; padding: 20px; border-radius: 5px; text-align: center; margin-bottom: 20px; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .content {{ color: #333; line-height: 1.6; }}
                .info-box {{ background-color: #ecf0f1; padding: 15px; border-left: 4px solid #27ae60; margin: 15px 0; }}
                .label {{ font-weight: bold; color: #2c3e50; }}
                .footer {{ color: #7f8c8d; font-size: 12px; text-align: center; margin-top: 20px; border-top: 1px solid #ecf0f1; padding-top: 10px; }}
                .success-badge {{ background-color: #27ae60; color: white; padding: 10px 15px; border-radius: 5px; display: inline-block; }}
            </style></head>
            <body>
            <div class="email-container">
                <div class="header">
                    <h1>✅ MÁQUINA LISTA PARA RETIRAR</h1>
                </div>
                <div class="content">
                    <p>Estimado {raypac['comercial']},</p>
                    <p>Le comunicamos que la reparación de su equipo ha sido <span class="success-badge">FINALIZADA</span> y está lista para retirar.</p>
                    <div class="info-box">
                        <p><span class="label">Número de Ficha:</span> {ficha['numero_ficha']:07d}</p>
                        <p><span class="label">Número de Serie:</span> {raypac['numero_serie']}</p>
                        <p><span class="label">Cliente:</span> {raypac['cliente']}</p>
                        <p><span class="label">Fecha de Finalización:</span> {fecha_egreso}</p>
                        <p><span class="label">Ticket de Seguimiento:</span> {ficha['numero_ticket'] or 'N/A'}</p>
                    </div>
                    <p>Por favor, contacte con nuestro departamento técnico para coordinar el retiro del equipo.</p>
                    <p>Gracias por confiar en <strong>DML Electricidad Industrial SRL</strong>.</p>
                </div>
                <div class="footer">
                    <p>Este es un mensaje automático. No responda a este correo.</p>
                    <p>DML Electricidad Industrial SRL - Servicio Técnico</p>
                </div>
            </div>
            </body>
            </html>
            """
            mail_sent = send_mail(raypac['mail_comercial'],
                                 f"✅ Máquina Lista: Ficha #{ficha['numero_ficha']:07d}",
                                 html_body)
            mail_status = "enviada" if mail_sent else "fallida (revisar logs)"
        else:
            mail_status = "sin email configurado"

        log_action(user['id'], "CLOSE", "dml_fichas", id, None,
                  f"Ficha finalizada - Notificación {mail_status} - Comercial: {raypac['comercial'] if raypac else 'N/A'}")

        flash(f"✅ Ficha #{ficha['numero_ficha']} cerrada y marcada como ENTREGADA. Notificación {mail_status}.", "success")
        return redirect(url_for("dml.dml_view", id=id))
    except Exception as e:
        flash(f"Error al cerrar ficha: {e!s}", "error")
        return redirect(url_for("dml.dml_view", id=id))


@dml_bp.route("/<int:id>/acuse", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST", "RAYPAC")
def dml_registrar_acuse(id):
    """Registra el acuse de recibo de una máquina entregada."""
    user = get_current_user()
    db = get_db()

    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_entregadas"))

    if ficha['estado_reparacion'] != 'ENTREGADA':
        flash("Solo se puede registrar acuse de fichas marcadas como ENTREGADA.", "error")
        return redirect(url_for("dml.dml_view", id=id))

    try:
        fecha_entrega = request.form.get("fecha_entrega_cliente")
        recibido_por = request.form.get("recibido_por", "").strip()
        observaciones = request.form.get("observaciones_entrega", "").strip()

        if not fecha_entrega or not recibido_por:
            flash("La fecha de entrega y el nombre de quien recibe son obligatorios.", "error")
            return redirect(url_for("dml.dml_entregadas"))

        # Actualizar acuse de recibo
        db.execute("""
            UPDATE dml_fichas
            SET fecha_entrega_cliente = %s, recibido_por = %s,
                observaciones = CASE
                    WHEN observaciones IS NOT NULL AND observaciones != ''
                    THEN observaciones || ' | ENTREGA: ' || %s
                    ELSE 'ENTREGA: ' || %s
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (fecha_entrega, recibido_por, observaciones, observaciones, id))

        db.commit()

        log_action(user['id'], "UPDATE", "dml_fichas", id, None,
                  f"Acuse de recibo registrado - Recibido por: {recibido_por}")

        flash(f"✅ Acuse de recibo registrado correctamente para Ficha #{ficha['numero_ficha']}.", "success")

    except Exception as e:
        flash(f"Error al cerrar ficha: {e!s}", "error")

    return redirect(url_for("dml.dml_view", id=id))


# ======================== PDF DE FICHA ========================
# NOTA: estas 2 rutas se agregaron en un checkpoint posterior al resto del
# archivo - en la primera pasada de extracción no se habían visto todavía
# (estaban ubicadas mas adelante en el app.py original, cerca del bloque de
# usuarios/admin, aunque su URL es /dml/... y por eso corresponden aca).

@dml_bp.route("/<int:id>/generar-ficha", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def generar_ficha(id):
    user = get_current_user()
    db = get_db()

    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_list"))

    # Verificar que esté en "MÁQUINA LISTA PARA RETIRAR"
    if ficha['estado_reparacion'] != 'MÁQUINA LISTA PARA RETIRAR':
        flash("La máquina debe estar en estado 'MÁQUINA LISTA PARA RETIRAR'.", "error")
        return redirect(url_for("dml.dml_view", id=id))

    try:
        # Generar PDF para validar que no hay errores
        pdf_buffer = generate_ficha_pdf(id)

        # Guardar en BD
        db.execute(
            "UPDATE dml_fichas SET ficha_generada = 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (id,)
        )
        db.commit()

        # Intentar enviar correo al comercial (no bloquear si falla)
        try:
            raypac = db.execute(
                "SELECT mail_comercial FROM raypac_entries WHERE id = %s",
                (ficha['raypac_id'],)
            ).fetchone()

            if raypac and raypac['mail_comercial']:
                html_body = f"""
                <html>
                <body>
                <h2>Máquina Lista para Entregar</h2>
                <p>La máquina <strong>{ficha['numero_ficha']}</strong> se encuentra lista para retirar.</p>
                <p>Datos del ticket: {ficha['numero_ticket']}</p>
                <p>Saludos, DML</p>
                </body>
                </html>
                """
                send_mail(raypac['mail_comercial'],
                         f"Máquina {ficha['numero_ticket']} - Lista para Retirar",
                         html_body)

                db.execute(
                    "UPDATE dml_fichas SET ticket_enviado = 1 WHERE id = %s",
                    (id,)
                )
                db.commit()
        except Exception as e:
            print(f"Error al enviar email: {e!s}")

        log_action(user['id'], "GENERATE_FICHA", "dml_fichas", id, None,
                  f"Ficha #{ficha['numero_ficha']}")

        flash("Ficha generada exitosamente. Descarga el PDF con el botón disponible.", "success")
        return redirect(url_for("dml.dml_view", id=id))

    except Exception as e:
        flash(f"Error al generar ficha: {e!s}", "error")
        return redirect(url_for("dml.dml_view", id=id))


@dml_bp.route("/<int:id>/pdf", methods=["GET"])
@login_required
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS")
def descargar_ficha_pdf(id):
    """Genera y descarga el PDF de una ficha de reparación."""
    user = get_current_user()
    db = get_db()

    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_list"))

    # Generar PDF on-demand
    pdf_buffer = generar_ficha_pdf(id)

    if not pdf_buffer:
        flash("No se pudo generar el PDF.", "error")
        return redirect(url_for("dml.dml_view", id=id))

    log_action(user['id'], "DOWNLOAD_FICHA_PDF", "dml_fichas", id, None,
              f"Ficha #{ficha['numero_ficha']}")

    # Devolver PDF
    return send_file(pdf_buffer, mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"ficha_{ficha['numero_ficha']:07d}.pdf")
