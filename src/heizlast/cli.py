from __future__ import annotations
import sys
import traceback
from pathlib import Path

def _bootstrap_when_run_directly() -> None:
    this_file = Path(__file__).resolve()
    pkg_dir = this_file.parent
    src_dir = pkg_dir.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

if __package__ in (None, ""):
    _bootstrap_when_run_directly()
    from heizlast.runtime_bootstrap import bootstrap
    bootstrap()
    from heizlast.infrastructure.cli_runner import main as _main
else:
    from .runtime_bootstrap import bootstrap
    bootstrap()
    from .infrastructure.cli_runner import main as _main

def main() -> int:
    try:
        return _main()
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())