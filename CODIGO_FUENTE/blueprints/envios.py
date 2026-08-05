import re
from datetime import datetime, date, timezone

from flask import Blueprint, request, render_template, redirect, url_for, flash

from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.decorators import login_required, role_required, get_current_user, log_action
from CODIGO_FUENTE.services.mail import send_mail
from CODIGO_FUENTE.services.stock import ajustar_stock_ubicacion, actualizar_estado_alerta_stock

envios_bp = Blueprint("envios", __name__, url_prefix="/envios")


@envios_bp.route("")
@login_required
@role_required("ADMIN", "RAYPAC", "DML_REPUESTOS", "DML_ST")
def envios_list():
    user = get_current_user()
    db = get_db()

    # Obtener envíos de repuestos
    envios_repuestos = db.execute(
        """
        SELECT e.*,
               'REPUESTO' as tipo_envio,
               (SELECT COUNT(*) FROM envios_repuestos_detalles d WHERE d.envio_id = e.id) AS items_count
        FROM envios_repuestos e
        ORDER BY e.created_at DESC
        """
    ).fetchall()

    # Obtener ingresos RAYPAC (equipos/máquinas) que fueron enviados
    envios_maquinas = db.execute(
        """
        SELECT
            id,
            'MAQUINA' as tipo_envio,
            numero_remito,
            numero_serie as numero_remito,
            fecha_recepcion as fecha_envio,
            NULL as fecha_recepcion,
            estado_envio_equipos as estado_envio,
            NULL as tipo_entrega,
            cliente || ' - ' || modelo_maquina as numero_remito_display,
            frozen_at as created_at,
            1 as items_count
        FROM raypac_entries
        WHERE is_frozen = TRUE
        ORDER BY frozen_at DESC
        """
    ).fetchall()

    # Combinar ambos tipos de envíos
    todos_envios = list(envios_repuestos) + list(envios_maquinas)
    # Ordenar por fecha de creación descendente
    def _sort_key(x):
        # Normaliza: envios_repuestos.created_at es TIMESTAMPTZ (datetime
        # CON zona horaria), pero raypac_entries.frozen_at (usado como
        # created_at para envíos de máquina) es DATE (sin hora ni zona).
        # Python no permite comparar un datetime "aware" con uno "naive",
        # así que todo se homogeneiza acá a datetime con tz UTC.
        val = x['created_at']
        if val is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if isinstance(val, datetime):
            if val.tzinfo is not None:
                return val
            return val.replace(tzinfo=timezone.utc)
        if isinstance(val, date):
            return datetime.combine(val, datetime.min.time(), tzinfo=timezone.utc)
        return datetime.min.replace(tzinfo=timezone.utc)
    todos_envios.sort(key=_sort_key, reverse=True)
    return render_template("envios_list.html", envios=todos_envios)

@envios_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def envios_new():
    user = get_current_user()
    db = get_db()

    stock_raypac = db.execute(
        """
        SELECT m.codigo_repuesto, m.item, COALESCE(su.cantidad, 0) AS cantidad
        FROM matriz_repuestos m
        LEFT JOIN stock_ubicaciones su ON su.codigo_repuesto = m.codigo_repuesto AND su.ubicacion = 'RAYPAC'
        ORDER BY m.codigo_repuesto
        """
    ).fetchall()

    if request.method == "POST":
        try:
            # Tipo de entrega
            tipo_entrega = request.form.get("tipo_entrega", "REPUESTOS")

            # OBLIGATORIO: Número de remito manual
            numero_remito_input = (request.form.get("numero_remito") or "").strip()

            if not numero_remito_input:
                flash("⚠️ El número de remito es OBLIGATORIO para enviar repuestos.", "error")
                return render_template("envios_form.html", stock=stock_raypac)

            # Auto-completar formato si solo ingresa 4 dígitos (últimos)
            if re.match(r'^\d{1,4}$', numero_remito_input):
                # Usuario ingresó solo números (1-4 dígitos), auto-completar
                ultimo = numero_remito_input.zfill(4)  # Rellenar con ceros a la izquierda
                numero_remito = f"00001-{ultimo}"  # Formato: 00001-XXXX
                flash(f"📋 Remito auto-completado: {numero_remito}", "info")
            elif re.match(r'^\d{4,5}-\d{4,7}$', numero_remito_input):
                numero_remito = numero_remito_input
            else:
                flash("⚠️ Formato de remito inválido. Ingresa solo los últimos 4 dígitos (ej: 4222) o el formato completo ####-#### (ej: 00001-04222).", "error")
                return render_template("envios_form.html", stock=stock_raypac)

            # Verificar que no exista ya en envios_repuestos
            existe = db.execute("SELECT id FROM envios_repuestos WHERE numero_remito = %s", (numero_remito,)).fetchone()
            if existe:
                flash(f"⚠️ El número de remito {numero_remito} ya existe en otro envío de repuestos.", "error")
                return render_template("envios_form.html", stock=stock_raypac)

            # Verificar que no exista en raypac_entries
            existe_raypac = db.execute("SELECT id FROM raypac_entries WHERE numero_remito = %s", (numero_remito,)).fetchone()
            if existe_raypac:
                flash(f"⚠️ El número de remito {numero_remito} ya fue usado para enviar un equipo. Usa un remito diferente.", "error")
                return render_template("envios_form.html", stock=stock_raypac)

            seleccionados = []

            # Procesar repuestos de la tabla principal
            for row in stock_raypac:
                qty_raw = (request.form.get(f"qty_{row['codigo_repuesto']}") or "0").strip()
                try:
                    qty = int(qty_raw or 0)
                except ValueError:
                    qty = 0
                if qty > 0:
                    seleccionados.append((row['codigo_repuesto'], row['item'], qty))

            # Procesar repuestos adicionales (no listados)
            for key in request.form.keys():
                if key.startswith('codigo_adicional_'):
                    idx = key.replace('codigo_adicional_', '')
                    codigo = request.form.get(f'codigo_adicional_{idx}', '').strip().upper()
                    descripcion = request.form.get(f'descripcion_adicional_{idx}', '').strip()
                    cantidad = request.form.get(f'cantidad_adicional_{idx}', '0').strip()

                    try:
                        qty = int(cantidad or 0)
                    except ValueError:
                        qty = 0

                    if codigo and qty > 0:
                        # Si no tiene descripción, buscarla en la matriz
                        if not descripcion:
                            rep = db.execute("SELECT item FROM matriz_repuestos WHERE codigo_repuesto = %s", (codigo,)).fetchone()
                            descripcion = rep['item'] if rep else f"Repuesto {codigo}"

                        seleccionados.append((codigo, descripcion, qty))

            if not seleccionados:
                flash("Selecciona al menos un repuesto con cantidad mayor a 0.", "error")
                return render_template("envios_form.html", stock=stock_raypac)

            fecha_envio = datetime.now().strftime("%Y-%m-%d")

            row = db.execute(
                """INSERT INTO envios_repuestos
                   (numero_remito, fecha_envio, tipo_entrega, estado_envio, is_frozen)
                   VALUES (%s, %s, %s, 'ENVIADO', TRUE)
                   RETURNING id""",
                (numero_remito, fecha_envio, tipo_entrega)
            ).fetchone()
            envio_id = row['id']

            # Guardar detalles del envío
            # IMPORTANTE: NO descontamos stock de RAYPAC (ellos no controlan stock desde este software)
            for codigo, item, qty in seleccionados:
                db.execute(
                    "INSERT INTO envios_repuestos_detalles (envio_id, codigo_repuesto, cantidad) VALUES (%s, %s, %s)",
                    (envio_id, codigo, qty)
                )

            db.commit()

            log_action(user['id'], "CREATE", "envios_repuestos", envio_id, None,
                      f"Remito {numero_remito} con {len(seleccionados)} items")

            flash(f"Envío generado: {numero_remito}", "success")
            return redirect(url_for("envios.envios_view", id=envio_id))
        except Exception as e:
            db.rollback()
            flash(f"Error al generar envío: {e}", "error")
            return render_template("envios_form.html", stock=stock_raypac)

    return render_template("envios_form.html", stock=stock_raypac)


@envios_bp.route("/<int:id>")
@login_required
@role_required("ADMIN", "RAYPAC", "DML_REPUESTOS", "DML_ST")
def envios_view(id):
    db = get_db()
    envio = db.execute("SELECT * FROM envios_repuestos WHERE id = %s", (id,)).fetchone()
    if not envio:
        flash("Envío no encontrado.", "error")
        return redirect(url_for("envios.envios_list"))
    detalles = db.execute(
        """
        SELECT d.*, m.item
        FROM envios_repuestos_detalles d
        LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = d.codigo_repuesto
        WHERE d.envio_id = %s
        ORDER BY d.codigo_repuesto
        """,
        (id,)
    ).fetchall()
    return render_template("envios_view.html", envio=envio, detalles=detalles)


@envios_bp.route("/<int:id>/confirmar", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS", "DML_ST")
def envios_confirmar(id):
    user = get_current_user()
    db = get_db()
    envio = db.execute("SELECT * FROM envios_repuestos WHERE id = %s", (id,)).fetchone()
    if not envio:
        flash("Envío no encontrado.", "error")
        return redirect(url_for("envios.envios_list"))
    # Verificar si ya fue recibido
    try:
        estado_envio = envio['estado_envio']
    except (KeyError, TypeError):
        estado_envio = None

    # Acceso directo sin .get() para sqlite3.Row
    fecha_recepcion_actual = envio['fecha_recepcion_dml'] if 'fecha_recepcion_dml' in envio.keys() else None

    if estado_envio == 'RECIBIDO' or fecha_recepcion_actual:
        flash("El envío ya fue confirmado.", "warning")
        return redirect(url_for("envios.envios_view", id=id))

    detalles = db.execute(
        "SELECT d.*, m.item FROM envios_repuestos_detalles d LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = d.codigo_repuesto WHERE d.envio_id = %s",
        (id,)
    ).fetchall()
    if not detalles:
        flash("No hay detalles de repuestos para este envío.", "error")
        return redirect(url_for("envios.envios_view", id=id))

    try:
        fecha_recepcion = datetime.now().strftime("%Y-%m-%d")

        # Actualizar stock DML con los repuestos recibidos
        for det in detalles:
            codigo = det['codigo_repuesto']
            qty = det['cantidad']

            # Agregar a stock de DML
            ajustar_stock_ubicacion(codigo, "DML", qty)
            actualizar_estado_alerta_stock(codigo)

        # Marcar envío como recibido
        db.execute(
            """UPDATE envios_repuestos
               SET estado_envio = 'RECIBIDO',
                   fecha_recepcion_dml = %s,
                   usuario_recepcion_id = %s,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = %s""",
            (fecha_recepcion, user['id'], id)
        )
        db.commit()

        log_action(user['id'], "CONFIRM", "envios_repuestos", id, None, "Recepción en DML")

        # Aviso a RAYPAC de recepción
        try:
            lineas = """
            <ul>
            %s
            </ul>
            """ % "\n".join([
                f"<li>{det['codigo_repuesto']} - {det['item'] or ''} x {det['cantidad']}</li>" for det in detalles
            ])
            html_body = f"""
            <h3>Confirmación de recepción de repuestos</h3>
            <p>Remito: <strong>{envio['numero_remito']}</strong></p>
            <p>Fecha recepción: {datetime.now().strftime('%Y-%m-%d')}</p>
            <p>Detalle:</p>
            {lineas}
            <p>Los repuestos fueron cargados en stock DML.</p>
            """
            send_mail("raypac@dml.local", f"Recepción remito {envio['numero_remito']} en DML", html_body)
        except Exception as e:
            print(f"Error enviando mail de recepción a Raypac: {e}")

        flash("Envío confirmado y stock actualizado.", "success")
        return redirect(url_for("envios.envios_view", id=id))
    except Exception as e:
        db.rollback()
        flash(f"Error al confirmar envío: {e}", "error")
        return redirect(url_for("envios.envios_view", id=id))


@envios_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def envios_edit(id):
    """Editar envío congelado (solo corrección de errores)"""
    user = get_current_user()
    db = get_db()

    envio = db.execute("SELECT * FROM envios_repuestos WHERE id = %s", (id,)).fetchone()
    if not envio:
        flash("Envío no encontrado.", "error")
        return redirect(url_for("envios.envios_list"))

    if request.method == "POST":
        try:
            nuevo_remito = request.form.get("numero_remito", "").strip()

            if not nuevo_remito:
                flash("El número de remito es obligatorio.", "error")
                return redirect(url_for("envios.envios_edit", id=id))

            # Verificar que no exista otro envío con ese remito
            existe = db.execute(
                "SELECT id FROM envios_repuestos WHERE numero_remito = %s AND id != %s",
                (nuevo_remito, id)
            ).fetchone()

            if existe:
                flash(f"Ya existe otro envío con el remito {nuevo_remito}.", "error")
                return redirect(url_for("envios.envios_edit", id=id))

            db.execute(
                "UPDATE envios_repuestos SET numero_remito = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (nuevo_remito, id)
            )
            db.commit()

            log_action(user['id'], "UPDATE", "envios_repuestos", id,
                      f"Remito: {envio['numero_remito']} → {nuevo_remito}",
                      "Corrección de remito")

            flash(f"✅ Remito actualizado a: {nuevo_remito}", "success")
            return redirect(url_for("envios.envios_view", id=id))

        except Exception as e:
            db.rollback()
            flash(f"Error al actualizar envío: {e}", "error")
            return redirect(url_for("envios.envios_edit", id=id))

    detalles = db.execute(
        """SELECT d.*, m.item
           FROM envios_repuestos_detalles d
           LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = d.codigo_repuesto
           WHERE d.envio_id = %s
           ORDER BY d.codigo_repuesto""",
        (id,)
    ).fetchall()

    return render_template("envios_edit.html", envio=envio, detalles=detalles)


@envios_bp.route("/<int:id>/unfreeze", methods=["POST"])
@login_required
@role_required("ADMIN")
def envios_unfreeze(id):
    """Desfreezar envío definitivamente (solo ADMIN con código)"""
    user = get_current_user()
    db = get_db()

    envio = db.execute("SELECT * FROM envios_repuestos WHERE id = %s", (id,)).fetchone()
    if not envio:
        flash("Envío no encontrado.", "error")
        return redirect(url_for("envios.envios_list"))

    # Verificar código de desfreeze (últimos 4 dígitos del remito)
    codigo = request.form.get("unfreeze_code", "").strip()
    remito_digitos = envio['numero_remito'][-4:]

    if codigo != remito_digitos:
        flash("❌ Código incorrecto. Ingresa los últimos 4 dígitos del remito.", "error")
        return redirect(url_for("envios.envios_view", id=id))

    try:
        db.execute(
            "UPDATE envios_repuestos SET is_frozen = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (id,)
        )
        db.commit()

        log_action(user['id'], "UNFREEZE", "envios_repuestos", id, None,
                  f"Envío descongelado por ADMIN")

        flash("🔓 Envío descongelado correctamente.", "success")
        return redirect(url_for("envios.envios_view", id=id))

    except Exception as e:
        db.rollback()
        flash(f"Error al descongelar envío: {e}", "error")
        return redirect(url_for("envios.envios_view", id=id))
