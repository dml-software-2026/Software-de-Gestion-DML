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

stock_bp = Blueprint("stock", __name__, url_prefix="/stock")

def calcular_nivel_alerta(cantidad):
    if cantidad == 0:
        return "ROJO"
    elif cantidad == 1:
        return "AMARILLO"
    elif cantidad == 2:
        return "NARANJA"
    else:
        return "OK"

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

    # Query con filtro por ubicación
    query = """SELECT DISTINCT m.*, COALESCE(su.cantidad, 0) as cantidad
              FROM matriz_repuestos m
              LEFT JOIN stock_ubicaciones su ON su.codigo_repuesto = m.codigo_repuesto AND su.ubicacion = %s
              WHERE 1=1"""
    params = [ubicacion]

    if buscar:
        query += " AND (m.codigo_repuesto LIKE %s OR m.item LIKE %s)"
        params.extend([f"%{buscar}%", f"%{buscar}%"])

    stocks = db.execute(query + " ORDER BY m.codigo_repuesto", params).fetchall()

    # Agregar información de alerta
    stocks_con_alerta = []
    for stock in stocks:
        alerta = calcular_nivel_alerta(stock['cantidad'])
        stocks_con_alerta.append({
            **dict(stock),
            'alerta': alerta,
            'ubicacion': ubicacion
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
                         readonly=readonly)


@stock_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST", "RAYPAC")
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

            if not codigo or not item:
                flash("Código e Item son obligatorios.", "error")
                return render_template("stock_new.html", ubicacion=ubicacion)

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
                (codigo_repuesto, ubicacion, cantidad)
                VALUES (%s, %s, %s)
            """, (codigo, ubicacion, cantidad))
            db.commit()

            log_action(user['id'], "CREATE", "stock_ubicaciones", None, None,
                      f"{codigo} - {item} en {ubicacion}")

            flash(f"Repuesto {codigo} agregado al stock de {ubicacion}.", "success")
            return redirect(url_for("stock.stock_list", ubicacion=ubicacion))
        except Exception as e:
            flash(f"Error: {e!s}", "error")
            return render_template("stock_new.html", ubicacion=ubicacion, user=user)

    return render_template("stock_new.html", ubicacion=ubicacion, user=user)


@stock_bp.route("/<codigo>/edit", methods=["GET", "POST"])
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

            db.execute("""
                UPDATE stock_ubicaciones
                SET cantidad = %s, updated_at = CURRENT_TIMESTAMP
                WHERE codigo_repuesto = %s AND ubicacion = %s
            """, (cantidad, codigo, ubicacion))
            db.commit()

            log_action(user['id'], "UPDATE", "stock_ubicaciones", None,
                      f"Anterior: {stock['cantidad']}", f"Nuevo: {cantidad}")

            flash("Stock actualizado.", "success")
            return redirect(url_for("stock.stock_list", ubicacion=ubicacion))
        except Exception as e:
            flash(f"Error: {e!s}", "error")

    return render_template("stock_edit.html", stock=stock, ubicacion=ubicacion, user=user)


@stock_bp.route("/<codigo>/delete", methods=["POST"])
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
