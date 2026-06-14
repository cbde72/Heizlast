from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_door_insert_reuses_window_opening_workflow():
    src = (ROOT / "src" / "heizlast" / "ui" / "window_insert_mixin.py").read_text(encoding="utf-8")

    assert "def _on_add_door_toggle" in src
    assert 'self._set_opening_insert_mode("door", checked)' in src
    assert 'self._add_opening_at(floor, scene_pos, opening_kind="door")' in src
    assert 'element_types=("Tür", "Haustür", "Terrassentür")' in src
    assert 'uid_prefix = "door" if is_door else "win"' in src
    assert 'element_type = str(v.get("element_type") or default_type).strip() or default_type' in src


def test_door_toolbar_action_is_next_to_window_insert():
    src = (ROOT / "src" / "heizlast" / "ui" / "build_mixin.py").read_text(encoding="utf-8")

    assert "self.act_add_door = self._make_action(" in src
    assert '"Tür einfügen"' in src
    assert "slot=self._on_add_door_toggle" in src
    assert 'icon=self._toolbar_icon("door_insert")' in src
    assert "self.act_add_window," in src
    assert "self.act_add_door," in src


def test_opening_graphics_and_selection_include_doors():
    redraw = (ROOT / "src" / "heizlast" / "ui" / "redraw_mixin.py").read_text(encoding="utf-8")
    presenter = (ROOT / "src" / "heizlast" / "presentation" / "plan_presenter.py").read_text(encoding="utf-8")
    selection = (ROOT / "src" / "heizlast" / "ui" / "selection_mixin.py").read_text(encoding="utf-8")
    delete = (ROOT / "src" / "heizlast" / "ui" / "element_delete_mixin.py").read_text(encoding="utf-8")
    room_ops = (ROOT / "src" / "heizlast" / "core" / "room_ops.py").read_text(encoding="utf-8")

    assert "is_opening_type(e.element_type)" in redraw
    assert "want_window = is_opening_type(e.element_type)" in presenter
    assert "is_opening_type(el.element_type) and el.uid" in selection
    assert "is_opening_type(e.element_type) and e.uid in uid_set" in delete
    assert "if is_opening_type(getattr(e, 'element_type', '')):" in room_ops
