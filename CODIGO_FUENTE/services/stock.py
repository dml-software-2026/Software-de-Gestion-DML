from datetime import datetime

from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.services.mail import send_mail


def check_stock_alert(codigo, ubicacion="DML"):
    """Verifica nivel de stock por ubicación y retorna estado de alerta."""
    db = get_db()
    stock = db.execute(
        "SELECT cantidad FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = %s",
        (codigo, ubicacion)
    ).fetchone()

    # Fallback: si no existe en la ubicación, usar cualquier ubicación (último registro)
    if not stock:
        stock = db.execute(
            "SELECT cantidad FROM stock_ubicaciones WHERE codigo_repuesto = %s ORDER BY updated_at DESC LIMIT 1",
            (codigo,)
        ).fetchone()

    if not stock:
        return "NO_EXISTE"

    qty = stock['cantidad']
    if qty == 0:
        return "ROJO"  # Falta completamente
    elif qty == 1:
        return "NARANJA"  # Último repuesto
    elif qty == 2:
        return "AMARILLO"  # Pocos repuestos
    else:
        return "OK"


def get_alert_badge(codigo, ubicacion="DML"):
    """Retorna HTML badge para mostrar nivel de alerta."""
    nivel = check_stock_alert(codigo, ubicacion)

    badge_config = {
        "ROJO": {"color": "#dc3545", "texto": "REPUESTO FALTANTE", "emoji": "🔴"},
        "AMARILLO": {"color": "#ffc107", "texto": "POCOS REPUESTOS", "emoji": "⚠️"},
        "NARANJA": {"color": "#ff6600", "texto": "ÚLTIMO REPUESTO", "emoji": "⚠️"},
        "OK": {"color": "#28a745", "texto": "DISPONIBLE", "emoji": "✅"},
        "NO_EXISTE": {"color": "#6c757d", "texto": "NO EXISTE", "emoji": "❓"}
    }

    config = badge_config.get(nivel, badge_config["OK"])
    return f'<span class="badge badge-alert" style="background-color: {config["color"]}; color: white; padding: 8px 12px; border-radius: 4px; font-weight: bold; display: inline-block; min-width: 140px; text-align: center;" title="{config["texto"]}">{config["emoji"]} {nivel}</span>'


def ajustar_stock_ubicacion(codigo_repuesto, ubicacion, delta):
    """Suma/resta stock en una ubicación específica, evitando negativos."""
    db = get_db()
    row = db.execute(
        "SELECT cantidad FROM stock_ubicaciones WHERE codigo_repuesto = %s AND ubicacion = %s",
        (codigo_repuesto, ubicacion)
    ).fetchone()
    if row:
        nueva_cantidad = row['cantidad'] + delta
        if nueva_cantidad < 0:
            raise ValueError(f"Stock insuficiente en {ubicacion} para {codigo_repuesto}")
        db.execute(
            "UPDATE stock_ubicaciones SET cantidad = %s, updated_at = CURRENT_TIMESTAMP WHERE codigo_repuesto = %s AND ubicacion = %s",
            (nueva_cantidad, codigo_repuesto, ubicacion)
        )
    else:
        if delta < 0:
            raise ValueError(f"No existe stock en {ubicacion} para {codigo_repuesto}")
        db.execute(
            "INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad) VALUES (%s, %s, %s)",
            (codigo_repuesto, ubicacion, delta)
        )


def verificar_alerta_stock(codigo_repuesto, ubicacion="DML"):
    """Verifica y registra alerta de stock por ubicación y dispara aviso si corresponde."""
    db = get_db()
    stock = db.execute(
        """
        SELECT su.cantidad, su.ubicacion, m.item
        FROM stock_ubicaciones su
        LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = su.codigo_repuesto
        WHERE su.codigo_repuesto = %s AND su.ubicacion = %s
        """,
        (codigo_repuesto, ubicacion)
    ).fetchone()

    if not stock:
        stock = db.execute(
            """
            SELECT su.cantidad, su.ubicacion, m.item
            FROM stock_ubicaciones su
            LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = su.codigo_repuesto
            WHERE su.codigo_repuesto = %s
            ORDER BY su.updated_at DESC
            LIMIT 1
            """,
            (codigo_repuesto,)
        ).fetchone()

    if not stock:
        return None

    nivel_alerta = check_stock_alert(codigo_repuesto, stock['ubicacion'])
    item_nombre = stock['item'] or codigo_repuesto

    if nivel_alerta in ["ROJO", "NARANJA", "AMARILLO"]:
        # Registrar alerta
        db.execute("""
            INSERT INTO stock_alertas (codigo_repuesto, item, cantidad_actual, nivel_alerta)
            VALUES (%s, %s, %s, %s)
        """, (codigo_repuesto, item_nombre, stock['cantidad'], nivel_alerta))
        db.commit()

        # Enviar email de alerta
        enviar_alerta_stock(codigo_repuesto, item_nombre, stock['cantidad'], nivel_alerta, stock['ubicacion'])

        return nivel_alerta
    return None


def enviar_alerta_stock(codigo, item, cantidad, nivel, ubicacion="DML"):
    """Envía email de alerta de stock."""
    colores = {
        "ROJO": "Repuesto AGOTADO",
        "NARANJA": "Último repuesto disponible",
        "AMARILLO": "Pocos repuestos disponibles"
    }

    body = f"""
    <h2>⚠️ ALERTA DE STOCK</h2>
    <p><strong>Nivel: {colores.get(nivel, nivel)}</strong></p>
    <p>Código: <strong>{codigo}</strong></p>
    <p>Item: <strong>{item}</strong></p>
    <p>Cantidad actual: <strong>{cantidad}</strong></p>
    <p>Ubicación: <strong>{ubicacion}</strong></p>
    <p>Por favor, verifique el stock y considere reposición.</p>
    """

     # Enviar a todos los destinatarios activos configurados en usuarios_notificaciones
    db = get_db()
    destinatarios = db.execute(
        "SELECT email FROM usuarios_notificaciones WHERE activo = TRUE"
    ).fetchall()

    for destinatario in destinatarios:
        send_mail(destinatario["email"], f"🔔 Alerta de Stock: {item}", body)


def actualizar_estado_alerta_stock(codigo, ubicacion="DML"):
    """Recalcula estado_alerta en stock_dml tras movimientos para la ubicación dada."""
    db = get_db()
    existe = db.execute(
        "SELECT 1 FROM stock_dml WHERE codigo_repuesto = %s",
        (codigo,)
    ).fetchone()
    if not existe:
        return

    nivel = check_stock_alert(codigo, ubicacion)
    db.execute(
        "UPDATE stock_dml SET estado_alerta = %s, updated_at = CURRENT_TIMESTAMP WHERE codigo_repuesto = %s",
        (nivel, codigo)
    )
    db.commit()


def actualizar_estadistica_repuesto(codigo_repuesto, cantidad=1):
    """Actualiza estadísticas de uso de repuesto."""
    db = get_db()

    stats = db.execute(
        "SELECT * FROM estadisticas_repuestos WHERE codigo_repuesto = %s",
        (codigo_repuesto,)
    ).fetchone()

    if stats:
        db.execute("""
            UPDATE estadisticas_repuestos
            SET cantidad_utilizada = cantidad_utilizada + %s,
                fecha_ultimo_uso = %s,
                total_usos = total_usos + 1
            WHERE codigo_repuesto = %s
        """, (cantidad, datetime.now().isoformat(), codigo_repuesto))
    else:
        # Obtener item de matriz
        item = db.execute(
            "SELECT item FROM matriz_repuestos WHERE codigo_repuesto = %s",
            (codigo_repuesto,)
        ).fetchone()

        db.execute("""
            INSERT INTO estadisticas_repuestos
            (codigo_repuesto, item, cantidad_utilizada, fecha_ultimo_uso, total_usos)
            VALUES (%s, %s, %s, %s, 1)
        """, (codigo_repuesto, item['item'] if item else None, cantidad, datetime.now().isoformat()))

    db.commit()