from CODIGO_FUENTE.extensions import get_db


def generate_ficha_number():
    """Genera el próximo número de ficha correlativo."""
    db = get_db()
    last = db.execute("SELECT MAX(numero_ficha) as max FROM dml_fichas").fetchone()
    return (last['max'] or 500) + 1


def generate_ticket_number(serial):
    """Genera número de ticket basado en número de serie: TK-{serie}.

    #259: una misma máquina puede entrar a DML varias veces, y numero_ticket
    es UNIQUE (en tickets y en dml_fichas). La primera vez queda TK-{serie}
    como siempre; las siguientes, TK-{serie}-2, TK-{serie}-3, etc.
    """
    db = get_db()
    base = f"TK-{serial.strip().upper()}"
    numero, n = base, 1
    while db.execute(
        """SELECT 1 FROM tickets WHERE numero_ticket = %s
           UNION ALL SELECT 1 FROM dml_fichas WHERE numero_ticket = %s""",
        (numero, numero),
    ).fetchone():
        n += 1
        numero = f"{base}-{n}"
    return numero
