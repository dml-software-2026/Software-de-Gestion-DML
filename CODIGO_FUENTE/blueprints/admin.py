import csv
import os
import sys

from flask import Blueprint, request, render_template, redirect, url_for, flash
from werkzeug.security import generate_password_hash

from CODIGO_FUENTE.config import BASE_DIR
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.decorators import login_required, role_required, get_current_user, log_action

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ======================== USUARIOS ========================

@admin_bp.route("/usuarios")
@login_required
@role_required("ADMIN")
def usuarios_list():
    db = get_db()
    user = get_current_user()
    usuarios = db.execute("SELECT * FROM users ORDER BY email").fetchall()
    return render_template("usuarios_list.html", usuarios=usuarios, user=user)


@admin_bp.route("/cargar-stock-csv", methods=["POST", "GET"])
@login_required
@role_required("ADMIN")
def cargar_stock_desde_web():
    """Endpoint para cargar stock desde el CSV en producción"""
    output = []
    try:
        # Ruta al CSV
        csv_path = os.path.join(BASE_DIR, "DOCUMENTOS DML", "Copia de NUEVO STOCK DE REPUESTOS COMPLETO.csv")
        output.append(f"[STOCK] Buscando CSV: {csv_path}")
        print(f"[STOCK] Buscando CSV: {csv_path}", file=sys.stderr, flush=True)

        if not os.path.exists(csv_path):
            output.append("[STOCK] ❌ Archivo CSV no encontrado")
            return "<br>".join(output), 404

        output.append("[STOCK] ✅ CSV encontrado, iniciando carga...")
        print("[STOCK] ✅ CSV encontrado", file=sys.stderr, flush=True)

        db = get_db()
        repuestos_cargados = 0
        repuestos_actualizados = 0
        errores = 0

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')

            # Saltar las primeras 4 filas (encabezados)
            for _ in range(4):
                next(reader, None)

            for idx, row in enumerate(reader, start=1):
                if len(row) < 11:
                    continue

                try:
                    # Extraer datos
                    codigo = row[2].strip() if len(row) > 2 and row[2] else None
                    item = row[3].strip() if len(row) > 3 and row[3] else None
                    cantidad_str = row[4].strip() if len(row) > 4 and row[4] else "0"
                    codigo_ubicacion = row[9].strip() if len(row) > 9 and row[9] else "SIN UBICACIÓN"

                    if not codigo or not item:
                        continue

                    # Limpiar y convertir cantidad
                    cantidad_str = cantidad_str.replace(',', '')
                    try:
                        cantidad = int(float(cantidad_str))
                    except:
                        errores += 1
                        continue

                    if cantidad <= 0:
                        continue

                    # 1. Insertar o actualizar en matriz_repuestos
                    cursor = db.execute("SELECT id FROM matriz_repuestos WHERE codigo_repuesto = %s", (codigo,))
                    existe_matriz = cursor.fetchone()

                    if not existe_matriz:
                        numero_correlativo = idx
                        db.execute("""
                            INSERT INTO matriz_repuestos (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                            VALUES (%s, %s, %s, %s, %s, 'DML')
                        """, (numero_correlativo, codigo, item, cantidad, cantidad))
                        repuestos_cargados += 1
                    else:
                        db.execute("""
                            UPDATE matriz_repuestos
                            SET item = %s, cantidad_actual = %s
                            WHERE codigo_repuesto = %s
                        """, (item, cantidad, codigo))
                        repuestos_actualizados += 1

                    # 2. Insertar o actualizar en stock_ubicaciones (DML)
                    cursor = db.execute("""
                        SELECT id FROM stock_ubicaciones
                        WHERE codigo_repuesto = %s AND ubicacion = 'DML'
                    """, (codigo,))

                    existe_stock = cursor.fetchone()

                    if not existe_stock:
                        db.execute("""
                            INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
                            VALUES (%s, 'DML', %s, %s)
                        """, (codigo, cantidad, codigo_ubicacion))
                    else:
                        db.execute("""
                            UPDATE stock_ubicaciones
                            SET cantidad = %s, codigo_ubicacion_fisica = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE codigo_repuesto = %s AND ubicacion = 'DML'
                        """, (cantidad, codigo_ubicacion, codigo))

                except Exception as e:
                    errores += 1
                    continue

        db.commit()

        output.append(f"[STOCK] ✅ Carga completada!")
        output.append(f"[STOCK] 📦 Repuestos nuevos: {repuestos_cargados}")
        output.append(f"[STOCK] 🔄 Repuestos actualizados: {repuestos_actualizados}")
        output.append(f"[STOCK] ⚠️ Errores: {errores}")

        print(f"[STOCK] Nuevos: {repuestos_cargados}, Actualizados: {repuestos_actualizados}, Errores: {errores}",
              file=sys.stderr, flush=True)

        result = "<br>".join(output)
        result += "<br><br><a href='/stock'>Ver Stock Cargado</a>"
        return result, 200

    except Exception as e:
        import traceback
        error_msg = str(e)
        trace = traceback.format_exc()
        output.append(f"[STOCK] ❌ Error: {error_msg}")
        print(f"[STOCK] ❌ Error: {error_msg}", file=sys.stderr, flush=True)
        print(trace, file=sys.stderr, flush=True)

        result = "<br>".join(output)
        result += f"<br><br><pre>{trace}</pre>"
        return result, 500


@admin_bp.route("/usuarios/nueva", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def usuario_new():
    user = get_current_user()
    db = get_db()

    if request.method == "POST":
        try:
            email = request.form.get("email")
            password = request.form.get("password")
            nombre = request.form.get("nombre")
            role = request.form.get("role")

            roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]

            if not all([email, password, role]):
                flash("Completa los campos obligatorios.", "error")
                return render_template("usuario_form.html", roles=roles)

            existe = db.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
            if existe:
                flash("Este email ya existe.", "error")
                return render_template("usuario_form.html", roles=roles)

            hash_pwd = generate_password_hash(password)
            db.execute("""
                INSERT INTO users (email, password_hash, nombre, role, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
            """, (email, hash_pwd, nombre, role))
            db.commit()

            log_action(user['id'], "CREATE", "users", None, None, f"{email} - {role}")

            flash(f"Usuario {email} creado.", "success")
            return redirect(url_for("admin.usuarios_list"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")

    roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]
    return render_template("usuario_form.html", roles=roles)


@admin_bp.route("/usuarios/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def usuario_edit(id):
    user = get_current_user()
    db = get_db()
    usuario = db.execute("SELECT * FROM users WHERE id = %s", (id,)).fetchone()

    if not usuario:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("admin.usuarios_list"))

    if request.method == "POST":
        try:
            role = request.form.get("role")
            new_password = (request.form.get("password") or "").strip()

            if not role:
                flash("Selecciona un rol.", "error")
                return redirect(url_for("admin.usuario_edit", id=id))

            if new_password:
                hash_pwd = generate_password_hash(new_password)
                db.execute(
                    "UPDATE users SET role = %s, password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (role, hash_pwd, id)
                )
            else:
                db.execute(
                    "UPDATE users SET role = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (role, id)
                )
            db.commit()

            log_action(user['id'], "UPDATE", "users", id, None, f"{usuario['email']}")

            if new_password:
                flash("Usuario actualizado y contraseña cambiada.", "success")
            else:
                flash("Usuario actualizado.", "success")
            return redirect(url_for("admin.usuarios_list"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")

    roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]
    return render_template("usuario_edit.html", target_user=usuario, roles=roles)


@admin_bp.route("/usuarios/<int:id>/toggle", methods=["POST"])
@login_required
@role_required("ADMIN")
def usuario_toggle(id):
    user = get_current_user()
    db = get_db()
    usuario = db.execute("SELECT * FROM users WHERE id = %s", (id,)).fetchone()

    if not usuario:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("admin.usuarios_list"))

    # is_active ahora es BOOLEAN en Postgres (antes era INTEGER 0/1 en
    # SQLite), por eso el toggle pasó de "1 - valor" a un "not" simple.
    nuevo_estado = not usuario['is_active']
    db.execute("UPDATE users SET is_active = %s WHERE id = %s", (nuevo_estado, id))
    db.commit()

    log_action(user['id'], "TOGGLE", "users", id, str(usuario['is_active']), str(nuevo_estado))

    estado_texto = "activado" if nuevo_estado else "desactivado"
    flash(f"Usuario {estado_texto} correctamente.", "success")
    return redirect(url_for("admin.usuarios_list"))
