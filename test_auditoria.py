from CODIGO_FUENTE.app import app  # ajustar si el objeto Flask se llama distinto o es una factory
from CODIGO_FUENTE.extensions import get_db
from CODIGO_FUENTE.decorators import log_action

with app.app_context():
    db = get_db()

    user = db.execute("SELECT id FROM users LIMIT 1").fetchone()
    assert user, "No hay usuarios en la base para probar"

    antes = db.execute("SELECT COUNT(*) AS c FROM logs_auditoria").fetchone()['c']

    log_action(user['id'], "CREATE", "dml_fichas", 999999, None, "test_auditoria")

    despues = db.execute("SELECT COUNT(*) AS c FROM logs_auditoria").fetchone()['c']
    assert despues == antes + 1, f"Se esperaba 1 registro nuevo, hubo {despues - antes}"

    row = db.execute(
        "SELECT id_log, fecha_hora, id_usuario, tipo_accion, tabla_afectada "
        "FROM logs_auditoria ORDER BY fecha_hora DESC LIMIT 1"
    ).fetchone()

    assert row['id_log'] is not None
    assert row['fecha_hora'] is not None
    assert row['id_usuario'] == user['id']
    assert row['tipo_accion'] == 'INSERT'  # "CREATE" se mapea a INSERT
    assert row['tabla_afectada'] == 'dml_fichas'

    print("OK — log_action escribe correctamente en logs_auditoria con el schema nuevo")

    db.execute("DELETE FROM logs_auditoria WHERE id_log = %s", (row['id_log'],))
    db.commit()
