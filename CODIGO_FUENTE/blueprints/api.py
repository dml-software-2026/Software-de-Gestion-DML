from flask import Blueprint, jsonify, url_for

from CODIGO_FUENTE.decorators import get_current_user, login_required
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.avisos import avisos_sin_ver

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/verificar-stock/<codigo>")
@login_required
def verificar_stock_api(codigo):
    """API para verificar existencia y stock de un repuesto en tiempo real.

    Usado por el JS de dml_edit.html (form "Agregar Nuevo Repuesto") para
    avisar antes de guardar si hay stock suficiente en DML. Mismo criterio
    de tablas que services/stock.py::check_stock_alert (matriz_repuestos +
    stock_ubicaciones), a diferencia de la versión original que usaba una
    tabla stock_repuestos inexistente y una variable db sin definir.
    """
    db = get_db()
    codigo = codigo.upper()

    repuesto = db.execute(
        "SELECT codigo_repuesto, item FROM matriz_repuestos WHERE codigo_repuesto = %s",
        (codigo,)
    ).fetchone()

    if not repuesto:
        return jsonify({
            "existe": False,
            "stock": 0,
            "descripcion": "",
            "codigo": codigo
        })

    stock = db.execute(
        "SELECT cantidad FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = 'DML'",
        (codigo,)
    ).fetchone()

    return jsonify({
        "existe": True,
        "stock": stock['cantidad'] if stock else 0,
        "descripcion": repuesto['item'] or "",
        "codigo": repuesto['codigo_repuesto']
    })


@api_bp.route("/avisos")
@login_required
def avisos_api():
    """Campanita de la navbar (#170/#258): lo llegado de RAYPAC que el
    usuario todavía no vio. El JS de base.html lo consulta al cargar cada
    página y cada minuto. RAYPAC (sin avisos) recibe una lista vacía."""
    avisos = avisos_sin_ver(get_current_user())
    for aviso in avisos:
        if aviso["tipo"] == "MAQUINA":
            aviso["url"] = url_for("raypac.raypac_view", id=aviso["id"])
        else:
            aviso["url"] = url_for("envios.envios_view", id=aviso["id"])
        aviso["clave"] = f"{aviso['tipo']}-{aviso['id']}"
        aviso["fecha"] = aviso["fecha"].strftime("%d/%m/%Y") if aviso["fecha"] else ""
    return jsonify({"total": len(avisos), "avisos": avisos})
