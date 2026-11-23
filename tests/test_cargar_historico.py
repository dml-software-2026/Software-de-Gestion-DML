"""#383: carga histórica tolerante desde la planilla del cliente (sin base)."""
from datetime import date, datetime

from CODIGO_FUENTE.scripts.cargar_historico import (
    _clave_columna,
    armar_ficha,
    parse_ciclos,
    parse_ficha,
    parse_repuestos,
)

MATRIZ = {"D006110": "RUEDA DE ARRASTRE", "B800532": "RESORTE"}


def fila(**kw):
    base = {"ficha_n": 900, "cliente": "ACME", "serie": "123", "modelo": "ITA 24",
            "ingreso": datetime(2026, 10, 1), "salida": datetime(2026, 10, 5),
            "observacion": "NO CORTA", "reparacion": "SE CAMBIA RUEDA",
            "repuestos": "D006110", "n_ciclos": 100}
    base.update(kw)
    return base


def test_encabezados_de_la_planilla():
    assert _clave_columna("Ficha N°") == "ficha_n"
    assert _clave_columna("N° Ciclos") == "n_ciclos"
    assert _clave_columna("Reparación") == "reparacion"
    assert _clave_columna("Mes Salida") == "mes_salida"
    assert _clave_columna("Salida") == "salida"
    assert _clave_columna("N° factura") == "n_factura"
    assert _clave_columna("Pago Ricardo") == "pago_tecnico"


def test_parseos():
    assert parse_ficha(561) == (561, None)
    assert parse_ficha("754 EX 717") == (754, "EX 717")
    assert parse_ciclos(13570) == (13570, None)
    assert parse_ciclos("MANUAL") == (None, "MANUAL")
    assert parse_repuestos("D006300\nD006510") == ([("D006300", 1), ("D006510", 1)], False)
    assert parse_repuestos("D006300(2) D006510(1)") == ([("D006300", 2), ("D006510", 1)], False)
    assert parse_repuestos("NO SE COLOCARON") == ([], True)
    assert parse_repuestos("B600013L, SP00367") == ([("B600013L", 1), ("SP00367", 1)], False)


def test_texto_en_repuestos_va_a_observaciones():
    data, _ = armar_ficha(fila(repuestos="NINGUNO"), MATRIZ)
    assert data["repuestos"] == []
    assert "Repuestos en la planilla: NINGUNO" in data["observacion"]


def test_ficha_completa():
    data, avisos = armar_ficha(fila(), MATRIZ)
    assert avisos == []
    assert data["ficha_n"] == 900
    assert data["fecha_ingreso"] == date(2026, 10, 1)
    assert data["repuestos"] == [("D006110", "RUEDA DE ARRASTRE", 1)]
    assert data["observacion"] == "NO CORTA"


def test_sin_ingreso_usa_salida():
    data, avisos = armar_ficha(fila(ingreso=None), MATRIZ)
    assert data["fecha_ingreso"] == date(2026, 10, 5)
    assert avisos


def test_fecha_ilegible_queda_en_observaciones():
    data, _ = armar_ficha(fila(salida="16-ab"), MATRIZ)
    assert data["fecha_egreso"] == date(2026, 10, 1)
    assert "16-ab" in data["observacion"]


def test_sin_fechas_se_saltea():
    data, motivo = armar_ficha(fila(ingreso=None, salida=None), MATRIZ)
    assert data is None and motivo


def test_repuesto_desconocido_no_descarta_la_ficha():
    data, avisos = armar_ficha(fila(repuestos="D006110\nZZ99999"), MATRIZ)
    assert data["repuestos"] == [("D006110", "RUEDA DE ARRASTRE", 1)]
    assert "ZZ99999" in data["observacion"]
    assert avisos


def test_datos_raros_van_a_observaciones():
    data, _ = armar_ficha(fila(ficha_n="754 EX 717", modelo=None, n_ciclos="MANUAL", serie=None), MATRIZ)
    assert data["ficha_n"] == 754
    assert data["modelo"] == "HISTORICO"
    assert data["serie"] == "HIST-754"
    assert data["n_ciclos"] is None
    assert "754 EX 717" in data["observacion"] and "MANUAL" in data["observacion"]


def test_aplica_correcciones_del_cliente():
    data, avisos = armar_ficha(fila(repuestos="B006440"), {"D006440": "X"})
    assert data["repuestos"] == [("D006440", "X", 1)]
    assert avisos == []
