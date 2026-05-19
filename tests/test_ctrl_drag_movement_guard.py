from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QGraphicsItem

from heizlast.domain.models import ElementModel, RoomModel
from heizlast.ui.graphics import ElementLabelItem, ElementLineItem, RoomPolygonItem, WindowLineItem


def _app():
    return QApplication.instance() or QApplication([])


def test_room_drag_requires_ctrl_but_model_sync_can_position_item():
    _app()
    room = RoomModel("r1", "EG", "Raum", 1.0, 2.0, 3.0, 4.0)
    item = RoomPolygonItem(room, lambda: False)
    start = item.pos()

    item._mouse_move_guard_active = True
    item._ctrl_move_active = False
    assert item.itemChange(QGraphicsItem.ItemPositionChange, QPointF(900.0, 900.0)) == start

    item._ctrl_move_active = True
    assert item.itemChange(QGraphicsItem.ItemPositionChange, QPointF(900.0, 900.0)) != start


def test_element_and_window_drag_requires_ctrl():
    _app()
    element = ElementModel(
        "r1",
        "Wand",
        4.0,
        1.0,
        x0_m=1.0,
        y0_m=2.0,
        x1_m=3.0,
        y1_m=2.0,
        length_m=2.0,
        height_m=2.0,
    )
    line = ElementLineItem(element)
    line_start = line.pos()
    line._mouse_move_guard_active = True
    line._ctrl_move_active = False
    assert line.itemChange(QGraphicsItem.ItemPositionChange, QPointF(900.0, 900.0)) == line_start
    line._ctrl_move_active = True
    assert line.itemChange(QGraphicsItem.ItemPositionChange, QPointF(900.0, 900.0)) != line_start

    window = WindowLineItem(element, orient="H", c_m=2.0, a0_m=0.0, a1_m=10.0)
    window_start = window.pos()
    window._mouse_move_guard_active = True
    window._ctrl_move_active = False
    assert window.itemChange(QGraphicsItem.ItemPositionChange, QPointF(900.0, 900.0)) == window_start
    window._ctrl_move_active = True
    assert window.itemChange(QGraphicsItem.ItemPositionChange, QPointF(180.0, 900.0)) != window_start


def test_element_label_drag_requires_ctrl():
    _app()
    element = ElementModel("r1", "Wand", 4.0, 1.0)
    label = ElementLabelItem(element)
    label.setPos(12.0, 14.0)
    start = label.pos()

    label._mouse_move_guard_active = True
    label._ctrl_move_active = False
    assert label.itemChange(QGraphicsItem.ItemPositionChange, QPointF(90.0, 90.0)) == start

    label._ctrl_move_active = True
    assert label.itemChange(QGraphicsItem.ItemPositionChange, QPointF(90.0, 90.0)) != start
