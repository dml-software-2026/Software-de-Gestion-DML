# CODIGO_FUENTE/blueprints/notificaciones.py
from flask import Blueprint, render_template, request, redirect, url_for
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.decorators import login_required, role_required

notificaciones_bp = Blueprint('notificaciones', __name__, url_prefix='/admin')

@notificaciones_bp.route('/notificaciones', methods=['GET'])
@login_required
@role_required("ADMIN")
def listar_notificaciones():
    db = get_db()
    destinatarios = db.execute(
        "SELECT id, email, nombre, activo FROM usuarios_notificaciones ORDER BY email"
    ).fetchall()
    return render_template('notificaciones.html', destinatarios=destinatarios)


@notificaciones_bp.route('/notificaciones/agregar', methods=['POST'])
@login_required
@role_required("ADMIN")
def agregar_notificacion():
    email = request.form.get('email', '').strip()
    nombre = request.form.get('nombre', '').strip()
    if email:
        db = get_db()
        db.execute(
            "INSERT INTO usuarios_notificaciones (email, nombre, activo) VALUES (%s, %s, TRUE) "
            "ON CONFLICT (email) DO NOTHING",
            (email, nombre)
        )
        db.commit()
    return redirect(url_for('notificaciones.listar_notificaciones'))


@notificaciones_bp.route('/notificaciones/<int:id>/toggle', methods=['POST'])
@login_required
@role_required("ADMIN")
def toggle_notificacion(id):
    db = get_db()
    db.execute("UPDATE usuarios_notificaciones SET activo = NOT activo WHERE id = %s", (id,))
    db.commit()
    return redirect(url_for('notificaciones.listar_notificaciones'))


@notificaciones_bp.route('/notificaciones/<int:id>/eliminar', methods=['POST'])
@login_required
@role_required("ADMIN")
def eliminar_notificacion(id):
    db = get_db()
    db.execute("DELETE FROM usuarios_notificaciones WHERE id = %s", (id,))
    db.commit()
    return redirect(url_for('notificaciones.listar_notificaciones'))