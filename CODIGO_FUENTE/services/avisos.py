"""Campanita de DML (#170/#258): lo que llegó de RAYPAC y el usuario todavía no vio.

"Llegó" = salió de RAYPAC y DML todavía no lo recibió:
- MAQUINA: ingreso RAYPAC freezado con estado_envio_equipos = 'ENVIADO'.
- REPUESTO: envío de repuestos con estado_envio = 'ENVIADO' sin recepción.

El "visto" es por usuario (tabla avisos_vistos): que lo abra el técnico no
lo saca de la campanita de Repuestos. Cada rol ve solo lo de su trabajo.
"""
from CODIGO_FUENTE.extensions import get_db

TIPOS_POR_ROL = {
    "ADMIN": ("MAQUINA", "REPUESTO"),
    "DML_ST": ("MAQUINA",),
    "DML_REPUESTOS": ("REPUESTO",),
}


def tipos_de(user):
    return TIPOS_POR_ROL.get(user["role"], ()) if user else ()


def avisos_sin_ver(user):
    """Lista de avisos sin ver del usuario, más nuevos primero."""
    tipos = tipos_de(user)
    db = get_db()
    avisos = []

    if "MAQUINA" in tipos:
        rows = db.execute(
            """
            SELECT r.id, r.cliente, r.modelo_maquina, r.numero_remito, r.frozen_at AS fecha
            FROM raypac_entries r
            WHERE r.is_frozen = TRUE AND r.estado_envio_equipos = 'ENVIADO'
              AND NOT EXISTS (
                  SELECT 1 FROM avisos_vistos v
                  WHERE v.user_id = %s AND v.tipo = 'MAQUINA' AND v.ref_id = r.id
              )
            """,
            (user["id"],)
        ).fetchall()
        avisos += [{
            "tipo": "MAQUINA",
            "id": r["id"],
            "titulo": f"Máquina nueva: {r['modelo_maquina'] or 'sin modelo'}",
            "detalle": f"{r['cliente'] or ''} · Remito {r['numero_remito'] or '-'}",
            "fecha": r["fecha"],
        } for r in rows]

    if "REPUESTO" in tipos:
        rows = db.execute(
            """
            SELECT e.id, e.numero_remito, e.fecha_envio AS fecha,
                   (SELECT COUNT(*) FROM envios_repuestos_detalles d WHERE d.envio_id = e.id) AS items
            FROM envios_repuestos e
            WHERE e.estado_envio = 'ENVIADO' AND e.fecha_recepcion_dml IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM avisos_vistos v
                  WHERE v.user_id = %s AND v.tipo = 'REPUESTO' AND v.ref_id = e.id
              )
            """,
            (user["id"],)
        ).fetchall()
        avisos += [{
            "tipo": "REPUESTO",
            "id": r["id"],
            "titulo": f"Envío de repuestos {r['numero_remito']}",
            "detalle": f"{r['items']} repuesto(s)",
            "fecha": r["fecha"],
        } for r in rows]

    # fecha es DATE en las dos tablas; a igual fecha, el id más alto es el más nuevo
    avisos.sort(key=lambda a: (str(a["fecha"] or ""), a["id"]), reverse=True)
    return avisos


def ids_sin_ver(user, tipo):
    """ids de un tipo que el usuario todavía no vio (para resaltar filas)."""
    return {a["id"] for a in avisos_sin_ver(user) if a["tipo"] == tipo}


def marcar_visto(user, tipo, ref_id):
    """Marca el aviso como visto para este usuario. Se llama al abrir el
    detalle; no hace nada si el rol no recibe avisos de ese tipo."""
    if tipo not in tipos_de(user):
        return
    db = get_db()
    try:
        db.execute(
            """INSERT INTO avisos_vistos (user_id, tipo, ref_id) VALUES (%s, %s, %s)
               ON CONFLICT (user_id, tipo, ref_id) DO NOTHING""",
            (user["id"], tipo, ref_id)
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error marcando aviso visto ({tipo} {ref_id}): {e}")


def reiniciar_vistos(tipo, ref_id):
    """Vuelve a mostrar el aviso a todos (ej. una máquina que se desfreezó y
    se volvió a freezar: es un envío nuevo). No commitea: va dentro de la
    transacción de quien lo llama."""
    get_db().execute(
        "DELETE FROM avisos_vistos WHERE tipo = %s AND ref_id = %s",
        (tipo, ref_id)
    )
