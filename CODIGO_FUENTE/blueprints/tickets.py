from datetime import datetime

from flask import Blueprint, request, render_template, redirect, url_for, flash

from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.decorators import login_required, role_required, get_current_user, log_action
from CODIGO_FUENTE.services.mail import send_mail
from CODIGO_FUENTE.services.numeracion import generate_ticket_number

tickets_bp = Blueprint("tickets", __name__)


@tickets_bp.route("/tickets/nuevo/<int:raypac_id>", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST", "RAYPAC")
def ticket_nuevo(raypac_id):
    """Crear ticket inicial desde RAYPAC freezado (nuevo flujo)."""
    user = get_current_user()
    db = get_db()

    raypac = db.execute("SELECT * FROM raypac_entries WHERE id = %s", (raypac_id,)).fetchone()
    if not raypac:
        flash("Ingreso RAYPAC no encontrado.", "error")
        return redirect(url_for("raypac.raypac_list"))

    if not raypac['is_frozen']:
        flash("El ingreso RAYPAC debe estar freezado para crear un ticket.", "error")
        return redirect(url_for("raypac.raypac_view", id=raypac_id))

    # Verificar si ya existe ticket para este RAYPAC
    ticket_existente = db.execute(
        "SELECT * FROM tickets WHERE raypac_id = %s", (raypac_id,)
    ).fetchone()

    if ticket_existente:
        flash(f"Ya existe un ticket para este ingreso: {ticket_existente['numero_ticket']}", "info")
        return redirect(url_for("tickets.ticket_view", numero_ticket=ticket_existente['numero_ticket']))

    if request.method == "POST":
        try:
            # Obtener datos del formulario
            fecha_ingreso = request.form.get("fecha_ingreso") or raypac['fecha_recepcion']
            tecnico_responsable = request.form.get("tecnico_responsable", "").strip()
            observaciones = request.form.get("observaciones", "").strip()

            # Componentes del estado del equipo
            estado_equipo = request.form.get("estado_equipo", "BUENO")
            carcaza = request.form.get("carcaza", "BUENO")
            cubre_feedwheel = request.form.get("cubre_feedwheel", "BUENO")
            mango = request.form.get("mango", "BUENO")
            botones = request.form.get("botones", "BUENO")
            motor_arrastre = request.form.get("motor_arrastre", "BUENO")
            motor_sellado = request.form.get("motor_sellado", "BUENO")
            cuchilla = request.form.get("cuchilla", "BUENO")
            servo = request.form.get("servo", "BUENO")
            rueda_arrastre = request.form.get("rueda_arrastre", "BUENO")
            resorte_manija = request.form.get("resorte_manija", "BUENO")
            otros = request.form.get("otros", "BUENO")

            # Validación
            if not tecnico_responsable:
                flash("El técnico responsable es obligatorio.", "error")
                return render_template("ticket_nuevo.html", raypac=raypac)

            # Generar número de ticket: TK-{serie}
            numero_ticket = generate_ticket_number(raypac['numero_serie'])

            # Crear ticket sin ficha_id (será NULL hasta que se cree la ficha)
            row = db.execute("""
                INSERT INTO tickets
                (numero_ticket, raypac_id, numero_serie, estado, ficha_id,
                 fecha_ingreso, tecnico_responsable, observaciones,
                 estado_equipo, carcaza, cubre_feedwheel, mango, botones,
                 motor_arrastre, motor_sellado, cuchilla, servo,
                 rueda_arrastre, resorte_manija, otros)
                VALUES (%s, %s, %s, 'ACTIVO', NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (numero_ticket, raypac_id, raypac['numero_serie'],
                  fecha_ingreso, tecnico_responsable, observaciones,
                  estado_equipo, carcaza, cubre_feedwheel, mango, botones,
                  motor_arrastre, motor_sellado, cuchilla, servo,
                  rueda_arrastre, resorte_manija, otros)).fetchone()

            db.commit()

            ticket_id = row['id']

            log_action(user['id'], "CREATE", "tickets", ticket_id, None,
                      f"Ticket inicial creado: {numero_ticket}")

            # Enviar email al comercial con el ticket
            if raypac['mail_comercial']:
                html_body = f"""
                <html>
                <head><style>
                    body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; }}
                    .email-container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; }}
                    .header {{ background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; padding: 20px; border-radius: 5px; text-align: center; }}
                    .ticket-box {{ border: 3px solid #2c3e50; padding: 20px; margin: 20px 0; border-radius: 8px; background-color: #ecf0f1; }}
                    .ticket-num {{ font-size: 32px; font-weight: bold; color: #e74c3c; text-align: center; margin: 10px 0; }}
                    .info-row {{ margin: 8px 0; padding: 5px 0; border-bottom: 1px solid #bdc3c7; }}
                    .label {{ font-weight: bold; color: #2c3e50; }}
                </style></head>
                <body>
                <div class="email-container">
                    <div class="header">
                        <h1>🎫 TICKET DE SEGUIMIENTO CREADO</h1>
                    </div>
                    <p>Estimado {raypac['comercial']},</p>
                    <p>Se ha generado un ticket de seguimiento para el equipo recibido:</p>
                    <div class="ticket-box">
                        <div class="ticket-num">{numero_ticket}</div>
                        <div class="info-row"><span class="label">Cliente:</span> {raypac['cliente']}</div>
                        <div class="info-row"><span class="label">Número de Serie:</span> {raypac['numero_serie']}</div>
                        <div class="info-row"><span class="label">Modelo:</span> {raypac['modelo_maquina']}</div>
                        <div class="info-row"><span class="label">Estado:</span> Pendiente de Revisión</div>
                    </div>
                    <p>Utilice este número de ticket para hacer seguimiento del estado de su equipo.</p>
                    <p style="color: #7f8c8d; font-size: 12px; text-align: center; margin-top: 20px;">DML Electricidad Industrial SRL - Servicio Técnico</p>
                </div>
                </body>
                </html>
                """
                send_mail(raypac['mail_comercial'],
                         f"🎫 Ticket de Seguimiento: {numero_ticket}",
                         html_body)

            flash(f"✅ Ticket {numero_ticket} creado exitosamente.", "success")
            return redirect(url_for("tickets.ticket_view", numero_ticket=numero_ticket))

        except Exception as e:
            flash(f"Error al crear ticket: {str(e)}", "error")

    return render_template("ticket_nuevo.html", raypac=raypac)


@tickets_bp.route("/tickets")
@login_required
@role_required("ADMIN", "DML_REPUESTOS", "DML_ST", "RAYPAC")
def tickets_list():
    """Listado de tickets activos (no cerrados) con búsqueda y filtro."""
    db = get_db()

    buscar = request.args.get("buscar", "")
    estado = request.args.get("estado", "")
    mostrar_cerrados = request.args.get("cerrados", "0") == "1"  # Por defecto no mostrar cerrados

    # LEFT JOIN porque tickets pueden existir sin ficha aún
    query = """
        SELECT t.*, f.numero_ficha, f.estado_reparacion,
               r.cliente, r.modelo_maquina, r.comercial
        FROM tickets t
        LEFT JOIN dml_fichas f ON t.ficha_id = f.id
        LEFT JOIN raypac_entries r ON t.raypac_id = r.id
        WHERE 1=1
    """
    params = []

    # Por defecto, solo mostrar tickets activos (no cerrados)
    if not mostrar_cerrados:
        query += " AND (t.estado IS NULL OR t.estado != 'CERRADO')"

    if buscar:
        query += " AND (t.numero_ticket LIKE %s OR t.numero_serie LIKE %s)"
        params.extend([f"%{buscar}%", f"%{buscar}%"])

    if estado:
        query += " AND t.estado = %s"
        params.append(estado)

    query += " ORDER BY t.fecha_creacion DESC"

    tickets = db.execute(query, params).fetchall()

    return render_template("tickets_list.html", tickets=tickets, buscar=buscar, estado=estado, mostrar_cerrados=mostrar_cerrados)


@tickets_bp.route("/ticket/<numero_ticket>")
def ticket_view(numero_ticket):
    """Vista pública del seguimiento de un ticket (sin login requerido).

    NOTA: sin @login_required a propósito - es la vista que usa el cliente
    final para hacer seguimiento de su equipo sin necesitar cuenta.
    Documentado también en el log de uso de IA del 25/06.
    """
    db = get_db()

    # LEFT JOIN porque el ticket puede existir sin ficha aún (nuevo flujo)
    ticket = db.execute("""
        SELECT t.*,
               f.numero_ficha, f.estado_reparacion, f.diagnostico_inicial, f.diagnostico_reparacion,
               r.cliente, r.numero_serie, r.modelo_maquina, r.comercial
        FROM tickets t
        LEFT JOIN dml_fichas f ON t.ficha_id = f.id
        LEFT JOIN raypac_entries r ON t.raypac_id = r.id
        WHERE t.numero_ticket = %s
    """, (numero_ticket,)).fetchone()

    if not ticket:
        flash("Ticket no encontrado.", "error")
        return redirect(url_for("auth.index"))

    # Obtener historial
    historial = db.execute("""
        SELECT * FROM ticket_historial WHERE ticket_id = %s ORDER BY fecha DESC
    """, (ticket['id'],)).fetchall()

    return render_template("ticket_view.html", ticket=ticket, historial=historial)


@tickets_bp.route("/ticket/<numero_ticket>/print")
def ticket_print(numero_ticket):
    """Imprime el ticket en formato solapa/etiqueta (print-friendly).

    NOTA: sin @login_required a propósito, mismo motivo que ticket_view.
    """
    db = get_db()

    # LEFT JOIN porque el ticket puede existir sin ficha (nuevo flujo)
    ticket = db.execute("""
        SELECT t.*, f.numero_ficha, f.estado_reparacion,
               r.numero_serie, r.cliente, r.comercial, r.modelo_maquina
        FROM tickets t
        LEFT JOIN dml_fichas f ON t.ficha_id = f.id
        LEFT JOIN raypac_entries r ON t.raypac_id = r.id
        WHERE t.numero_ticket = %s
    """, (numero_ticket,)).fetchone()

    if not ticket:
        flash("Ticket no encontrado.", "error")
        return redirect(url_for("auth.index"))

    return render_template("ticket_print.html", ticket=ticket, now=datetime.now())
