import re
from datetime import UTC, date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from CODIGO_FUENTE.decorators import (
    get_current_user,
    log_action,
    login_required,
    role_required,
)
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.avisos import ids_sin_ver, marcar_visto
from CODIGO_FUENTE.services.mail import get_destinatarios_activos, send_mail
from CODIGO_FUENTE.services.stock import (
    actualizar_estado_alerta_stock,
    ajustar_stock_ubicacion,
)

envios_bp = Blueprint("envios", __name__, url_prefix="/envios")


@envios_bp.route("")
@login_required
@role_required("ADMIN", "RAYPAC", "DML_REPUESTOS", "DML_ST")
def envios_list():
    user = get_current_user()
    db = get_db()

    # ?estado=todos muestra también los recibidos; por defecto se ocultan
    mostrar_recibidos = request.args.get("estado") == "todos"

    # Estos fragmentos son fijos (no vienen del usuario): el parámetro de la
    # URL solo elige cuál de los dos usar, así que no hay riesgo de inyección SQL.
    filtro_repuestos = "" if mostrar_recibidos else "WHERE COALESCE(e.estado_envio, '') <> 'RECIBIDO'"
    filtro_maquinas = "" if mostrar_recibidos else (
        "AND NOT (f.fecha_entrega_cliente IS NOT NULL "
        "OR (f.numero_remito_salida IS NULL AND COALESCE(r.estado_envio_equipos, '') = 'RECIBIDO'))"
    )

    envios_repuestos = db.execute(
        f"""
        SELECT e.*,
               'REPUESTO' as tipo_envio,
               (SELECT COUNT(*) FROM envios_repuestos_detalles d WHERE d.envio_id = e.id) AS items_count
        FROM envios_repuestos e
        {filtro_repuestos}
        ORDER BY e.created_at DESC
        """
    ).fetchall()

    envios_maquinas = db.execute(
        f"""
        SELECT
            r.id,
            'MAQUINA' as tipo_envio,
            r.numero_remito,
            r.fecha_recepcion as fecha_envio,
            NULL as fecha_recepcion,
            CASE
                WHEN f.fecha_entrega_cliente IS NOT NULL THEN 'ENTREGADO'
                WHEN f.numero_remito_salida IS NOT NULL THEN 'EN_TRANSITO_VUELTA'
                WHEN r.estado_envio_equipos = 'RECIBIDO' THEN 'RECIBIDO'
                WHEN r.estado_envio_equipos = 'ENVIADO' THEN 'ENVIADO'
                ELSE 'PENDIENTE'
            END as estado_envio,
            NULL as tipo_entrega,
            r.cliente || ' - ' || r.modelo_maquina as numero_remito_display,
            r.frozen_at as created_at,
            1 as items_count
        FROM raypac_entries r
        LEFT JOIN LATERAL (
            SELECT * FROM dml_fichas
            WHERE raypac_id = r.id
            ORDER BY created_at DESC
            LIMIT 1
        ) f ON TRUE
        WHERE r.is_frozen = TRUE
        {filtro_maquinas}
        ORDER BY r.frozen_at DESC
        """
    ).fetchall()

    # Ordenar cada lista por fecha de creación descendente por separado
    def _sort_key(x):
        # Normaliza: envios_repuestos.created_at es TIMESTAMPTZ (datetime
        # CON zona horaria), pero raypac_entries.frozen_at (usado como
        # created_at para envíos de máquina) es DATE (sin hora ni zona).
        # Python no permite comparar un datetime "aware" con uno "naive",
        # así que todo se homogeneiza acá a datetime con tz UTC.
        val = x['created_at']
        if val is None:
            return datetime.min.replace(tzinfo=UTC)
        if isinstance(val, datetime):
            if val.tzinfo is not None:
                return val
            return val.replace(tzinfo=UTC)
        if isinstance(val, date):
            return datetime.combine(val, datetime.min.time(), tzinfo=UTC)
        return datetime.min.replace(tzinfo=UTC)

    envios_repuestos = sorted(envios_repuestos, key=_sort_key, reverse=True)
    envios_maquinas = sorted(envios_maquinas, key=_sort_key, reverse=True)
    return render_template(
        "envios_list.html",
        envios_repuestos=envios_repuestos,
        envios_maquinas=envios_maquinas,
        mostrar_recibidos=mostrar_recibidos,
        # #170: filas que este usuario todavía no vio (resaltadas en la tabla)
        sin_ver={"MAQUINA": ids_sin_ver(user, "MAQUINA"), "REPUESTO": ids_sin_ver(user, "REPUESTO")},
    )
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
            if re.match(r'^\d{1,8}$', numero_remito_input):
                # Autocompletar con el prefijo estándar 00001-, siempre 8 dígitos del lado derecho
                ultimo = numero_remito_input.zfill(8)  # Rellenar con ceros a la izquierda hasta completar 8 dígitos
                numero_remito = f"00001-{ultimo}"  # Formato: 00001-XXXXXXXX (8 dígitos)
                flash(f"📋 Remito auto-completado: {numero_remito}", "info")
            elif re.match(r'^\d{4,5}-\d{8}$', numero_remito_input):
                numero_remito = numero_remito_input
            else:
                flash("⚠️ Formato de remito inválido. Ingresa solo los dígitos del remito (ej: 4222 o 2568) o el formato completo #####-######## (ej: 00001-00004222).", "error")
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
                    # Sin descripción propia: la de la matriz se lee con un JOIN al mostrarlo
                    seleccionados.append((row['codigo_repuesto'], None, qty))

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
            for codigo, descripcion, qty in seleccionados:
                db.execute(
                    "INSERT INTO envios_repuestos_detalles (envio_id, codigo_repuesto, cantidad, descripcion) VALUES (%s, %s, %s, %s)",
                    (envio_id, codigo, qty, descripcion)
                )

            db.commit()

            log_action(user['id'], "CREATE", "envios_repuestos", envio_id, None,
                      f"Remito {numero_remito} con {len(seleccionados)} items")
            # Aviso de nuevo envío (si falla, no debe romper la creación)
            try:
                items_html = "".join(f"<li>{c} - {i} x {q}</li>" for c, i, q in seleccionados)
                html = f"""
                <h3>📦 Nuevo envío de repuestos</h3>
                <p>Remito: <strong>{numero_remito}</strong></p>
                <p>Tipo de entrega: {tipo_entrega}</p>
                <ul>{items_html}</ul>
                """
                for email in get_destinatarios_activos():
                    send_mail(email, f"📦 Nuevo envío {numero_remito}", html)
            except Exception as e:
                print(f"Error enviando aviso de nuevo envío: {e}")
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
    # Campanita de DML (#170): abrir el detalle saca el envío de "sin ver"
    marcar_visto(get_current_user(), "REPUESTO", id)
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
    recibido = envio['estado_envio'] == 'RECIBIDO' or bool(envio['fecha_recepcion_dml'])
    puede_recibir = not recibido and get_current_user()['role'] in ('ADMIN', 'DML_REPUESTOS', 'DML_ST')
    return render_template("envios_view.html", envio=envio, detalles=detalles,
                           recibido=recibido, puede_recibir=puede_recibir)


@envios_bp.route("/<int:id>/confirmar", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS", "DML_ST")
def envios_confirmar(id):
    user = get_current_user()
    db = get_db()
    # FOR UPDATE: si llegan dos confirmaciones a la vez (doble click, dos
    # personas), la segunda espera a que termine la primera y ya lo ve
    # RECIBIDO - sin esto el stock se sumaría dos veces.
    envio = db.execute("SELECT * FROM envios_repuestos WHERE id = %s FOR UPDATE", (id,)).fetchone()
    if not envio:
        flash("Envío no encontrado.", "error")
        return redirect(url_for("envios.envios_list"))

    if envio['estado_envio'] == 'RECIBIDO' or envio['fecha_recepcion_dml']:
        db.rollback()
        flash("El envío ya fue confirmado.", "warning")
        return redirect(url_for("envios.envios_view", id=id))

    detalles = db.execute(
        """SELECT d.*, m.item
           FROM envios_repuestos_detalles d
           LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = d.codigo_repuesto
           WHERE d.envio_id = %s
           ORDER BY d.codigo_repuesto""",
        (id,)
    ).fetchall()
    if not detalles:
        db.rollback()
        flash("No hay detalles de repuestos para este envío.", "error")
        return redirect(url_for("envios.envios_view", id=id))

    # Cantidad que DML contó de cada renglón (#57). El campo viene precargado
    # con la del remito; si falta (form viejo) se toma esa misma.
    recibidos = {}
    for det in detalles:
        valor = (request.form.get(f"recibido_{det['id']}") or str(det['cantidad'])).strip()
        try:
            recibidos[det['id']] = int(valor)
        except ValueError:
            recibidos[det['id']] = -1
        if recibidos[det['id']] < 0:
            db.rollback()
            flash(f"Cantidad recibida inválida para {det['codigo_repuesto']}.", "error")
            return redirect(url_for("envios.envios_view", id=id))

    try:
        codigos_nuevos = []

        # Todo en una sola transacción: si un renglón falla no se suma nada
        # (antes cada renglón se commiteaba por separado y un error a mitad
        # de camino dejaba stock cargado con el envío todavía "en tránsito").
        for det in detalles:
            codigo = det['codigo_repuesto']
            qty = recibidos[det['id']]

            if qty > 0 and det['item'] is None:
                # Repuesto no listado: se da de alta en la matriz con la
                # descripción que cargó RAYPAC, si no stock_ubicaciones lo
                # rechaza por la FK.
                numero = db.execute("SELECT COALESCE(MAX(numero), 0) + 1 AS n FROM matriz_repuestos").fetchone()['n']
                descripcion = det['descripcion'] or f"Repuesto {codigo}"
                nuevo = db.execute(
                    """INSERT INTO matriz_repuestos
                       (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                       VALUES (%s, %s, %s, 0, 0, 'DML')
                       ON CONFLICT (codigo_repuesto) DO NOTHING
                       RETURNING id""",
                    (numero, codigo, descripcion)
                ).fetchone()
                if nuevo:
                    codigos_nuevos.append((codigo, descripcion))

            if qty > 0:
                ajustar_stock_ubicacion(codigo, "DML", qty)

            db.execute(
                "UPDATE envios_repuestos_detalles SET cantidad_recibida = %s WHERE id = %s",
                (qty, det['id'])
            )

        db.execute(
            """UPDATE envios_repuestos
               SET estado_envio = 'RECIBIDO',
                   fecha_recepcion_dml = %s,
                   usuario_recepcion_id = %s,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = %s""",
            (datetime.now().strftime("%Y-%m-%d"), user['id'], id)
        )
        db.commit()
    except Exception as e:
        db.rollback()
        flash(f"Error al confirmar envío: {e}", "error")
        return redirect(url_for("envios.envios_view", id=id))

    # A partir de acá la recepción ya está guardada: lo que falle (alertas,
    # mails) solo se loguea, no deshace nada.
    for codigo in {det['codigo_repuesto'] for det in detalles}:
        try:
            actualizar_estado_alerta_stock(codigo)
        except Exception as e:
            db.rollback()
            print(f"Error actualizando alerta de stock de {codigo}: {e}")

    diferencias = [det for det in detalles if recibidos[det['id']] != det['cantidad']]
    log_action(user['id'], "CONFIRM", "envios_repuestos", id, None,
               f"Recepción en DML ({len(diferencias)} diferencias con el remito)")

    _avisar_recepcion_a_raypac(envio, detalles, recibidos)
    if codigos_nuevos:
        _avisar_codigos_nuevos(envio, codigos_nuevos)
        for codigo, descripcion in codigos_nuevos:
            flash(f"Se dio de alta el código nuevo {codigo} ({descripcion}) en la matriz de repuestos.", "info")

    if diferencias:
        flash(f"Envío recibido con {len(diferencias)} diferencia(s) respecto del remito. "
              "El stock se cargó con lo recibido.", "warning")
    else:
        flash("Envío confirmado y stock actualizado.", "success")
    return redirect(url_for("envios.envios_view", id=id))


def _avisar_recepcion_a_raypac(envio, detalles, recibidos):
    """Mail a RAYPAC con lo recibido, marcando las diferencias con el remito."""
    try:
        lineas = []
        for det in detalles:
            descripcion = det['item'] or det['descripcion'] or ''
            recibido = recibidos[det['id']]
            linea = f"{det['codigo_repuesto']} - {descripcion}: remito {det['cantidad']}, recibido {recibido}"
            if recibido != det['cantidad']:
                linea = f"<strong style='color:#b02a37'>{linea} (DIFERENCIA)</strong>"
            lineas.append(f"<li>{linea}</li>")
        html_body = f"""
        <h3>Confirmación de recepción de repuestos</h3>
        <p>Remito: <strong>{envio['numero_remito']}</strong></p>
        <p>Fecha recepción: {datetime.now().strftime('%Y-%m-%d')}</p>
        <p>Detalle:</p>
        <ul>{''.join(lineas)}</ul>
        <p>Los repuestos fueron cargados en stock DML con las cantidades recibidas.</p>
        """
        send_mail("raypac@dml.local", f"Recepción remito {envio['numero_remito']} en DML", html_body)
    except Exception as e:
        print(f"Error enviando mail de recepción a Raypac: {e}")


def _avisar_codigos_nuevos(envio, codigos_nuevos):
    """Mail a los destinatarios de Admin → Notificaciones por cada código
    que se dio de alta solo en la matriz al recibir un envío (#57)."""
    try:
        db = get_db()
        destinatarios = db.execute(
            "SELECT email FROM usuarios_notificaciones WHERE activo = TRUE"
        ).fetchall()
        items = "".join(f"<li><strong>{codigo}</strong> - {descripcion}</li>" for codigo, descripcion in codigos_nuevos)
        html_body = f"""
        <h3>Nuevos códigos de repuesto en la matriz</h3>
        <p>Al recibir el remito <strong>{envio['numero_remito']}</strong> llegaron repuestos que
        no estaban en la matriz y se dieron de alta automáticamente:</p>
        <ul>{items}</ul>
        <p>Revisá que la descripción sea correcta desde la sección Stock.</p>
        """
        for destinatario in destinatarios:
            send_mail(destinatario["email"], f"Nuevo código de repuesto (remito {envio['numero_remito']})", html_body)
    except Exception as e:
        print(f"Error enviando aviso de códigos nuevos: {e}")


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
                  "Envío descongelado por ADMIN")

        flash("🔓 Envío descongelado correctamente.", "success")
        return redirect(url_for("envios.envios_view", id=id))

    except Exception as e:
        db.rollback()
        flash(f"Error al descongelar envío: {e}", "error")
        return redirect(url_for("envios.envios_view", id=id))
