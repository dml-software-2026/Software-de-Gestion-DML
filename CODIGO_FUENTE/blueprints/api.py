from flask import Blueprint, jsonify

from CODIGO_FUENTE.decorators import login_required

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/verificar-stock/<codigo>")
@login_required
def verificar_stock_api(codigo):
    """API para verificar existencia y stock de un repuesto en tiempo real.

    ADVERTENCIA - CÓDIGO ROTO EN EL ORIGINAL, movido tal cual sin arreglar
    para no cambiar comportamiento en este refactor:
    1. Usa una variable `db` que nunca se define en este scope (nunca se
       llamó a get_db()) - tira NameError si se llega a ejecutar.
    2. Consulta una tabla `stock_repuestos` que no existe en ningún otro
       lugar del proyecto - el resto del código usa `stock_ubicaciones` +
       `matriz_repuestos`.
    3. `db.execute(...)` devolvería un Cursor, que en Python siempre es
       "truthy" - el `if repuesto:` de abajo sería siempre True aunque no
       haya resultados, aunque esto es secundario frente al punto 1, que ya
       rompe la ejecución antes de llegar acá.
    Todo indica que es un endpoint no usado/no probado en producción (no
    encontramos referencias a esta ruta en el resto del código ni en
    templates). Recomendación para el equipo: confirmar si algo lo llama y,
    si no, eliminarlo; si se necesita, reescribirlo usando
    services/stock.py::check_stock_alert como base.
    """
    repuesto = db.execute(
        "SELECT codigo_repuesto, descripcion, stock FROM stock_repuestos WHERE codigo_repuesto = ?",
        (codigo.upper(),)
    )

    if repuesto:
        return jsonify({
            "existe": True,
            "stock": repuesto[0]['stock'],
            "descripcion": repuesto[0]['descripcion'],
            "codigo": repuesto[0]['codigo_repuesto']
        })
    else:
        return jsonify({
            "existe": False,
            "stock": 0,
            "descripcion": "",
            "codigo": codigo.upper()
        })
