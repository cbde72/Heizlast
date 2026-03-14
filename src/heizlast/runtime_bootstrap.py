from __future__ import annotations
import os
import sys
from pathlib import Path

def bootstrap() -> Path:
    pkg_dir = Path(__file__).resolve().parent
    src_dir = pkg_dir.parent
    project_root = src_dir.parent.parent

    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    os.environ.setdefault("HEIZLAST_PACKAGE_DIR", str(pkg_dir))
    os.environ.setdefault("HEIZLAST_PROJECT_ROOT", str(project_root))
    os.environ.setdefault("MPLCONFIGDIR", str(project_root / ".mplconfig"))

    try:
        (project_root / ".mplconfig").mkdir(exist_ok=True)
    except Exception:
        pass

    return pkg_dir