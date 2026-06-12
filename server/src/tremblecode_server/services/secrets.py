"""Fernet encryption for secrets at rest (API keys, MCP env values).

The key is taken from TC_FERNET_KEY or generated once and stored alongside
the agent home so it survives restarts.
"""

from cryptography.fernet import Fernet

from ..config import get_settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        settings = get_settings()
        key = settings.fernet_key
        if not key:
            key_file = settings.agent_home.parent / "fernet.key"
            key_file.parent.mkdir(parents=True, exist_ok=True)
            if key_file.exists():
                key = key_file.read_text().strip()
            else:
                key = Fernet.generate_key().decode()
                key_file.write_text(key)
                key_file.chmod(0o600)
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
