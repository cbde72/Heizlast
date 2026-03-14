from __future__ import annotations
import os
from pathlib import Path

def package_dir() -> Path:
    return Path(__file__).resolve().parent

def src_dir() -> Path:
    return package_dir().parent

def project_root() -> Path:
    env = os.environ.get("HEIZLAST_PROJECT_ROOT")
    return Path(env) if env else src_dir().parent.parent

def assets_dir() -> Path:
    return project_root() / "assets"

def fonts_dir() -> Path:
    return assets_dir() / "fonts"