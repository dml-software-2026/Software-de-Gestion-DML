"""Número de remito: formato y autocompletado (#305).

El remito se escribe a mano. Alcanza con el número (ej. 4321) y el sistema lo
completa al formato de los talonarios de RAYPAC: 00001-00004321 (punto de
venta de 4-5 dígitos, guión, número de 8 dígitos).
"""
import re

FORMATO_COMPLETO = re.compile(r'^\d{4,5}-\d{8}$')
SOLO_NUMERO = re.compile(r'^\d{1,8}$')
PUNTO_DE_VENTA = "00001"


def normalizar_remito(texto):
    """Devuelve (remito, error). Uno de los dos es None.

    - "4321" -> "00001-00004321"
    - "00001-00004321" -> igual (formato completo)
    - vacío o con otro formato -> error con el mensaje para el usuario
    """
    texto = (texto or "").strip()
    if not texto:
        return None, "⚠️ El número de remito es OBLIGATORIO para freezar y enviar."
    if SOLO_NUMERO.match(texto):
        return f"{PUNTO_DE_VENTA}-{texto.zfill(8)}", None
    if FORMATO_COMPLETO.match(texto):
        return texto, None
    return None, ("⚠️ Formato de remito inválido. Escribí solo el número (ej: 4321) "
                  "o el formato completo #####-######## (ej: 00001-00004321).")


def numero_para_input(remito):
    """El número sin ceros ni punto de venta, para precargar el input al
    volver a freezar (00001-00004321 -> 4321). Si no tiene el formato del
    talonario (ej. un N° de serie de la época del #292), no precarga nada."""
    if remito and FORMATO_COMPLETO.match(remito):
        return remito.split('-')[-1].lstrip('0') or '0'
    return ""
