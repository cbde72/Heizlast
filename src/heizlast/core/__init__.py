"""Lightweight core package exports.

This module must stay importable without optional UI dependencies such as PySide6,
so tests can import pure domain/core submodules in headless environments.
"""

try:
    from .config import CSV_DELIMITER, DEFAULT_U, DEFAULT_FACTOR, VentilationCfg
except Exception:  # pragma: no cover
    CSV_DELIMITER = ';'
    DEFAULT_U = {}
    DEFAULT_FACTOR = {}
    VentilationCfg = object

try:
    from .csv_io import load_rooms, load_elements, save_rooms, save_elements
except Exception:  # pragma: no cover
    pass

try:
    from .element_access import get_room_elements, element_axis_length_from_geometry, meta_rooms
except Exception:  # pragma: no cover
    pass

try:
    from .element_metrics import ElementMetricsService
except Exception:  # pragma: no cover
    pass

try:
    from .geometry import build_auto_walls_shared_merge
except Exception:  # pragma: no cover
    pass

try:
    from .heatload import calc_heatloads, ensure_auto_decks
except Exception:  # pragma: no cover
    pass

try:
    from .attic_geometry import AtticGeometry
except Exception:  # pragma: no cover
    pass

try:
    from .dormer_geometry import DormerGeometry, DormerInput, DormerResult, RoofContext
except Exception:  # pragma: no cover
    pass

from .polygon_ops import snap_m, parse_polygon_m, serialize_polygon_m


__all__ = [
    "CSV_DELIMITER",
    "DEFAULT_U",
    "DEFAULT_FACTOR",
    "VentilationCfg",
    "load_rooms",
    "load_elements",
    "save_rooms",
    "save_elements",
    "get_room_elements",
    "element_axis_length_from_geometry",
    "meta_rooms",
    "ElementMetricsService",
    "build_auto_walls_shared_merge",
    "calc_heatloads",
    "ensure_auto_decks",
    "AtticGeometry",
    "DormerGeometry",
    "DormerInput",
    "DormerResult",
    "RoofContext",
    "snap_m",
    "parse_polygon_m",
    "serialize_polygon_m",
]
