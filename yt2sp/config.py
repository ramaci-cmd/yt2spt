"""Konfigurasi global – membaca config.toml dari direktori kerja."""
from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

_DEFAULT_CONFIG: dict = {
    "resolve": {
        "rate_per_minute": 30,
        "backoff_base": 2.0,
        "backoff_max": 120.0,
    },
    "match": {
        "auto_accept_threshold": 0.85,
        "review_threshold": 0.60,
        "title_weight": 0.6,
        "artist_weight": 0.4,
        "duration_tolerance_pct": 0.10,
    },
    "export": {
        "chunk_size": 50,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(path: Path | None = None) -> dict:
    """Muat config.toml. Kalau tidak ada, pakai default."""
    cfg_path = path or Path("config.toml")
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            user_cfg = tomllib.load(f)
        return _deep_merge(_DEFAULT_CONFIG, user_cfg)
    return dict(_DEFAULT_CONFIG)
