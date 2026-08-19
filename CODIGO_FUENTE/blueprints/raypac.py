import re
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from CODIGO_FUENTE.decorators import (
    get_current_user,
    log_action,
    login_required,
    permission_required,
    role_required,
)
from CODIGO_FUENTE.extensions import get_db

raypac_bp = Blueprint("raypac", __name__, url_prefix="/raypac")


@raypac_bp.route("")
@login_required
@permission_required(read_roles=["DML_ST"], write_roles=["RAYPAC"])
def raypac_list(readonly=False):
    user = get_current_user()
    db = get_db()

    try:
        entries = db.execute("""
            SELECT r.*,
                   (SELECT COUNT(*) FROM dml_fichas f WHERE f.raypac_id = r.id) AS fichas_count,
                   (SELECT f.id FROM dml_fichas f WHERE f.raypac_id = r.id ORDER BY f.created_at DESC LIMIT 1) AS ficha_id,
                   (SELECT f.estado_reparacion FROM dml_fichas f WHERE f.raypac_id = r.id ORDER BY f.created_at DESC LIMIT 1) AS estado_ficha,
                   (SELECT t.id FROM tickets t WHERE t.raypac_id = r.id ORDER BY t.created_at DESC LIMIT 1) AS ticket_id,
                   (SELECT t.numero_ticket FROM tickets t WHERE t.raypac_id = r.id ORDER BY t.created_at DESC LIMIT 1) AS ticket_numero
            FROM raypac_entries r
            ORDER BY r.created_at DESC
        """).fetchall()
    except Exception as e:
        db.rollback()  # En caso de error, revertir la transacción
        # Si hay error en la query, mostrar mensaje y retornar lista vacía
        flash(f"Error al cargar ingresos RAYPAC: {e!s}", "error")
        entries = []

    # Configuración de badges para estados de fichas DML
    estado_config = {
        "REVISION_INICIAL": {"color": "#17a2b8", "texto": "Revisión Inicial"},
        "EN_REPARACION": {"color": "#ffc107", "texto": "En Reparación"},
        "PAUSADA": {"color": "#fd7e14", "texto": "Pausada"},
        "FINALIZADA": {"color": "#28a745", "texto": "Finalizada"},
        "ENTREGADA": {"color": "#6c757d", "texto": "Entregada"},
        "MÁQUINA ENTREGADA": {"color": "#6c757d", "texto": "Máquina Entregada"}
    }

    return render_template("raypac_list.html", entries=entries, user_role=user['role'], readonly=readonly, estado_config=estado_config)


@raypac_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def raypac_new():
    user = get_current_user()
    db = get_db()

    if request.method == "POST":
        try:
            fecha = request.form.get("fecha_recepcion") or datetime.now().strftime("%Y-%m-%d")
            tipo_solicitud = request.form.get("tipo_solicitud")
            cliente = request.form.get("cliente")
            numero_serie = request.form.get("numero_serie")
            modelo = request.form.get("modelo_maquina")
            tipo_maquina = request.form.get("tipo_maquina")
            numero_bateria = request.form.get("numero_bateria") or "NO APLICA"
            numero_cargador = request.form.get("numero_cargador") or "NO APLICA"
            diagnostico = request.form.get("diagnostico_ingreso")
            comercial = request.form.get("comercial")
            mail_comercial = request.form.get("mail_comercial")
            contacto_cliente = request.form.get("contacto_cliente")
            email_cliente = request.form.get("email_cliente")

            # Validación básica
            if not all([tipo_solicitud, cliente, numero_serie, modelo, tipo_maquina, comercial, mail_comercial]):
                flash("Por favor completa todos los campos obligatorios.", "error")
                return render_template("raypac_form.html")

            # Verificar que el número de serie es único
            existe = db.execute("SELECT id FROM raypac_entries WHERE numero_serie = %s", (numero_serie,)).fetchone()
            if existe:
                flash("Este número de serie ya existe en el sistema.", "error")
                return render_template("raypac_form.html")

            # Número correlativo interno
            correlativo = db.execute("SELECT COALESCE(MAX(numero_correlativo), 0) + 1 AS next FROM raypac_entries").fetchone()['next']

            # NOTA: SQLite no devuelve el id insertado en el mismo INSERT (por
            # eso el código original hacía un segundo SELECT con
            # last_insert_rowid(), que no existe en Postgres). Postgres sí
            # permite pedirlo directo con RETURNING id, en una sola query.
            row = db.execute("""
                INSERT INTO raypac_entries
                (numero_correlativo, fecha_recepcion, tipo_solicitud, cliente, numero_serie, modelo_maquina, tipo_maquina,
                 numero_bateria, numero_cargador, diagnostico_ingreso, comercial, mail_comercial, contacto_cliente, email_cliente)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (correlativo, fecha, tipo_solicitud, cliente, numero_serie, modelo, tipo_maquina,
                  numero_bateria, numero_cargador, diagnostico, comercial, mail_comercial, contacto_cliente, email_cliente)).fetchone()
            db.commit()

            raypac_id = row['id']
            log_action(user['id'], "CREATE", "raypac_entries", raypac_id, None,
                      f"Ingreso RAYPAC: {cliente} - {numero_serie}")

            flash("Ingreso RAYPAC registrado correctamente.", "success")
            return redirect(url_for("raypac.raypac_view", id=raypac_id))
        except Exception as e:
            db.rollback()  # Revertir la transacción en caso de error
            flash(f"Error al guardar: {e!s}", "error")
            return render_template("raypac_form.html")

    return render_template("raypac_form.html")


@raypac_bp.route("/<int:id>")
@login_required
@permission_required(read_roles=["DML_ST"], write_roles=["RAYPAC"])
def raypac_view(id, readonly=False):
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = %s", (id,)).fetchone()

    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac.raypac_list"))

    # Verificar si existe un ticket asociado
    ticket = db.execute("SELECT numero_ticket FROM tickets WHERE raypac_id = %s", (id,)).fetchone()

    return render_template("raypac_view.html", entry=entry, user_role=user['role'], readonly=readonly, ticket=ticket)


@raypac_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def raypac_edit(id):
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = %s", (id,)).fetchone()

    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac.raypac_list"))

    if entry['is_frozen'] and not request.form.get("unfreeze_code"):
        flash("Este registro está freezado. Requiere código de desbloqueo.", "error")
        return render_template("raypac_view.html", entry=entry)

    if request.method == "POST":
        try:
            unfreeze_code = request.form.get("unfreeze_code")
            # TODO SEGURIDAD (Épica 2): código de desbloqueo hardcodeado
            # ("ADMIN2024"). Mismo patrón que los hashes hardcodeados en
            # migrate_db() y debería resolverse junto con esa tarea.
            if entry['is_frozen'] and unfreeze_code != "ADMIN2024":
                flash("Código de desbloqueo incorrecto.", "error")
                return render_template("raypac_view.html", entry=entry)

            fecha = request.form.get("fecha_recepcion")
            tipo_solicitud = request.form.get("tipo_solicitud")
            cliente = request.form.get("cliente")
            numero_serie = request.form.get("numero_serie")
            diagnostico = request.form.get("diagnostico_ingreso")
            comercial = request.form.get("comercial")
            mail_comercial = request.form.get("mail_comercial")
            contacto_cliente = request.form.get("contacto_cliente")
            email_cliente = request.form.get("email_cliente")

            db.execute("""
                UPDATE raypac_entries
                SET fecha_recepcion=%s, tipo_solicitud=%s, cliente=%s, numero_serie=%s,
                    diagnostico_ingreso=%s, comercial=%s, mail_comercial=%s, contacto_cliente=%s, email_cliente=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id = %s
            """, (fecha, tipo_solicitud, cliente, numero_serie, diagnostico, comercial, mail_comercial, contacto_cliente, email_cliente, id))
            db.commit()

            log_action(user['id'], "UPDATE", "raypac_entries", id, None,
                      f"Actualización: {cliente}")

            flash("Ingreso RAYPAC actualizado.", "success")
            return redirect(url_for("raypac.raypac_view", id=id))
        except Exception as e:
            db.rollback()
            flash(f"Error: {e!s}", "error")

    return render_template("raypac_form.html", entry=entry, edit=True)


@raypac_bp.route("/<int:id>/freeze", methods=["POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def raypac_freeze(id):
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = %s", (id,)).fetchone()

    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac.raypac_list"))

    numero_remito = (request.form.get("numero_remito") or "").strip()

    # CAMBIO DAVID: Remito OBLIGATORIO con formato ####-#### (8 dígitos)
    if not numero_remito:
        flash("⚠️ El número de remito es OBLIGATORIO para freezar y enviar. Formato: últimos 4 dígitos o completo ####-####.", "error")
        return redirect(url_for("raypac.raypac_view", id=id))

    # Auto-completar formato si solo ingresa 4 dígitos (últimos)
    if re.match(r'^\d{1,4}$', numero_remito):
        # Usuario ingresó solo números (1-4 dígitos), auto-completar
        ultimo = numero_remito.zfill(4)  # Rellenar con ceros a la izquierda
        numero_remito = f"00001-{ultimo}"  # Formato: 00001-XXXX
        flash(f"📋 Remito auto-completado: {numero_remito}", "info")
    elif not re.match(r'^\d{4,5}-\d{4,7}$', numero_remito):
        flash("⚠️ Formato de remito inválido. Ingresa solo los últimos 4 dígitos (ej: 4222) o el formato completo ####-#### (ej: 00001-04222).", "error")
        return redirect(url_for("raypac.raypac_view", id=id))

    # Verificar que no exista ya en raypac_entries
    existe = db.execute("SELECT id FROM raypac_entries WHERE numero_remito = %s", (numero_remito,)).fetchone()
    if existe and existe['id'] != id:
        flash("El número de remito ya existe en otro equipo.", "error")
        return redirect(url_for("raypac.raypac_view", id=id))

    # Verificar que no exista en envios_repuestos
    existe_envio = db.execute("SELECT id FROM envios_repuestos WHERE numero_remito = %s", (numero_remito,)).fetchone()
    if existe_envio:
        flash("El número de remito ya existe en un envío de repuestos. Usa un remito diferente.", "error")
        return redirect(url_for("raypac.raypac_view", id=id))

    db.execute("""
        UPDATE raypac_entries
        SET is_frozen = TRUE, frozen_at = CURRENT_TIMESTAMP, numero_remito = %s,
            estado_envio_equipos = 'ENVIADO', fecha_envio_equipos = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (numero_remito, id))
    db.commit()

    log_action(user['id'], "FREEZE", "raypac_entries", id, None,
              f"Freezado con remito {numero_remito} - Equipo enviado a DML")

    flash("Máquina freezada y enviada a ST.", "success")
    return redirect(url_for("raypac.raypac_view", id=id))


@raypac_bp.route("/<int:id>/unfreeze", methods=["POST"])
@login_required
@role_required("ADMIN")  # RESTRICCIÓN: Solo ADMIN puede desfreezar
def raypac_unfreeze(id):
    """Descongelar un ingreso RAYPAC con código (solo ADMIN)"""
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = %s", (id,)).fetchone()

    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac.raypac_list"))

    if not entry['is_frozen']:
        flash("El registro no está freezado.", "error")
        return redirect(url_for("raypac.raypac_view", id=id))

    unfreeze_code = request.form.get("unfreeze_code", "").strip()

    # CAMBIO DAVID: Verificar código usando últimos 4 dígitos del remito
    # Formato remito: 0000-0000, últimos 4 dígitos = "0000" después del guión
    if entry['numero_remito'] and '-' in entry['numero_remito']:
        codigo_correcto = entry['numero_remito'].split('-')[-1]  # Últimos 4 dígitos
    else:
        codigo_correcto = entry['numero_remito'][-4:] if entry['numero_remito'] else ""

    if unfreeze_code != codigo_correcto:
        flash(f"⚠️ Código incorrecto. Use los últimos 4 dígitos del remito ({entry['numero_remito']}).", "error")
        return redirect(url_for("raypac.raypac_view", id=id))

    db.execute("""
        UPDATE raypac_entries
        SET is_frozen = FALSE, frozen_at = NULL
        WHERE id = %s
    """, (id,))
    db.commit()

    log_action(user['id'], "UNFREEZE", "raypac_entries", id, None, "Descongelado")

    flash("✅ Máquina descongelada correctamente.", "success")
    return redirect(url_for("raypac.raypac_view", id=id))


@raypac_bp.route("/<int:id>/recepcionar", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def raypac_recepcionar_dml(id):
    """DML recepciona el equipo y actualiza estado a RECIBIDO"""
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = %s", (id,)).fetchone()

    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac.raypac_list"))

    if not entry['is_frozen']:
        flash("El equipo debe estar enviado (freezado) para poder recepcionarlo.", "error")
        return redirect(url_for("raypac.raypac_view", id=id))

    if entry['estado_envio_equipos'] == 'RECIBIDO':
        flash("Este equipo ya fue recepcionado en DML.", "warning")
        return redirect(url_for("raypac.raypac_view", id=id))

    db.execute("""
        UPDATE raypac_entries
        SET estado_envio_equipos = 'RECIBIDO', updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (id,))
    db.commit()

    log_action(user['id'], "RECEPCIONAR", "raypac_entries", id, None,
              f"Equipo recepcionado en DML - Remito: {entry['numero_remito']}")

    flash("✅ Equipo recepcionado correctamente en DML.", "success")
    return redirect(url_for("raypac.raypac_view", id=id))
