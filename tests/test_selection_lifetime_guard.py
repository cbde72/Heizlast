from heizlast.ui.selection_mixin import MainWindowSelectionMixin


class DeletedScene:
    def selectedItems(self):
        raise RuntimeError("Internal C++ object already deleted.")


class Scene:
    def __init__(self, items):
        self._items = items

    def selectedItems(self):
        return list(self._items)


class SelectionHarness(MainWindowSelectionMixin):
    def __init__(self):
        self.scene_KG = DeletedScene()
        self.scene_EG = DeletedScene()
        self.scene_DG = Scene(["dg-item"])
        self.rooms = {}
        self._selected_room_id = "old-room"
        self._in_sync_list_with_graphics_selection = False
        self.populated = False

    def _populate_room_form(self):
        self.populated = True

    def _sync_list_with_uid(self, uid):
        raise AssertionError("No element UID should be synchronized.")


def test_scene_selection_changed_ignores_deleted_qt_scene():
    harness = SelectionHarness()

    harness._on_scene_selection_changed("KG")

    assert harness._selected_room_id is None
    assert harness.populated is True


def test_selected_graphics_items_skips_deleted_scenes():
    harness = SelectionHarness()

    assert harness._selected_graphics_items() == ["dg-item"]
