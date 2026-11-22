from flask import Blueprint, render_template, request

from CODIGO_FUENTE.decorators import (
    get_current_user,
    login_required,
    permission_required,
    role_required,
)
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.excel import respuesta_xlsx
from CODIGO_FUENTE.services.stock import nivel_de_cantidad
from CODIGO_FUENTE.services.ubicacion_fisica import SIN_UBICACION

estadisticas_bp = Blueprint("estadisticas", __name__)


@estadisticas_bp.route("/estadisticas")
@login_required
# #336: RAYPAC la ve de solo lectura (pedido del cliente), con los datos de DML
# igual que DML_ST: su stock se ve desde Stock y no usa repuestos en reparaciones.
@permission_required(read_roles=["DML_ST", "RAYPAC"], write_roles=["DML_REPUESTOS"])
def estadisticas(readonly=False):
    """Dashboard de estadísticas de repuestos más utilizados."""
    user = get_current_user()
    db = get_db()

    # Determinar ubicación según rol
    if user['role'] == 'ADMIN':
        ubicacion = request.args.get("ubicacion", "DML")
        ubicaciones_disponibles = ["RAYPAC", "DML"]
    else:
        ubicacion = "DML"  # DML_REPUESTOS, DML_ST y RAYPAC ven DML
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
        WHERE su.cantidad <= 2 AND su.ubicacion = %s
        ORDER BY su.cantidad ASC
    """, (ubicacion,)).fetchall()

    # Estadísticas generales
    stats = {
        "total_repuestos": db.execute("SELECT COUNT(*) as cnt FROM matriz_repuestos").fetchone()['cnt'],
        "repuestos_en_ubicacion": db.execute(
            "SELECT COUNT(*) as cnt FROM stock_ubicaciones WHERE ubicacion = %s",
            (ubicacion,)
        ).fetchone()['cnt'],
        "total_movimientos": db.execute("SELECT SUM(total_usos) as total FROM estadisticas_repuestos").fetchone()['total'] or 0 if ubicacion == "DML" else 0,
        "fichas_completadas": db.execute("SELECT COUNT(*) as cnt FROM dml_fichas WHERE is_closed = TRUE").fetchone()['cnt'] if ubicacion == "DML" else 0,
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


# ======================== DESCARGAS EN EXCEL ========================
# #312: antes eran CSV (en un Excel en español se abrían en una sola columna
# y con los acentos rotos). Ahora son .xlsx reales (services/excel.py).

@estadisticas_bp.route("/export/fichas.xlsx")
@login_required
@role_required("ADMIN", "DML_ST")
def export_fichas_xlsx():
    """Fichas DML en Excel."""
    db = get_db()
    fichas = db.execute("""
        SELECT f.numero_ficha, f.fecha_ingreso, f.fecha_egreso, f.estado_reparacion,
               f.tecnico, f.tecnico_resp, f.n_ciclos, f.numero_remito_salida,
               r.cliente, r.numero_serie, r.modelo_maquina
        FROM dml_fichas f
        LEFT JOIN raypac_entries r ON f.raypac_id = r.id
        ORDER BY f.created_at DESC
    """).fetchall()

    encabezados = ['N° Ficha', 'Cliente', 'N° de Serie', 'Modelo', 'Estado',
                   'Fecha Ingreso', 'Fecha Egreso', 'Técnico', 'Responsable',
                   'N° Ciclos', 'Remito Salida']
    filas = [
        [f['numero_ficha'], f['cliente'], f['numero_serie'], f['modelo_maquina'],
         f['estado_reparacion'], f['fecha_ingreso'], f['fecha_egreso'],
         f['tecnico'], f['tecnico_resp'], f['n_ciclos'], f['numero_remito_salida']]
        for f in fichas
    ]
    return respuesta_xlsx("fichas_dml", "Fichas DML", encabezados, filas)


@estadisticas_bp.route("/export/stock.xlsx")
@login_required
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS", "RAYPAC")
def export_stock_xlsx():
    """Stock de DML en Excel, con las mismas columnas que se ven en /stock.

    - Todos: código, descripción, cantidad en DML y estado.
    - Roles de DML y ADMIN: también la ubicación física (RAYPAC no la ve,
      respuesta 5.2 de David, 2026-11-15).
    - ADMIN: también el stock de RAYPAC y el total, como el CSV de antes.
    """
    user = get_current_user()
    es_admin = user['role'] == 'ADMIN'
    ve_ubicacion_fisica = user['role'] != 'RAYPAC'

    db = get_db()
    stock = db.execute("""
        SELECT m.codigo_repuesto, m.item,
               su_dml.codigo_ubicacion_fisica,
               COALESCE(su_dml.cantidad, 0) AS stock_dml,
               COALESCE(su_raypac.cantidad, 0) AS stock_raypac
        FROM matriz_repuestos m
        LEFT JOIN stock_ubicaciones su_dml ON su_dml.codigo_repuesto = m.codigo_repuesto AND su_dml.ubicacion = 'DML'
        LEFT JOIN stock_ubicaciones su_raypac ON su_raypac.codigo_repuesto = m.codigo_repuesto AND su_raypac.ubicacion = 'RAYPAC'
        ORDER BY m.codigo_repuesto
    """).fetchall()

    encabezados = ['Código', 'Descripción']
    if ve_ubicacion_fisica:
        encabezados.append('Ubicación física')
    encabezados += ['Cantidad DML', 'Estado']
    if es_admin:
        encabezados += ['Stock RAYPAC', 'Stock Total']

    filas = []
    for s in stock:
        fila = [s['codigo_repuesto'], s['item']]
        if ve_ubicacion_fisica:
            fisica = (s['codigo_ubicacion_fisica'] or "").strip()
            fila.append("" if fisica in ("", SIN_UBICACION) else fisica)
        fila += [s['stock_dml'], nivel_de_cantidad(s['stock_dml'])]
        if es_admin:
            fila += [s['stock_raypac'], s['stock_dml'] + s['stock_raypac']]
        filas.append(fila)

    return respuesta_xlsx("stock_dml", "Stock DML", encabezados, filas)


@estadisticas_bp.route("/export/raypac.xlsx")
@login_required
@role_required("ADMIN", "RAYPAC")
def export_raypac_xlsx():
    """Ingresos RAYPAC en Excel."""
    db = get_db()
    entries = db.execute("""
        SELECT r.numero_correlativo, r.fecha_recepcion, r.tipo_solicitud, r.cliente,
               r.numero_serie, r.modelo_maquina, r.comercial, r.numero_remito,
               r.is_frozen, r.contacto_cliente, r.email_cliente
        FROM raypac_entries r
        ORDER BY r.created_at DESC
    """).fetchall()

    encabezados = ['N° Correlativo', 'Fecha Recepción', 'Tipo', 'Cliente', 'N° de Serie',
                   'Modelo', 'Comercial', 'Remito', 'Estado', 'Contacto', 'Email']
    filas = [
        [e['numero_correlativo'], e['fecha_recepcion'], e['tipo_solicitud'],
         e['cliente'], e['numero_serie'], e['modelo_maquina'], e['comercial'],
         e['numero_remito'], 'Freezado' if e['is_frozen'] else 'Editable',
         e['contacto_cliente'], e['email_cliente']]
        for e in entries
    ]
    return respuesta_xlsx("ingresos_raypac", "Ingresos RAYPAC", encabezados, filas)
