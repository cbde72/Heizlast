from __future__ import annotations
import sys
import traceback
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox

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
    from heizlast.ui.main_window import MainWindow
else:
    from .runtime_bootstrap import bootstrap
    bootstrap()
    from .ui.main_window import MainWindow

def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        w = MainWindow()
        w.show()
        return app.exec()
    except Exception as exc:
        tb = traceback.format_exc()
        try:
            print (tb)
            QMessageBox.critical(None, "Heizlast V5.16 Startfehler", f"{exc}\n\n{tb}")
        except Exception:
            print(tb, file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
