"""Cifrado de credenciales de exchange (API key / secret) con Fernet.

Las API keys de Binance NUNCA se guardan en texto plano. Se cifran con
SECRET_KEY (Fernet) antes de escribirse en la base de datos. El secret del
exchange tampoco se muestra nunca en la API.
"""
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from backend.config import config


def _derivar_clave() -> bytes:
    # Derivar una clave Fernet de 32 bytes a partir de SECRET_KEY.
    digest = hashes.Hash(hashes.SHA256())
    digest.update(config.SECRET_KEY.encode())
    return base64.urlsafe_b64encode(digest.finalize())


_fernet = Fernet(_derivar_clave())


def cifrar(texto: str) -> str:
    """Cifra un texto y devuelve el token como string."""
    if not texto:
        return ""
    return _fernet.encrypt(texto.encode()).decode()


def descifrar(token: str) -> str:
    """Descifra un token Fernet. Devuelve '' si esta vacio."""
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except Exception:
        return ""
