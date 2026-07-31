from datetime import datetime

from extensions import get_db


def generate_ficha_number():
    """Genera el próximo número de ficha correlativo."""
    db = get_db()
    last = db.execute("SELECT MAX(numero_ficha) as max FROM dml_fichas").fetchone()
    return (last['max'] or 500) + 1


def generate_ticket_number(serial):
    """Genera número de ticket basado en número de serie: TK-{serie}."""
    # Nuevo formato simplificado: TK-{serie}
    return f"TK-{serial.upper()}"


def generate_remito_raypac():
    """Genera un número de remito RP-YYYY-00001 correlativo para envíos a ST."""
    db = get_db()
    year = datetime.now().year
    count = db.execute(
        "SELECT COUNT(*) as total FROM raypac_entries WHERE numero_remito LIKE ?",
        (f"RP-{year}-%",)
    ).fetchone()
    seq = (count['total'] or 0) + 1
    return f"RP-{year}-{seq:05d}"


def generate_remito_envio():
    """Genera remitos para envíos de repuestos (ER-YYYY-00001)."""
    db = get_db()
    year = datetime.now().year
    count = db.execute(
        "SELECT COUNT(*) as total FROM envios_repuestos WHERE numero_remito LIKE ?",
        (f"ER-{year}-%",)
    ).fetchone()
    seq = (count['total'] or 0) + 1
    return f"ER-{year}-{seq:05d}"


def crear_ticket(ficha_id, numero_serie):
    """Crea un ticket de seguimiento para una ficha DML."""
    db = get_db()
    numero_ticket = generate_ticket_number(numero_serie)

    db.execute("""
        INSERT INTO tickets (numero_ticket, ficha_id, numero_serie)
        VALUES (?, ?, ?)
    """, (numero_ticket, ficha_id, numero_serie))

    # Actualizar ficha con número de ticket
    db.execute("UPDATE dml_fichas SET numero_ticket = ? WHERE id = ?", (numero_ticket, ficha_id))
    db.commit()

    return numero_ticket


def registrar_cambio_estado_ticket(ticket_id, estado_nuevo, usuario_id, motivo=None):
    """Registra cambio de estado en el historial del ticket."""
    db = get_db()
    ticket = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()

    db.execute("""
        INSERT INTO ticket_historial (ticket_id, estado_anterior, estado_nuevo, usuario_id, motivo)
        VALUES (?, ?, ?, ?, ?)
    """, (ticket_id, ticket['estado'] if ticket else None, estado_nuevo, usuario_id, motivo))

    db.execute("UPDATE tickets SET estado = ? WHERE id = ?", (estado_nuevo, ticket_id))
    db.commit()
