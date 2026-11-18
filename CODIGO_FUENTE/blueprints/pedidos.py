"""Pedidos de repuestos de RAYPAC a DML (#341, parte a del #308).

RAYPAC arma el pedido sobre el stock de DML (ve la cantidad, sin ubicación)
y a DML le llega el aviso por campanita y mail. Mientras está PEDIDO, RAYPAC
lo puede corregir o cancelar; cuando DML lo marca EN_PREPARACION ya no.
El envío (ENVIADO) y la recepción (RECIBIDO) son la parte b (#342).
"""
import sys

from flask import Blueprint, flash, redirect, render_template, request, url_for

from CODIGO_FUENTE.decorators import get_current_user, log_action, login_required, role_required
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.avisos import ids_sin_ver, marcar_visto, reiniciar_vistos
from CODIGO_FUENTE.services.mail import get_destinatarios, send_mail

pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")

ROLES_VEN = ("ADMIN", "RAYPAC", "DML_REPUESTOS")
ROLES_PIDEN = ("ADMIN", "RAYPAC")
ROLES_PREPARAN = ("ADMIN", "DML_REPUESTOS")
OBSERVACIONES_MAX = 500

ESTADOS = {
    "PEDIDO": ("Pedido", "bg-primary"),
    "EN_PREPARACION": ("En preparación en DML", "bg-info text-dark"),
    "ENVIADO": ("Enviado", "bg-warning text-dark"),
    "RECIBIDO": ("Recibido en RAYPAC", "bg-success"),
    "CANCELADO": ("Cancelado", "bg-secondary"),
}
ACTIVOS = ("PEDIDO", "EN_PREPARACION", "ENVIADO")


def _stock_dml(db):
    """Stock de DML para armar el pedido: código, ítem y cuánto hay (sin ubicación, #308)."""
    return db.execute("""
        SELECT su.codigo_repuesto, COALESCE(m.item, '') AS item, su.cantidad
        FROM stock_ubicaciones su
        LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = su.codigo_repuesto
        WHERE su.ubicacion = 'DML'
        ORDER BY su.codigo_repuesto
    """).fetchall()


def _leer_form(stock):
    """Devuelve (renglones [(codigo, cantidad)], observaciones) o None si hay un error (ya flasheado)."""
    renglones = []
    for fila in stock:
        texto = (request.form.get(f"qty_{fila['codigo_repuesto']}") or "").strip()
        if not texto or texto == "0":
            continue
        if not texto.isdigit():
            flash(f"Cantidad inválida para {fila['codigo_repuesto']}: tiene que ser un número entero.", "error")
            return None
        renglones.append((fila['codigo_repuesto'], int(texto)))
    if not renglones:
        flash("El pedido está vacío: cargá la cantidad de al menos un repuesto.", "error")
        return None
    observaciones = " ".join((request.form.get("observaciones") or "").split())
    if len(observaciones) > OBSERVACIONES_MAX:
        flash(f"Las observaciones no pueden tener más de {OBSERVACIONES_MAX} caracteres.", "error")
        return None
    return renglones, observaciones or None


def _valores_desde_request(stock):
    return {
        "cantidades": {f["codigo_repuesto"]: request.form.get(f"qty_{f['codigo_repuesto']}", "") for f in stock},
        "observaciones": request.form.get("observaciones", ""),
    }


def _guardar_renglones(db, pedido_id, renglones):
    for codigo, cantidad in renglones:
        db.execute(
            "INSERT INTO pedidos_repuestos_detalles (pedido_id, codigo_repuesto, cantidad) VALUES (%s, %s, %s)",
            (pedido_id, codigo, cantidad)
        )


def _detalles(db, pedido_id):
    return db.execute("""
        SELECT d.codigo_repuesto, d.cantidad, COALESCE(m.item, '') AS item, su.cantidad AS stock_dml
        FROM pedidos_repuestos_detalles d
        LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = d.codigo_repuesto
        LEFT JOIN stock_ubicaciones su ON su.codigo_repuesto = d.codigo_repuesto AND su.ubicacion = 'DML'
        WHERE d.pedido_id = %s
        ORDER BY d.codigo_repuesto
    """, (pedido_id,)).fetchall()


def _avisar_pedido_nuevo(pedido_id, renglones, observaciones, user):
    """Mail a DML (#341, respuesta 3.1 de David). Si falla, no rompe el pedido."""
    try:
        items = "".join(f"<li>{codigo} x {cantidad}</li>" for codigo, cantidad in renglones)
        obs = f"<p>Observaciones: {observaciones}</p>" if observaciones else ""
        html = (
            f"<h3>🛒 Nuevo pedido de repuestos de RAYPAC (#{pedido_id})</h3>"
            f"<p>Lo cargó {user['nombre'] or user['email']}.</p><ul>{items}</ul>{obs}"
            f"<p><a href=\"{url_for('pedidos.pedidos_view', id=pedido_id, _external=True)}\">Ver el pedido</a></p>"
        )
        for email in get_destinatarios("NUEVO_INGRESO"):
            send_mail(email, f"🛒 Nuevo pedido de repuestos #{pedido_id}", html)
    except Exception as e:
        print(f"Error enviando aviso de pedido de repuestos: {e}", file=sys.stderr, flush=True)


def _pedido_para_cambiar(db, id, estados_validos):
    """El pedido bloqueado para escribir, o None (con flash) si no existe o no está en un estado válido."""
    pedido = db.execute("SELECT * FROM pedidos_repuestos WHERE id = %s FOR UPDATE", (id,)).fetchone()
    if not pedido:
        db.rollback()
        flash("Pedido no encontrado.", "error")
        return None
    if pedido["estado"] not in estados_validos:
        db.rollback()
        flash(f"El pedido está «{ESTADOS[pedido['estado']][0]}» y ya no se puede cambiar así.", "warning")
        return None
    return pedido


@pedidos_bp.app_context_processor
def _estados_pedido():
    return {"ESTADOS_PEDIDO": ESTADOS}


@pedidos_bp.route("")
@login_required
@role_required(*ROLES_VEN)
def pedidos_list():
    db = get_db()
    todos = request.args.get("estado") == "todos"
    filtro = "" if todos else "WHERE p.estado IN %s"
    pedidos = db.execute(f"""
        SELECT p.*, u.nombre AS creado_por_nombre,
               (SELECT COUNT(*) FROM pedidos_repuestos_detalles d WHERE d.pedido_id = p.id) AS items,
               (SELECT COALESCE(SUM(d.cantidad), 0) FROM pedidos_repuestos_detalles d WHERE d.pedido_id = p.id) AS unidades
        FROM pedidos_repuestos p
        LEFT JOIN users u ON u.id = p.creado_por
        {filtro}
        ORDER BY p.created_at DESC, p.id DESC
    """, () if todos else (ACTIVOS,)).fetchall()
    return render_template("pedidos_list.html", pedidos=pedidos, todos=todos,
                           sin_ver=ids_sin_ver(get_current_user(), "PEDIDO"))


@pedidos_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required(*ROLES_PIDEN)
def pedidos_new():
    user = get_current_user()
    db = get_db()
    stock = _stock_dml(db)

    if request.method == "POST":
        datos = _leer_form(stock)
        if not datos:
            return render_template("pedidos_form.html", stock=stock, pedido=None, valores=_valores_desde_request(stock))
        renglones, observaciones = datos
        try:
            pedido_id = db.execute(
                "INSERT INTO pedidos_repuestos (observaciones, creado_por) VALUES (%s, %s) RETURNING id",
                (observaciones, user["id"])
            ).fetchone()["id"]
            _guardar_renglones(db, pedido_id, renglones)
            db.commit()
        except Exception as e:
            db.rollback()
            flash(f"Error al guardar el pedido: {e}", "error")
            return render_template("pedidos_form.html", stock=stock, pedido=None, valores=_valores_desde_request(stock))

        log_action(user["id"], "CREATE", "pedidos_repuestos", pedido_id, None,
                   f"Pedido #{pedido_id} con {len(renglones)} repuesto(s)")
        _avisar_pedido_nuevo(pedido_id, renglones, observaciones, user)
        flash(f"Pedido #{pedido_id} enviado a DML. Lo podés corregir o cancelar hasta que lo empiecen a preparar.",
              "success")
        return redirect(url_for("pedidos.pedidos_view", id=pedido_id))

    return render_template("pedidos_form.html", stock=stock, pedido=None,
                           valores={"cantidades": {}, "observaciones": ""})


@pedidos_bp.route("/<int:id>")
@login_required
@role_required(*ROLES_VEN)
def pedidos_view(id):
    db = get_db()
    user = get_current_user()
    pedido = db.execute("""
        SELECT p.*, u.nombre AS creado_por_nombre
        FROM pedidos_repuestos p LEFT JOIN users u ON u.id = p.creado_por
        WHERE p.id = %s
    """, (id,)).fetchone()
    if not pedido:
        flash("Pedido no encontrado.", "error")
        return redirect(url_for("pedidos.pedidos_list"))
    marcar_visto(user, "PEDIDO", id)  # campanita de DML: abrirlo lo saca de "sin ver"
    pendiente = pedido["estado"] == "PEDIDO"
    return render_template("pedidos_view.html", pedido=pedido, detalles=_detalles(db, id),
                           puede_editar=pendiente and user["role"] in ROLES_PIDEN,
                           puede_preparar=pendiente and user["role"] in ROLES_PREPARAN)


@pedidos_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*ROLES_PIDEN)
def pedidos_edit(id):
    user = get_current_user()
    db = get_db()
    pedido = _pedido_para_cambiar(db, id, ("PEDIDO",))
    if not pedido:
        return redirect(url_for("pedidos.pedidos_view", id=id))
    stock = _stock_dml(db)

    if request.method == "POST":
        datos = _leer_form(stock)
        if not datos:
            db.rollback()
            return render_template("pedidos_form.html", stock=stock, pedido=pedido, valores=_valores_desde_request(stock))
        renglones, observaciones = datos
        try:
            db.execute(
                "UPDATE pedidos_repuestos SET observaciones = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (observaciones, id)
            )
            db.execute("DELETE FROM pedidos_repuestos_detalles WHERE pedido_id = %s", (id,))
            _guardar_renglones(db, id, renglones)
            reiniciar_vistos("PEDIDO", id)  # cambió: DML lo tiene que volver a ver
            db.commit()
        except Exception as e:
            db.rollback()
            flash(f"Error al guardar el pedido: {e}", "error")
            return render_template("pedidos_form.html", stock=stock, pedido=pedido, valores=_valores_desde_request(stock))
        log_action(user["id"], "UPDATE", "pedidos_repuestos", id, None,
                   f"Pedido #{id} corregido: {len(renglones)} repuesto(s)")
        flash("Pedido actualizado.", "success")
        return redirect(url_for("pedidos.pedidos_view", id=id))

    cantidades = {d["codigo_repuesto"]: d["cantidad"] for d in _detalles(db, id)}
    db.rollback()  # libera el FOR UPDATE: en el GET no se escribe nada
    return render_template("pedidos_form.html", stock=stock, pedido=pedido,
                           valores={"cantidades": cantidades, "observaciones": pedido["observaciones"] or ""})


def _cambiar_estado(id, desde, hacia, accion, mensaje):
    user = get_current_user()
    db = get_db()
    if not _pedido_para_cambiar(db, id, (desde,)):
        return redirect(url_for("pedidos.pedidos_view", id=id))
    db.execute("UPDATE pedidos_repuestos SET estado = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (hacia, id))
    db.commit()
    log_action(user["id"], accion, "pedidos_repuestos", id, desde, hacia)
    flash(mensaje, "success")
    return redirect(url_for("pedidos.pedidos_view", id=id))


@pedidos_bp.route("/<int:id>/cancelar", methods=["POST"])
@login_required
@role_required(*ROLES_PIDEN)
def pedidos_cancelar(id):
    return _cambiar_estado(id, "PEDIDO", "CANCELADO", "UPDATE", f"Pedido #{id} cancelado.")


@pedidos_bp.route("/<int:id>/preparar", methods=["POST"])
@login_required
@role_required(*ROLES_PREPARAN)
def pedidos_preparar(id):
    return _cambiar_estado(id, "PEDIDO", "EN_PREPARACION", "UPDATE",
                           f"Pedido #{id} en preparación. RAYPAC ya no lo puede cambiar.")
