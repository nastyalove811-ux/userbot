"""
Общие хелперы: шифрование чувствительных данных и разбор команд.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from cryptography.fernet import Fernet

from app.settings import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.encryption_key.encode())


def encrypt(value: str) -> str:
    """Шифрует строку (например, session_string или api_hash аккаунта)."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    """Расшифровывает строку, зашифрованную encrypt()."""
    return _fernet().decrypt(token.encode()).decode()


@dataclass
class ParsedCommand:
    prefix: str
    command: str
    args: list[str]
    raw_args: str


_COMMAND_RE = re.compile(r"^([^\sa-zA-Zа-яА-Я0-9])([a-zA-Zа-яА-Я0-9_]+)(?:\s+(.*))?$", re.DOTALL)


def parse_command(text: str, prefix: str, bot_username: str | None = None) -> ParsedCommand | None:
    """
    Разбирает входящее сообщение на команду и аргументы.
    Поддерживаются варианты:
    - .help
    - @botname .help
    - botname .help
    - текст после упоминания бота, если оно стоит перед командой.
    """
    if not text:
        return None

    candidate = text.strip()
    if not candidate:
        return None

    if bot_username:
        normalized = bot_username.strip().lstrip("@").lower()
        patterns = [
            rf"^(?:@?{re.escape(normalized)}\s*[:\-]?\s*)",
            rf"(?<!\w)(?:@?{re.escape(normalized)}\s*[:\-]?\s*)",
        ]
        for pattern in patterns:
            candidate = re.sub(pattern, "", candidate, count=1, flags=re.IGNORECASE)
            if candidate != text.strip():
                break

    if not candidate.startswith(prefix):
        return None

    body = candidate[len(prefix):]
    if not body:
        return None
    parts = body.split(None, 1)
    command = parts[0].lower()
    raw_args = parts[1] if len(parts) > 1 else ""
    try:
        args = shlex.split(raw_args) if raw_args else []
    except ValueError:
        args = raw_args.split() if raw_args else []
    return ParsedCommand(prefix=prefix, command=command, args=args, raw_args=raw_args)


def generate_encryption_key() -> str:
    """Генерирует новый ключ для ENCRYPTION_KEY (запускать один раз при настройке проекта)."""
    return Fernet.generate_key().decode()


if __name__ == "__main__":
    print(generate_encryption_key())
