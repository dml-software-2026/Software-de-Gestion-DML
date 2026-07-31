import csv
from datetime import datetime
from io import StringIO

from flask import Blueprint, request, render_template, make_response

from extensions import get_db
from decorators import login_required, role_required, permission_required, get_current_user

estadisticas_bp = Blueprint("estadisticas", __name__)


@estadisticas_bp.route("/estadisticas")
@login_required
@permission_required(read_roles=["DML_ST"], write_roles=["DML_REPUESTOS"])
def estadisticas(readonly=False):
    """Dashboard de estadísticas de repuestos más utilizados."""
    user = get_current_user()
    db = get_db()

    # Determinar ubicación según rol
    if user['role'] == 'ADMIN':
        ubicacion = request.args.get("ubicacion", "DML")
        ubicaciones_disponibles = ["RAYPAC", "DML"]
    else:
        ubicacion = "DML"  # DML_REPUESTOS y DML_ST solo ven DML
        ubicaciones_disponibles = []

    # Top 10 repuestos más utilizados (solo tiene sentido para DML, donde se usan en reparaciones)
    if ubicacion == "DML":
        top_repuestos = db.execute("""
            SELECT
                e.codigo_repuesto,
                e.item,
                e.total_usos,
                e.cantidad_utilizada,
                e.fecha_ultimo_uso,
                COALESCE(su.cantidad, 0) as stock_actual
            FROM estadisticas_repuestos e
            LEFT JOIN stock_ubicaciones su ON su.codigo_repuesto = e.codigo_repuesto AND su.ubicacion = 'DML'
            ORDER BY e.total_usos DESC
            LIMIT 10
        """).fetchall()
    else:
        # RAYPAC no tiene "top usos" porque no usa repuestos, solo envía
        top_repuestos = []

    # Repuestos críticos (stock bajo) por ubicación
    repuestos_criticos = db.execute("""
        SELECT
            su.codigo_repuesto,
            m.item,
            su.cantidad as stock_actual,
            su.ubicacion
        FROM stock_ubicaciones su
        LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = su.codigo_repuesto
        WHERE su.cantidad <= 2 AND su.ubicacion = ?
        ORDER BY su.cantidad ASC
    """, (ubicacion,)).fetchall()

    # Estadísticas generales
    stats = {
        "total_repuestos": db.execute("SELECT COUNT(*) as cnt FROM matriz_repuestos").fetchone()['cnt'],
        "repuestos_en_ubicacion": db.execute(
            "SELECT COUNT(*) as cnt FROM stock_ubicaciones WHERE ubicacion = ?",
            (ubicacion,)
        ).fetchone()['cnt'],
        "total_movimientos": db.execute("SELECT SUM(total_usos) as total FROM estadisticas_repuestos").fetchone()['total'] or 0 if ubicacion == "DML" else 0,
        "fichas_completadas": db.execute("SELECT COUNT(*) as cnt FROM dml_fichas WHERE is_closed = 1").fetchone()['cnt'] if ubicacion == "DML" else 0,
    }

    return render_template(
        "estadisticas.html",
        user=user,
        top_repuestos=top_repuestos,
        repuestos_criticos=repuestos_criticos,
        stats=stats,
        ubicacion=ubicacion,
        ubicaciones_disponibles=ubicaciones_disponibles,
        readonly=readonly
    )


# ======================== EXPORTACIONES CSV ========================

@estadisticas_bp.route("/export/fichas-csv")
@login_required
@role_required("ADMIN", "DML_ST")
def export_fichas_csv():
    """Exportar fichas DML a CSV"""
    db = get_db()
    fichas = db.execute("""
        SELECT f.numero_ficha, f.fecha_ingreso, f.fecha_egreso, f.estado_reparacion,
               f.tecnico, f.tecnico_resp, f.n_ciclos, f.numero_remito_salida,
               r.cliente, r.numero_serie, r.modelo_maquina
        FROM dml_fichas f
        LEFT JOIN raypac_entries r ON f.raypac_id = r.id
        ORDER BY f.created_at DESC
    """).fetchall()

    # Crear CSV en memoria
    si = StringIO()
    writer = csv.writer(si)

    # Header
    writer.writerow([
        'N° Ficha', 'Cliente', 'Serie', 'Modelo', 'Estado',
        'Fecha Ingreso', 'Fecha Egreso', 'Técnico', 'Responsable',
        'N° Ciclos', 'Remito Salida'
    ])

    # Datos
    for f in fichas:
        writer.writerow([
            f['numero_ficha'], f['cliente'], f['numero_serie'], f['modelo_maquina'],
            f['estado_reparacion'], f['fecha_ingreso'], f['fecha_egreso'] or '',
            f['tecnico'], f['tecnico_resp'], f['n_ciclos'], f['numero_remito_salida'] or ''
        ])

    # Preparar respuesta
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=fichas_dml_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"

    return output


@estadisticas_bp.route("/export/stock-csv")
@login_required
@role_required("ADMIN", "DML_REPUESTOS", "RAYPAC")
def export_stock_csv():
    """Exportar stock a CSV"""
    db = get_db()
    stock = db.execute("""
        SELECT m.codigo_repuesto, m.item,
               COALESCE(su_dml.cantidad, 0) as stock_dml,
               COALESCE(su_raypac.cantidad, 0) as stock_raypac,
               (COALESCE(su_dml.cantidad, 0) + COALESCE(su_raypac.cantidad, 0)) as stock_total
        FROM matriz_repuestos m
        LEFT JOIN stock_ubicaciones su_dml ON su_dml.codigo_repuesto = m.codigo_repuesto AND su_dml.ubicacion = 'DML'
        LEFT JOIN stock_ubicaciones su_raypac ON su_raypac.codigo_repuesto = m.codigo_repuesto AND su_raypac.ubicacion = 'RAYPAC'
        ORDER BY m.codigo_repuesto
    """).fetchall()

    # Crear CSV en memoria
    si = StringIO()
    writer = csv.writer(si)

    # Header
    writer.writerow(['Código', 'Descripción', 'Stock DML', 'Stock RAYPAC', 'Stock Total'])

    # Datos
    for s in stock:
        writer.writerow([
            s['codigo_repuesto'], s['item'], s['stock_dml'],
            s['stock_raypac'], s['stock_total']
        ])

    # Preparar respuesta
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=stock_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"

    return output


@estadisticas_bp.route("/export/raypac-csv")
@login_required
@role_required("ADMIN", "RAYPAC")
def export_raypac_csv():
    """Exportar ingresos RAYPAC a CSV"""
    db = get_db()
    entries = db.execute("""
        SELECT r.numero_correlativo, r.fecha_recepcion, r.tipo_solicitud, r.cliente,
               r.numero_serie, r.modelo_maquina, r.comercial, r.numero_remito,
               r.is_frozen, r.contacto_cliente, r.email_cliente
        FROM raypac_entries r
        ORDER BY r.created_at DESC
    """).fetchall()

    # Crear CSV en memoria
    si = StringIO()
    writer = csv.writer(si)

    # Header
    writer.writerow([
        'N° Correlativo', 'Fecha Recepción', 'Tipo', 'Cliente', 'Serie',
        'Modelo', 'Comercial', 'Remito', 'Estado', 'Contacto', 'Email'
    ])

    # Datos
    for e in entries:
        estado = 'Freezado' if e['is_frozen'] else 'Editable'
        writer.writerow([
            e['numero_correlativo'], e['fecha_recepcion'], e['tipo_solicitud'],
            e['cliente'], e['numero_serie'], e['modelo_maquina'], e['comercial'],
            e['numero_remito'] or '', estado, e['contacto_cliente'] or '',
            e['email_cliente'] or ''
        ])

    # Preparar respuesta
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=raypac_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"

    return output
