"""Resolve repo-root .env for load_dotenv; safe inside Docker (/shared-python/...)."""
from pathlib import Path


def resolve_dotenv_path() -> Path:
    p = Path(__file__).resolve()
    for depth in (3, 2):
        try:
            candidate = p.parents[depth] / ".env"
            if candidate.is_file():
                return candidate
        except IndexError:
            continue
    return Path("/.env")
