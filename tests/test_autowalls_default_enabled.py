from pathlib import Path


def test_autowalls_is_enabled_by_default_in_main_window_and_action():
    root = Path(__file__).resolve().parents[1]
    main_window = (root / "src" / "heizlast" / "ui" / "main_window.py").read_text(encoding="utf-8")
    build_mixin = (root / "src" / "heizlast" / "ui" / "build_mixin.py").read_text(encoding="utf-8")

    assert "self.autowalls_enabled = True" in main_window
    assert '"Auto-Wände aktiv"' in build_mixin
    assert "checked=True" in build_mixin[build_mixin.index('self.act_autowalls_enabled = self._make_action('):build_mixin.index('self.act_add_window = self._make_action(')]
