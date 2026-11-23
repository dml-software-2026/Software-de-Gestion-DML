from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from CODIGO_FUENTE.config import MANO_DE_OBRA_OPCIONES, TECNICOS_ST
from CODIGO_FUENTE.decorators import (
    get_current_user,
    log_action,
    login_required,
    permission_required,
    role_required,
    verify_admin_password,
)
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.flujo import build_flow_steps
from CODIGO_FUENTE.services.mail import get_destinatarios, send_mail
from CODIGO_FUENTE.services.numeracion import generate_ficha_number
from CODIGO_FUENTE.services.pdf import generar_pdf_ficha
from CODIGO_FUENTE.services.stock import (
    actualizar_estadistica_repuesto,
    ajustar_stock_ubicacion,
    verificar_alerta_stock,
)

dml_bp = Blueprint("dml", __name__, url_prefix="/dml")

# #274: estados que se pueden elegir desde el formulario de edición. Es la
# única fuente de la lista: dml_edit.html arma el <select> a partir de esta
# constante y dml_edit() rechaza cualquier valor que no esté acá (antes
# guardaba cualquier texto, ej. "A LA ESPERA DE REVISI%D3N" de un POST
# armado a mano). "MÁQUINA ENTREGADA" queda afuera a propósito (#157), el
# único camino a ese estado es "Cerrar Ficha".
ESTADOS_EDITABLES = [
    'A LA ESPERA DE REVISIÓN',
    'A LA ESPERA DE REPUESTOS',
    'A LA ESPERA DE APROBACIÓN DE PRESUPUESTO',  # #260
    'EN REPARACIÓN',
    'REPARADA',  # #329 - antes 'REPARACIÓN COMPLETADA'
    'MÁQUINA LISTA PARA RETIRAR',
]


def codigo_edicion_ficha(numero_remito_salida):
    """#333: código que pide editar una ficha ya recibida por RAYPAC: los
    últimos 4 dígitos del remito de salida de DML (el que viaja con la
    máquina de vuelta), mismo criterio que el desfreezado de un ingreso.
    "00001-04222" -> "4222". Vacío si la ficha no tiene remito."""
    digitos = "".join(c for c in (numero_remito_salida or "") if c.isdigit())
    return digitos[-4:]


def _ficha_desbloqueada(ficha_id):
    """#333: RAYPAC/ADMIN desbloquearon esta ficha con el código en esta sesión."""
    return ficha_id in session.get("fichas_desbloqueadas", [])


def _paso_flujo(ficha):
    """#158/#333: paso del tracker de 4 pasos. El 3ro ("Lista para retirar")
    es cuando DML la envía a RAYPAC; el 4to, cuando RAYPAC da el OK."""
    if ficha['fecha_entrega_cliente'] or ficha['is_closed']:
        return 4
    if ficha['enviada_raypac_at']:
        return 3
    return 2


def registrar_estado(db, ficha_id, estado, usuario_id):
    """#171: deja asentado un cambio de estado_reparacion en el historial
    de la ficha. No hace commit - va en la misma transacción que el UPDATE
    del estado, así nunca queda uno sin el otro."""
    db.execute(
        "INSERT INTO dml_fichas_historial (ficha_id, estado, usuario_id) VALUES (%s, %s, %s)",
        (ficha_id, estado, usuario_id),
    )


@dml_bp.route("")
@login_required
@permission_required(read_roles=["RAYPAC", "DML_REPUESTOS"], write_roles=["DML_ST"])
def dml_list(readonly=False):
    user = get_current_user()
    db = get_db()

    buscar = request.args.get("buscar", "")
    estado = request.args.get("estado", "")

    # Mismo patrón de búsqueda/filtro que tickets_list (#193) - las fichas
    # cerradas no entran acá a propósito, ya tienen su propia pantalla en
    # /dml/entregadas, no hace falta un toggle "mostrar cerrados" como en
    # tickets.
    query = """
        SELECT f.*, r.cliente, r.numero_serie
        FROM dml_fichas f
        LEFT JOIN raypac_entries r ON f.raypac_id = r.id
        WHERE f.is_closed = FALSE
    """
    params = []

    if buscar:
        query += """ AND (CAST(f.numero_ficha AS TEXT) LIKE %s
                       OR r.cliente ILIKE %s
                       OR r.numero_serie ILIKE %s
                       OR f.numero_ticket ILIKE %s)"""
        comodin = f"%{buscar}%"
        params.extend([comodin, comodin, comodin, comodin])

    if estado:
        query += " AND f.estado_reparacion = %s"
        params.append(estado)

    query += " ORDER BY f.created_at DESC"

    fichas = db.execute(query, params).fetchall()

    return render_template("dml_list.html", fichas=fichas, user_role=user['role'], readonly=readonly,
                            buscar=buscar, estado=estado)


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
           OR f.enviada_raypac_at IS NOT NULL  -- #333: enviadas, esperando el OK de RAYPAC
        ORDER BY f.is_closed ASC, f.fecha_entrega_cliente DESC, f.updated_at DESC
    """).fetchall()

    return render_template("dml_entregadas.html", fichas=fichas, user_role=user['role'])


@dml_bp.route("/new/<int:raypac_id>", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def dml_new(raypac_id):
    # #328: "Crear Ficha" ya no pasa por un formulario intermedio
    # (dml_form.html, eliminado): crea la ficha con lo que ya se sabe y
    # manda directo a la edición. Solo crea por POST (los botones son
    # <form method="POST">) para que un refresh, un link pegado o un
    # prefetch del navegador no generen fichas. Un GET (link viejo/pegado)
    # vuelve a la ficha si ya existe, o al ingreso RAYPAC si no.
    user = get_current_user()
    db = get_db()

    raypac = db.execute("SELECT * FROM raypac_entries WHERE id = %s", (raypac_id,)).fetchone()
    if not raypac:
        flash("Ingreso RAYPAC no encontrado.", "error")
        return redirect(url_for("raypac.raypac_list"))

    # #55: la ficha solo se puede crear despues de generar el ticket (se
    # bloquea acá también, no solo ocultando el botón). FOR UPDATE: dos
    # clics seguidos en "Crear Ficha" esperan uno al otro, y el segundo ve
    # el ficha_id que dejó el primero en vez de crear una ficha duplicada.
    ticket = db.execute(
        "SELECT * FROM tickets WHERE raypac_id = %s ORDER BY id DESC LIMIT 1"
        + (" FOR UPDATE" if request.method == "POST" else ""),
        (raypac_id,)
    ).fetchone()
    if not ticket:
        flash("Debe crear un ticket primero antes de generar la ficha.", "error")
        return redirect(url_for("raypac.raypac_view", id=raypac_id))

    if ticket['ficha_id']:
        db.rollback()  # libera el FOR UPDATE
        return redirect(url_for("dml.dml_edit", id=ticket['ficha_id']))

    if request.method != "POST":
        return redirect(url_for("raypac.raypac_view", id=raypac_id))

    try:
        # Fecha de ingreso = hoy (editable en la edición). No hay una fecha
        # guardada del "Dar de Alta en DML" para tomar en su lugar, y la
        # ficha se crea en DML después de recibir la máquina y hacer el ticket.
        fecha_ingreso = datetime.now().strftime("%Y-%m-%d")
        # El técnico viene del ticket (#327, obligatorio al crearlo).
        tecnico = ticket['tecnico_responsable'] or ""

        numero_ficha = generate_ficha_number()

        row = db.execute("""
            INSERT INTO dml_fichas
            (numero_ficha, raypac_id, ticket_id, numero_ticket, fecha_ingreso, tecnico,
             n_ciclos, tecnico_resp, estado_reparacion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (numero_ficha, raypac_id, ticket['id'], ticket['numero_ticket'], fecha_ingreso, tecnico,
              0, tecnico or None, 'A LA ESPERA DE REVISIÓN')).fetchone()

        ficha_id = row['id']

        registrar_estado(db, ficha_id, 'A LA ESPERA DE REVISIÓN', user['id'])

        db.execute("UPDATE tickets SET ficha_id = %s WHERE id = %s", (ficha_id, ticket['id']))

        # Partes estándar, con el estado que se cargó en la inspección
        # visual del ticket.
        ticket_to_parte = {
            'ESTADO DEL EQUIPO': 'estado_equipo',
            'CARCAZA': 'carcaza',
            'CUBRE FEEDWHEEL': 'cubre_feedwheel',
            'MANGO': 'mango',
            'BOTONES': 'botones',
            'MOTOR DE ARRASTRE': 'motor_arrastre',
            'MOTOR DE SELLADO': 'motor_sellado',
            'CUCHILLA': 'cuchilla',
            'SERVO': 'servo',
            'RUEDA DE ARRASTRE': 'rueda_arrastre',
            'RESORTE DE MANIJA': 'resorte_manija',
            'OTROS': 'otros',
        }
        for parte_nombre, ticket_col in ticket_to_parte.items():
            valor = ticket[ticket_col] if ticket_col in ticket.keys() else None
            if parte_nombre == "OTROS":
                # #330: OTROS es texto libre; vacío si no se escribió nada en el ticket
                estado = valor or ""
            else:
                estado = valor or "POR INSPECCIONAR"
            db.execute(
                "INSERT INTO dml_partes (ficha_id, nombre_parte, estado) VALUES (%s, %s, %s)",
                (ficha_id, parte_nombre, estado)
            )

        # Un solo commit: si algo falla no queda una ficha a medio crear
        # (antes había un commit antes de las partes).
        db.commit()

        log_action(user['id'], "CREATE", "dml_fichas", ficha_id, None,
                   f"Ficha DML #{numero_ficha} - Ticket: {ticket['numero_ticket']}")

        flash(f"Ficha #{numero_ficha} creada. Ticket: {ticket['numero_ticket']}", "success")
        return redirect(url_for("dml.dml_edit", id=ficha_id))
    except Exception as e:
        db.rollback()
        flash(f"No se pudo crear la ficha: {e!s}", "error")
        return redirect(url_for("raypac.raypac_view", id=raypac_id))


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

    # #158: tracker de 4 pasos (Ticket/Ficha/Entregada/Acuse) - es el tramo
    # del lado DML (ver raypac_view() para el tramo de 3 pasos del lado
    # RAYPAC). Ticket creado siempre está en "done" acá: dml_new() exige un
    # ticket existente antes de poder crear la ficha.
    current_step = _paso_flujo(ficha)
    flow_steps = build_flow_steps(
        ["Ticket creado", "Ficha en reparación", "Lista para retirar", "Acuse registrado"], current_step
    )

    # #171: historial de estados, del más reciente al más viejo.
    historial = db.execute("""
        -- La base (Supabase) guarda en UTC: se pasa a hora argentina acá
        -- para que la hora que ve RAYPAC sea la real.
        SELECT h.estado, h.fecha AT TIME ZONE 'America/Argentina/Buenos_Aires' AS fecha,
               u.nombre AS usuario
        FROM dml_fichas_historial h
        LEFT JOIN users u ON u.id = h.usuario_id
        WHERE h.ficha_id = %s
        ORDER BY h.fecha DESC, h.id DESC
    """, (id,)).fetchall()

    return render_template("dml_view.html", ficha=ficha, raypac=raypac, partes=partes, repuestos=repuestos,
                           user_role=user['role'], user_email=user['email'], readonly=readonly,
                           flow_steps=flow_steps, historial=historial)


@dml_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST", "RAYPAC")
def dml_edit(id):
    user = get_current_user()
    db = get_db()
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()

    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_list"))

    # #333: DML (ADMIN/DML_ST) edita libre hasta que RAYPAC da el OK de
    # recepción. Ya recibida (is_closed), solo la edita RAYPAC o ADMIN,
    # después de desbloquearla con el código (dml_desbloquear()).
    if ficha['is_closed']:
        if user['role'] not in ("ADMIN", "RAYPAC") or not _ficha_desbloqueada(id):
            flash("Esta ficha ya fue recibida por RAYPAC. Para editarla, RAYPAC (o ADMIN) "
                  "tiene que desbloquearla con el código desde la ficha.", "error")
            return redirect(url_for("dml.dml_view", id=id))
    elif user['role'] == "RAYPAC":
        flash("RAYPAC puede editar la ficha recién después de dar el OK de recepción.", "error")
        return redirect(url_for("dml.dml_view", id=id))

    if request.method == "POST":
        try:
            # Capturar SOLO los campos editables (no los de RAYPAC)
            fecha_ingreso = request.form.get("fecha_ingreso")
            # #176: "Fecha de Egreso" no es required (recién se completa al
            # cerrar la ficha) - el string vacío rompía el UPDATE de más
            # abajo (Postgres no acepta '' para una columna date).
            fecha_egreso = request.form.get("fecha_egreso") or None

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
            numero_remito = request.form.get("numero_remito_salida") or None
            tecnico_resp = request.form.get("tecnico_resp") or ""
            mano_de_obra = request.form.get("mano_de_obra") or None

            # #157: "MÁQUINA ENTREGADA" ya no es una opción del <select> (ver
            # dml_edit.html), pero valido igual por si llega un POST armado a
            # mano - el único camino a ese estado es "Cerrar Ficha", que corre
            # el checklist completo y marca is_closed=TRUE.
            if ficha['is_closed']:
                # #333: ya recibida por RAYPAC - el estado no se toca desde acá
                estado = ficha['estado_reparacion']
            elif estado == 'MÁQUINA ENTREGADA':
                flash("La ficha queda entregada cuando RAYPAC confirma la recepción.", "error")
                return redirect(url_for("dml.dml_edit", id=id))
            elif estado not in ESTADOS_EDITABLES:
                flash("Estado de reparación inválido. Elegí uno de la lista.", "error")
                return redirect(url_for("dml.dml_edit", id=id))

            # #327: técnico de la lista, vacío, o el texto viejo que ya tenía la ficha
            if tecnico_resp and tecnico_resp not in TECNICOS_ST and tecnico_resp != (ficha['tecnico_resp'] or ""):
                flash("Técnico responsable inválido. Elegí uno de la lista.", "error")
                return redirect(url_for("dml.dml_edit", id=id))

            # #331: una opción de la lista o vacío (opcional)
            if mano_de_obra and mano_de_obra not in MANO_DE_OBRA_OPCIONES:
                flash("Mano de obra inválida. Elegí una opción de la lista.", "error")
                return redirect(url_for("dml.dml_edit", id=id))

            # Validación de flujo lógico de estados según documento David
            # Orden lógico: A LA ESPERA DE REVISIÓN → EN REPARACIÓN → [A LA ESPERA DE REPUESTOS] → MÁQUINA LISTA PARA RETIRAR → MÁQUINA ENTREGADA
            estados_orden = {
                'A LA ESPERA DE REVISIÓN': 0,
                'REVISION_INICIAL': 0,  # alias legado, ver #44 - fichas creadas antes del fix
                'EN REPARACIÓN': 1,
                'EN REPARACION': 1,  # alias sin tilde, ver #44 - encoding legado en datos viejos
                'A LA ESPERA DE REPUESTOS': 1,  # Mismo nivel que EN REPARACIÓN (puede ir y volver)
                'A LA ESPERA DE APROBACIÓN DE PRESUPUESTO': 1,  # #260 - idem, espera externa sin que DML pueda avanzar
                'REPARADA': 2,  # #329
                'REPARACIÓN COMPLETADA': 2,  # alias legado de 'REPARADA', ver #329
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
                    tecnico_resp=%s, mano_de_obra=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id = %s
            """, (fecha_ingreso, fecha_egreso,
                  estado, diagnostico_rep, observaciones,
                  n_ciclos, mecanizado, horas, numero_remito,
                  tecnico_resp, mano_de_obra, id))
            # #171: solo si el estado cambió - guardar la ficha sin tocar el
            # estado (ej. solo observaciones) no es un paso nuevo del historial.
            if estado != ficha['estado_reparacion']:
                registrar_estado(db, id, estado, user['id'])
            db.commit()

            # Actualizar partes
            partes = db.execute("SELECT id, nombre_parte FROM dml_partes WHERE ficha_id = %s ORDER BY id", (id,)).fetchall()
            for idx, parte in enumerate(partes):
                estado_parte = request.form.get(f"parte_{idx}")
                if parte['nombre_parte'] == "OTROS":
                    # #330: texto libre, se puede dejar vacío
                    if estado_parte is not None:
                        db.execute(
                            "UPDATE dml_partes SET estado = %s WHERE id = %s",
                            (estado_parte.strip()[:500], parte['id'])
                        )
                    continue
                if estado_parte:
                    db.execute(
                        "UPDATE dml_partes SET estado = %s WHERE id = %s",
                        (estado_parte, parte['id'])
                    )
            db.commit()

            log_action(user['id'], "UPDATE", "dml_fichas", id, None, "Actualización ficha")

            # #333: el desbloqueo sirve para una edición; la próxima vuelve a pedir el código
            if ficha['is_closed']:
                session["fichas_desbloqueadas"] = [f for f in session.get("fichas_desbloqueadas", []) if f != id]

            flash("Ficha actualizada correctamente.", "success")
            return redirect(url_for("dml.dml_view", id=id))
        except Exception as e:
            db.rollback()  # Revertir la transacción en caso de error
            flash(f"Error: {e!s}", "error")

    # ORDER BY id: el POST mapea parte_{idx} por este mismo orden
    partes = db.execute("SELECT * FROM dml_partes WHERE ficha_id = %s ORDER BY id", (id,)).fetchall()
    repuestos = db.execute("SELECT * FROM dml_repuestos WHERE ficha_id = %s", (id,)).fetchall()

    # Convertir Row a dict para serialización JSON
    partes = [dict(p) for p in partes]
    repuestos = [dict(r) for r in repuestos]
    ficha = dict(ficha)

    # #158: mismo tracker que dml_view() - Facu pidió que también se vea acá,
    # no solo en la vista de solo lectura.
    current_step = _paso_flujo(ficha)
    flow_steps = build_flow_steps(
        ["Ticket creado", "Ficha en reparación", "Lista para retirar", "Acuse registrado"], current_step
    )

    return render_template("dml_edit.html", ficha=ficha, partes=partes, repuestos=repuestos, flow_steps=flow_steps,
                           estados_editables=ESTADOS_EDITABLES)


# ======================== REPUESTOS ========================

@dml_bp.route("/<int:id>/repuestos/agregar", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def agregar_repuesto(id):
    user = get_current_user()
    db = get_db()

    # #306: FOR UPDATE bloquea la ficha hasta el commit. Si llegan dos POST
    # seguidos (doble clic), el segundo espera acá a que termine el primero
    # y después ve el repuesto ya cargado (chequeo de duplicado de abajo).
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s FOR UPDATE", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_edit", id=id))
    if ficha['is_closed']:
        flash("La ficha ya fue recibida por RAYPAC: los repuestos no se modifican.", "error")
        return redirect(url_for("dml.dml_view", id=id))

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

    # #306: mismo criterio que dml_edit.html ("Este repuesto ya está agregado a
    # la ficha"), ahora también en el backend: frena el doble POST y que el
    # stock se descuente dos veces.
    ya_cargado = db.execute(
        "SELECT 1 FROM dml_repuestos WHERE ficha_id = %s AND codigo_repuesto = %s",
        (id, codigo)
    ).fetchone()
    if ya_cargado:
        db.rollback()  # suelta el FOR UPDATE
        flash(f"El repuesto '{codigo}' ya está agregado a la ficha.", "warning")
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
    else:
        en_stock = 0
        en_falta = 1
        estado_repuesto = "EN FALTA"

    # Insertar repuesto. #306: va ANTES de tocar el stock porque
    # actualizar_estadistica_repuesto() hace su propio commit (y eso suelta
    # el FOR UPDATE): así el repuesto ya queda guardado junto con el descuento.
    db.execute("""
        INSERT INTO dml_repuestos
        (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada, estado_repuesto, en_stock, en_falta)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (id, codigo, repuesto['item'], cantidad_utilizada, cantidad_utilizada, estado_repuesto, en_stock, en_falta))

    if en_stock:
        # Descontar del stock en DML usando ajustar_stock_ubicacion
        ajustar_stock_ubicacion(codigo, "DML", -cantidad_utilizada)
        # Actualizar estadísticas de uso (solo cuando el repuesto se usa de verdad)
        actualizar_estadistica_repuesto(codigo, cantidad_utilizada)
    db.commit()

    # (se sacó la llamada a actualizar_estadistica_repuesto que estaba acá)

    # Verificar alerta de stock después de descontar
    if en_stock:
        verificar_alerta_stock(codigo, cantidad_anterior=stock['cantidad'])

    log_action(user['id'], "ADD_PART", "dml_repuestos", id, None,
              f"{codigo} x{cantidad_utilizada} ({estado_repuesto})")

    if en_stock:
        flash(f"Repuesto '{codigo}' agregado (disponible en stock, descontado automáticamente).", "success")
    else:
        flash(f"Repuesto '{codigo}' agregado (⚠️ NO hay stock disponible - marcado EN FALTA).", "warning")

    return redirect(url_for("dml.dml_edit", id=id))


def _ficha_cerrada(ficha_id):
    """#333: True si RAYPAC ya dio el OK de recepción de la ficha."""
    fila = get_db().execute("SELECT is_closed FROM dml_fichas WHERE id = %s", (ficha_id,)).fetchone()
    return bool(fila and fila['is_closed'])


@dml_bp.route("/<int:ficha_id>/repuestos/mover-a-stock/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS")
def mover_repuesto_a_stock(ficha_id, repuesto_id):
    if _ficha_cerrada(ficha_id):
        flash("La ficha ya fue recibida por RAYPAC: los repuestos no se modifican.", "error")
        return redirect(url_for("dml.dml_view", id=ficha_id))

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
        SET en_stock = 1, en_falta = 0, estado_repuesto = 'EN STOCK'
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

    # Actualizar estadísticas de uso (se agrega esta línea)
    actualizar_estadistica_repuesto(repuesto['codigo_repuesto'], repuesto['cantidad_utilizada'])

    db.commit()

    verificar_alerta_stock(repuesto['codigo_repuesto'], cantidad_anterior=stock['cantidad'])

    log_action(user['id'], "MOVER_REPUESTO_A_STOCK", "dml_repuestos", repuesto_id,
              "EN FALTA", f"EN STOCK - {repuesto['codigo_repuesto']}")

    flash(f"✅ Repuesto {repuesto['codigo_repuesto']} movido a EN STOCK y descontado del inventario.", "success")
    return redirect(url_for("dml.dml_edit", id=ficha_id))


@dml_bp.route("/<int:ficha_id>/repuestos/eliminar/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def eliminar_repuesto(ficha_id, repuesto_id):
    if _ficha_cerrada(ficha_id):
        flash("La ficha ya fue recibida por RAYPAC: los repuestos no se modifican.", "error")
        return redirect(url_for("dml.dml_view", id=ficha_id))

    user = get_current_user()
    db = get_db()

    repuesto = db.execute("SELECT * FROM dml_repuestos WHERE id = %s AND ficha_id = %s", (repuesto_id, ficha_id)).fetchone()
    if not repuesto:
        flash("Repuesto no encontrado.", "error")
        return redirect(url_for("dml.dml_edit", id=ficha_id))

    # Si el repuesto estaba en stock, devolverlo a ubicación DML
    if repuesto['en_stock']:
        ajustar_stock_ubicacion(repuesto['codigo_repuesto'], "DML", repuesto['cantidad_utilizada'])

        # Restar de estadísticas (reversar el uso): 1 uso menos, y la cantidad
        # real utilizada menos — no restar cantidad_utilizada de total_usos,
        # que cuenta "veces", no "unidades". GREATEST evita negativos.
        db.execute("""
            UPDATE estadisticas_repuestos
            SET total_usos = GREATEST(total_usos - 1, 0),
                cantidad_utilizada = GREATEST(cantidad_utilizada - %s, 0),
                updated_at = CURRENT_TIMESTAMP
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

@dml_bp.route("/<int:id>/close", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def dml_close(id):
    """#333: "Enviar a RAYPAC". Corre el checklist de siempre, deja la ficha
    en MÁQUINA LISTA PARA RETIRAR, cierra el ticket y avisa al comercial.
    La ficha NO queda cerrada: DML la puede seguir editando hasta que RAYPAC
    da el OK de recepción (dml_registrar_acuse()), que es lo que la cierra."""
    user = get_current_user()
    db = get_db()

    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_list"))

    if ficha['is_closed'] or ficha['enviada_raypac_at']:
        flash("Esta ficha ya se envió a RAYPAC.", "info")
        return redirect(url_for("dml.dml_view", id=id))

    # VALIDACIONES OBLIGATORIAS antes de enviar
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

    # 5. #226: no se puede cerrar con repuestos EN FALTA (criterio de David).
    # Una ficha sin repuestos (solo mano de obra) no entra acá y cierra normal.
    repuestos_en_falta = db.execute(
        "SELECT codigo_repuesto FROM dml_repuestos WHERE ficha_id = %s AND en_falta = 1",
        (id,)
    ).fetchall()
    if repuestos_en_falta:
        codigos = ", ".join(r['codigo_repuesto'] for r in repuestos_en_falta)
        errores.append(f"Hay repuestos EN FALTA que impiden el cierre: {codigos}")

    if errores:
        flash("⚠️ No se puede enviar la ficha a RAYPAC. Campos requeridos faltantes:", "error")
        for error in errores:
            flash(f"• {error}", "error")
        return redirect(url_for("dml.dml_edit", id=id))

    try:
        # Cerrar la ficha y marcar como entregada. #156: usar el valor
        # canonico real ('MÁQUINA ENTREGADA', el mismo del <select> de
        # dml_edit.html y de estados_orden/color map) en vez del 'ENTREGADA'
        # suelto que dejaba la ficha en un estado huerfano - mismo patron
        # de bug que el #44, pero en el flujo de cierre en vez del de alta.
        # #333: ya no cierra la ficha - queda enviada, esperando el OK de RAYPAC.
        fecha_egreso = datetime.now().strftime("%Y-%m-%d")
        db.execute("""
            UPDATE dml_fichas
            SET enviada_raypac_at = CURRENT_TIMESTAMP, fecha_egreso = %s,
                estado_reparacion = 'MÁQUINA LISTA PARA RETIRAR', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (fecha_egreso, id))
        if ficha['estado_reparacion'] != 'MÁQUINA LISTA PARA RETIRAR':
            registrar_estado(db, id, 'MÁQUINA LISTA PARA RETIRAR', user['id'])

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
                                 html_body,
                                 cc=get_destinatarios("MAQUINA_LISTA"))
            mail_status = "enviada" if mail_sent else "fallida (revisar logs)"
        else:
            mail_status = "sin email configurado"

        log_action(user['id'], "UPDATE", "dml_fichas", id, None,
                  f"Ficha enviada a RAYPAC - Notificación {mail_status} - Comercial: {raypac['comercial'] if raypac else 'N/A'}")

        categoria = "success" if mail_status == "enviada" else "warning"
        flash(f"✅ Ficha #{ficha['numero_ficha']} enviada a RAYPAC. Queda esperando que RAYPAC confirme la recepción. "
              f"Notificación {mail_status}.", categoria)
        return redirect(url_for("dml.dml_view", id=id))
    except Exception as e:
        db.rollback()
        flash(f"Error al enviar la ficha: {e!s}", "error")
        return redirect(url_for("dml.dml_view", id=id))


@dml_bp.route("/<int:id>/acuse", methods=["POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def dml_registrar_acuse(id):
    """Registra el acuse de recibo de una máquina entregada."""
    user = get_current_user()
    db = get_db()

    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_entregadas"))

    # #333: el OK de recepción es para fichas que DML ya envió. Las cerradas
    # antes del #333 (estado 'MÁQUINA ENTREGADA', o el alias legado
    # 'ENTREGADA' del #156) también pueden registrarlo, como hasta ahora.
    if not (ficha['enviada_raypac_at'] or ficha['is_closed']
            or ficha['estado_reparacion'] in ('MÁQUINA ENTREGADA', 'ENTREGADA')):
        flash("DML todavía no envió esta ficha a RAYPAC.", "error")
        return redirect(url_for("dml.dml_view", id=id))
    if ficha['recibido_por']:
        flash("La recepción de esta ficha ya está registrada.", "info")
        return redirect(url_for("dml.dml_view", id=id))

    try:
        fecha_entrega = request.form.get("fecha_entrega_cliente")
        recibido_por = request.form.get("recibido_por", "").strip()
        observaciones = request.form.get("observaciones_entrega", "").strip()

        if not fecha_entrega or not recibido_por:
            flash("La fecha de entrega y el nombre de quien recibe son obligatorios.", "error")
            return redirect(url_for("dml.dml_entregadas"))

        # #333: el OK de RAYPAC cierra el circuito: la ficha queda entregada
        # (is_closed) y desde acá solo la edita RAYPAC/ADMIN con código.
        db.execute("""
            UPDATE dml_fichas
            SET fecha_entrega_cliente = %s, recibido_por = %s,
                is_closed = TRUE, estado_reparacion = 'MÁQUINA ENTREGADA',
                observaciones = CASE
                    WHEN observaciones IS NOT NULL AND observaciones != ''
                    THEN observaciones || ' | ENTREGA: ' || %s
                    ELSE 'ENTREGA: ' || %s
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (fecha_entrega, recibido_por, observaciones, observaciones, id))
        if ficha['estado_reparacion'] != 'MÁQUINA ENTREGADA':
            registrar_estado(db, id, 'MÁQUINA ENTREGADA', user['id'])

        db.commit()

        log_action(user['id'], "UPDATE", "dml_fichas", id, None,
                  f"Acuse de recibo registrado - Recibido por: {recibido_por}")

        flash(f"✅ Recepción confirmada: la Ficha #{ficha['numero_ficha']} queda entregada.", "success")

    except Exception as e:
        db.rollback()
        flash(f"Error al registrar la recepción: {e!s}", "error")

    return redirect(url_for("dml.dml_view", id=id))


@dml_bp.route("/<int:id>/desbloquear", methods=["POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def dml_desbloquear(id):
    """#333: habilita editar una ficha ya recibida. RAYPAC pone los últimos 4
    dígitos del remito de salida (como el desfreezado); ADMIN puede usar ese
    código o su propia contraseña (#133)."""
    user = get_current_user()
    db = get_db()
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_entregadas"))

    if not ficha['is_closed']:
        flash("La ficha todavía no fue recibida por RAYPAC: no hace falta desbloquearla.", "info")
        return redirect(url_for("dml.dml_view", id=id))

    codigo = request.form.get("codigo", "").strip()
    codigo_correcto = codigo_edicion_ficha(ficha['numero_remito_salida'])
    valido = bool(codigo_correcto) and codigo == codigo_correcto
    if not valido and user['role'] == "ADMIN":
        valido = verify_admin_password(codigo)
    if not valido:
        flash("Código incorrecto. Son los últimos 4 dígitos del remito de salida de DML.", "error")
        return redirect(url_for("dml.dml_view", id=id))

    desbloqueadas = [f for f in session.get("fichas_desbloqueadas", []) if f != id]
    session["fichas_desbloqueadas"] = desbloqueadas + [id]
    log_action(user['id'], "UPDATE", "dml_fichas", id, None, "Ficha recibida desbloqueada para editar")
    db.commit()
    return redirect(url_for("dml.dml_edit", id=id))


# ======================== PDF DE FICHA ========================
# NOTA: esta ruta se agregó en un checkpoint posterior al resto del
# archivo - en la primera pasada de extracción no se había visto todavía
# (estaba ubicada mas adelante en el app.py original, cerca del bloque de
# usuarios/admin, aunque su URL es /dml/... y por eso corresponde aca).
#
# #134: existía también generar_ficha() (POST /generar-ficha), código
# huérfano - ningún template la llamaba. Se eliminó: lo que hacía (generar
# el PDF, avisar por mail al comercial que la máquina está lista) ya lo
# cubren descargar_ficha_pdf() de acá abajo y dml_close() ("Cerrar Ficha",
# manda el mismo mail de "MÁQUINA LISTA PARA RETIRAR"), y el flag que
# marcaba (ficha_generada, más ticket_enviado) no lo leía nada en código
# vivo - quedan sin usar en el schema, no se tocaron.

@dml_bp.route("/<int:id>/pdf", methods=["GET"])
@login_required
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS", "RAYPAC")
def descargar_ficha_pdf(id):
    """Genera y descarga el PDF de una ficha de reparación."""
    user = get_current_user()
    db = get_db()

    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_list"))

     # Generar PDF on-demand
    pdf_bytes = generar_pdf_ficha(id)
    if not pdf_bytes:
        flash("No se pudo generar el PDF.", "error")
        return redirect(url_for("dml.dml_view", id=id))
    log_action(user['id'], "DOWNLOAD_FICHA_PDF", "dml_fichas", id, None,
              f"Ficha #{ficha['numero_ficha']}")
    # Devolver PDF
    return send_file(BytesIO(pdf_bytes), mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"FICHA_{ficha['numero_ficha']:07d}.pdf")  # #332: en mayúscula


@dml_bp.route("/<int:id>/enviar-pdf", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS", "RAYPAC")
def enviar_ficha_pdf(id):
    """#171: manda el PDF de la ficha al mail del usuario logueado - mismos
    roles que descargar_ficha_pdf(), para que RAYPAC lo reciba sin depender
    de que alguien de DML se lo pase."""
    user = get_current_user()
    db = get_db()

    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = %s", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml.dml_list"))

    pdf_bytes = generar_pdf_ficha(id)
    if not pdf_bytes:
        flash("No se pudo generar el PDF.", "error")
        return redirect(url_for("dml.dml_view", id=id))

    numero = f"{ficha['numero_ficha']:07d}"
    html_body = f"""
    <p>Hola{(' ' + user['nombre']) if user['nombre'] else ''},</p>
    <p>Te adjuntamos la ficha de servicio técnico <strong>#{numero}</strong>
    (estado actual: <strong>{ficha['estado_reparacion']}</strong>).</p>
    <p>Sistema de Gestión DML</p>
    """
    enviado = send_mail(user['email'], f"Ficha DML #{numero}", html_body,
                        attachments=[(f"FICHA_{numero}.pdf", pdf_bytes)])  # #332

    if enviado:
        log_action(user['id'], "SEND_FICHA_PDF", "dml_fichas", id, None,
                   f"Ficha #{ficha['numero_ficha']} a {user['email']}")
        flash(f"Te enviamos el PDF de la ficha a {user['email']}.", "success")
    else:
        flash("No se pudo enviar el mail. Probá de nuevo más tarde o descargá el PDF.", "error")
    return redirect(url_for("dml.dml_view", id=id))
