from .redraw_mixin import MainWindowRedrawMixin
from .autowalls_mixin import MainWindowAutowallsMixin
from .overlay_mixin import MainWindowOverlayMixin

class MainWindowGraphicsMixin(
    MainWindowRedrawMixin,
    MainWindowAutowallsMixin,
    MainWindowOverlayMixin,
):
    """Compatibility aggregation mixin after splitting graphics responsibilities."""
    pass