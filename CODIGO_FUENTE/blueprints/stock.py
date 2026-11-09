from flask import Blueprint, flash, redirect, render_template, request, url_for

from CODIGO_FUENTE.decorators import (
    get_current_user,
    log_action,
    login_required,
    permission_required,
    role_required,
    verify_admin_password,
)
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.stock import nivel_de_cantidad, verificar_alerta_stock
from CODIGO_FUENTE.services.ubicacion_fisica import (
    SIN_UBICACION,
    UBICACION_FISICA_MAX,
    normalizar_ubicacion_fisica,
)

stock_bp = Blueprint("stock", __name__, url_prefix="/stock")

# #309: roles que pueden cambiar la ubicación física (sin contraseña, a
# diferencia de Editar stock): DML_REPUESTOS es quien maneja el depósito.
ROLES_EDITAR_UBICACION = ("ADMIN", "DML_ST", "DML_REPUESTOS")



@stock_bp.route("")
@login_required
@permission_required(read_roles=["DML_ST"], write_roles=["DML_REPUESTOS", "RAYPAC"])

def stock_list(readonly=False):
    user = get_current_user()
    db = get_db()

    # Determinar ubicación según rol del usuario
    if user['role'] == 'RAYPAC':
        # RAYPAC solo ve su stock (RAYPAC)
        ubicacion = "RAYPAC"
    elif user['role'] in ['DML_REPUESTOS', 'DML_ST']:
        # DML_REPUESTOS y DML_ST ven stock de DML
        ubicacion = "DML"
    else:
        # ADMIN puede ver ambos (parámetro en URL)
        ubicacion = request.args.get("ubicacion", "DML")

    buscar = request.args.get("buscar", "")
    # #309: la ubicación física es solo del depósito de DML.
    mostrar_ubicacion_fisica = ubicacion == "DML"
    sin_ubicacion = mostrar_ubicacion_fisica and request.args.get("sin_ubicacion") == "1"

    # Query con filtro por ubicación
    query = """SELECT DISTINCT m.*, COALESCE(su.cantidad, 0) as cantidad,
                     su.id AS stock_id, su.codigo_ubicacion_fisica
              FROM matriz_repuestos m
              LEFT JOIN stock_ubicaciones su ON su.codigo_repuesto = m.codigo_repuesto AND su.ubicacion = %s
              WHERE 1=1"""
    params = [ubicacion]

    if buscar:
        # ILIKE: que "e05" encuentre "E05-F05-B02" (y lo mismo en código/descripción).
        if mostrar_ubicacion_fisica:
            query += " AND (m.codigo_repuesto ILIKE %s OR m.item ILIKE %s OR su.codigo_ubicacion_fisica ILIKE %s)"
            params.extend([f"%{buscar}%"] * 3)
        else:
            query += " AND (m.codigo_repuesto ILIKE %s OR m.item ILIKE %s)"
            params.extend([f"%{buscar}%"] * 2)

    if sin_ubicacion:
        query += """ AND (su.codigo_ubicacion_fisica IS NULL
                          OR TRIM(su.codigo_ubicacion_fisica) = ''
                          OR su.codigo_ubicacion_fisica = %s)"""
        params.append(SIN_UBICACION)

    stocks = db.execute(query + " ORDER BY m.codigo_repuesto", params).fetchall()

    # Agregar información de alerta
    stocks_con_alerta = []
    for stock in stocks:
        alerta = nivel_de_cantidad(stock['cantidad'])
        fisica = (stock['codigo_ubicacion_fisica'] or "").strip()
        stocks_con_alerta.append({
            **dict(stock),
            'alerta': alerta,
            'ubicacion': ubicacion,
            'ubicacion_fisica': "" if fisica in ("", SIN_UBICACION) else fisica,
        })

    # Para ADMIN, mostrar opción de cambiar ubicación
    ubicaciones_disponibles = []
    if user['role'] == 'ADMIN':
        ubicaciones_disponibles = ["RAYPAC", "DML"]

    return render_template("stock_list.html",
                         user=user,
                         rows=stocks_con_alerta,
                         ubicacion=ubicacion,
                         ubicaciones_disponibles=ubicaciones_disponibles,
                         readonly=readonly,
                         mostrar_ubicacion_fisica=mostrar_ubicacion_fisica,
                         sin_ubicacion=sin_ubicacion,
                         puede_editar_ubicacion=(mostrar_ubicacion_fisica
                                                 and user['role'] in ROLES_EDITAR_UBICACION),
                         ubicacion_fisica_max=UBICACION_FISICA_MAX)


@stock_bp.route("/<path:codigo>/ubicacion-fisica", methods=["POST"])
@login_required
@role_required(*ROLES_EDITAR_UBICACION)
def stock_ubicacion_fisica(codigo):
    """#309: cambiar el lugar físico de un repuesto en el depósito de DML.

    Botón propio en /stock, sin contraseña de ADMIN (a diferencia de Editar
    stock), porque solo toca la ubicación y no la cantidad.
    """
    user = get_current_user()
    db = get_db()
    ubicacion = "DML"

    # Volver al listado con la misma búsqueda/filtro que tenía la persona.
    volver = {"ubicacion": ubicacion}
    if request.form.get("buscar"):
        volver["buscar"] = request.form["buscar"]
    if request.form.get("sin_ubicacion") == "1":
        volver["sin_ubicacion"] = "1"

    nueva = normalizar_ubicacion_fisica(request.form.get("codigo_ubicacion_fisica"))
    if len(nueva) > UBICACION_FISICA_MAX:
        flash(f"La ubicación no puede tener más de {UBICACION_FISICA_MAX} caracteres.", "error")
        return redirect(url_for("stock.stock_list", **volver))

    stock = db.execute(
        "SELECT id, codigo_ubicacion_fisica FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = %s",
        (codigo, ubicacion)
    ).fetchone()
    if not stock:
        flash(f"El repuesto {codigo} no está cargado en el stock de {ubicacion}.", "error")
        return redirect(url_for("stock.stock_list", **volver))

    anterior = stock['codigo_ubicacion_fisica'] or SIN_UBICACION
    if anterior != nueva:
        db.execute("""
            UPDATE stock_ubicaciones
            SET codigo_ubicacion_fisica = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (nueva, stock['id']))
        db.commit()
        log_action(user['id'], "UPDATE", "stock_ubicaciones", stock['id'],
                   f"{codigo} ubicación: {anterior}", f"{codigo} ubicación: {nueva}")

    if nueva == SIN_UBICACION:
        flash(f"{codigo} quedó sin ubicación.", "warning")
    else:
        flash(f"Ubicación de {codigo} actualizada: {nueva}.", "success")
    return redirect(url_for("stock.stock_list", **volver))


@stock_bp.route("/new", methods=["GET", "POST"])
@login_required
# Los códigos nuevos los da de alta solo DML, no RAYPAC (pedido de David).
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS")
def stock_new():
    user = get_current_user()
    db = get_db()

    # Determinar ubicación según rol
    if user['role'] == 'RAYPAC':
        ubicacion = "RAYPAC"
    elif user['role'] == 'DML_REPUESTOS':
        ubicacion = "DML"
    else:
        ubicacion = request.args.get("ubicacion", "DML")  # ADMIN puede elegir

    if request.method == "POST":
        try:
            # Solo ADMIN necesita contraseña
            if user['role'] == 'ADMIN':
                admin_password = (request.form.get("admin_password") or "").strip()
                # #133: se confirma contra la contraseña del propio usuario
                # logueado (mismo mecanismo que el login), no un código fijo
                # separado que había que memorizar aparte.
                if not verify_admin_password(admin_password):
                    flash("Contraseña de administración incorrecta.", "error")
                    return render_template("stock_new.html", ubicacion=ubicacion, user=user)

            codigo = request.form.get("codigo_repuesto")
            item = request.form.get("item")
            cantidad = int(request.form.get("cantidad", 0))
            # #309 (b): lugar físico, opcional (vacío -> SIN UBICACIÓN). Solo
            # aplica al depósito de DML; en RAYPAC queda el default.
            ubicacion_fisica = SIN_UBICACION
            if ubicacion == "DML":
                ubicacion_fisica = normalizar_ubicacion_fisica(request.form.get("codigo_ubicacion_fisica"))

            if not codigo or not item:
                flash("Código e Item son obligatorios.", "error")
                # (antes faltaba user= y el template rompía al leer user.role)
                return render_template("stock_new.html", ubicacion=ubicacion, user=user)

            if len(ubicacion_fisica) > UBICACION_FISICA_MAX:
                flash(f"La ubicación no puede tener más de {UBICACION_FISICA_MAX} caracteres.", "error")
                return render_template("stock_new.html", ubicacion=ubicacion, user=user)

            # Verificar que el repuesto existe en matriz o crearlo
            existe_matriz = db.execute(
                "SELECT id FROM matriz_repuestos WHERE codigo_repuesto = %s",
                (codigo,)
            ).fetchone()

            if not existe_matriz:
                # Crear en matriz si no existe
                numero = db.execute("SELECT MAX(numero) as max FROM matriz_repuestos").fetchone()['max'] or 0
                db.execute("""
                    INSERT INTO matriz_repuestos
                    (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                    VALUES (%s, %s, %s, 0, 0, 'RAYPAC')
                """, (numero + 1, codigo, item))

            # Verificar que no existe en esa ubicación
            existe_stock = db.execute(
                "SELECT id FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = %s",
                (codigo, ubicacion)
            ).fetchone()

            if existe_stock:
                flash(f"Este repuesto ya existe en {ubicacion}.", "error")
                return render_template("stock_new.html", ubicacion=ubicacion, user=user)

            # Insertar en stock_ubicaciones
            db.execute("""
                INSERT INTO stock_ubicaciones
                (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
                VALUES (%s, %s, %s, %s)
            """, (codigo, ubicacion, cantidad, ubicacion_fisica))
            db.commit()

            detalle = f"{codigo} - {item} en {ubicacion}"
            if ubicacion == "DML":
                detalle += f" (ubicación: {ubicacion_fisica})"
            log_action(user['id'], "CREATE", "stock_ubicaciones", None, None, detalle)

            flash(f"Repuesto {codigo} agregado al stock de {ubicacion}.", "success")
            return redirect(url_for("stock.stock_list", ubicacion=ubicacion))
        except Exception as e:
            flash(f"Error: {e!s}", "error")
            return render_template("stock_new.html", ubicacion=ubicacion, user=user)

    return render_template("stock_new.html", ubicacion=ubicacion, user=user)


# path: el código puede traer "/" (ej. "PRUEBA 5/11"); con <codigo> la URL
# /stock/PRUEBA 5/11/edit daba 404. Lo mismo en ubicacion-fisica y delete.
@stock_bp.route("/<path:codigo>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def stock_edit(codigo):
    user = get_current_user()
    db = get_db()

    # Determinar ubicación según rol o parámetro
    if user['role'] == 'RAYPAC':
        ubicacion = "RAYPAC"
    elif user['role'] == 'DML_REPUESTOS':
        ubicacion = "DML"
    else:
        ubicacion = request.args.get("ubicacion", "DML")

    stock = db.execute(
        "SELECT * FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = %s",
        (codigo, ubicacion)
    ).fetchone()

    if not stock:
        flash("Repuesto no encontrado en " + ubicacion + ".", "error")
        return redirect(url_for("stock.stock_list"))

    if request.method == "POST":
        try:
            # Solo ADMIN necesita contraseña
            if user['role'] == 'ADMIN':
                admin_password = (request.form.get("admin_password") or "").strip()
                # #133: ver nota en stock_new sobre verify_admin_password().
                if not verify_admin_password(admin_password):
                    flash("Contraseña de administración incorrecta.", "error")
                    return render_template("stock_edit.html", stock=stock, ubicacion=ubicacion, user=user)

            cantidad = int(request.form.get("cantidad", 0))
            # #309 (b): en DML también se edita el lugar físico. En RAYPAC el
            # campo no se muestra y se conserva lo que había.
            ubicacion_fisica_anterior = stock['codigo_ubicacion_fisica'] or SIN_UBICACION
            ubicacion_fisica = ubicacion_fisica_anterior
            if ubicacion == "DML":
                ubicacion_fisica = normalizar_ubicacion_fisica(request.form.get("codigo_ubicacion_fisica"))
                if len(ubicacion_fisica) > UBICACION_FISICA_MAX:
                    flash(f"La ubicación no puede tener más de {UBICACION_FISICA_MAX} caracteres.", "error")
                    return render_template("stock_edit.html", stock=stock, ubicacion=ubicacion, user=user)

            db.execute("""
                UPDATE stock_ubicaciones
                SET cantidad = %s, codigo_ubicacion_fisica = %s, updated_at = CURRENT_TIMESTAMP
                WHERE codigo_repuesto = %s AND ubicacion = %s
            """, (cantidad, ubicacion_fisica, codigo, ubicacion))
            db.commit()
            verificar_alerta_stock(codigo, ubicacion, cantidad_anterior=stock['cantidad'])
            anterior, nuevo = f"Anterior: {stock['cantidad']}", f"Nuevo: {cantidad}"
            if ubicacion_fisica != ubicacion_fisica_anterior:
                anterior += f", ubicación: {ubicacion_fisica_anterior}"
                nuevo += f", ubicación: {ubicacion_fisica}"
            log_action(user['id'], "UPDATE", "stock_ubicaciones", None, anterior, nuevo)

            flash("Stock actualizado.", "success")
            return redirect(url_for("stock.stock_list", ubicacion=ubicacion))
        except Exception as e:
            flash(f"Error: {e!s}", "error")

    return render_template("stock_edit.html", stock=stock, ubicacion=ubicacion, user=user)


@stock_bp.route("/<path:codigo>/delete", methods=["POST"])
@login_required
@role_required("ADMIN")  # Solo ADMIN puede eliminar
def stock_delete(codigo):
    user = get_current_user()
    db = get_db()

    # Obtener ubicación del parámetro
    ubicacion = request.args.get("ubicacion", "DML")

    # Solo ADMIN necesita contraseña
    admin_password = (request.form.get("admin_password") or "").strip()
    # #133: ver nota en stock_new sobre verify_admin_password().
    if not verify_admin_password(admin_password):
        flash("Contraseña de administración incorrecta.", "error")
        return redirect(url_for("stock.stock_list", ubicacion=ubicacion))

    db.execute(
        "DELETE FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = %s",
        (codigo, ubicacion)
    )
    db.commit()

    log_action(user['id'], "DELETE", "stock_ubicaciones", None, codigo, None)

    flash(f"Repuesto eliminado del stock de {ubicacion}.", "success")
    return redirect(url_for("stock.stock_list", ubicacion=ubicacion))
