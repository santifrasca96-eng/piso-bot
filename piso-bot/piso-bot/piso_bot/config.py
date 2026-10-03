from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path | None = None) -> None:
    """Carga .env (KEY=VALUE) sin depender de librerías externas."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(path: Path | None = None) -> dict:
    path = path or ROOT / "config.yaml"
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    # Los datos personales no van en el repositorio (en GitHub es público): se leen de la
    # variable de entorno PROFILE_YAML (un secreto en GitHub Actions) y pisan a `profile`.
    extra = os.environ.get("PROFILE_YAML", "").strip()
    if extra:
        cfg.setdefault("profile", {}).update(yaml.safe_load(extra) or {})
    return cfg


def profile_is_placeholder(cfg: dict) -> bool:
    p = cfg.get("profile", {})
    return "TU NOMBRE" in str(p.get("name", "")) or "XX" in str(p.get("phone", ""))


def data_dir() -> Path:
    d = ROOT / "data"
    d.mkdir(exist_ok=True)
    return d
