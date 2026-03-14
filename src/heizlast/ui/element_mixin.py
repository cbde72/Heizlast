from .element_edit_mixin import MainWindowElementEditMixin
from .element_delete_mixin import MainWindowElementDeleteMixin
from .window_insert_mixin import MainWindowWindowInsertMixin

class MainWindowElementMixin(
    MainWindowElementEditMixin,
    MainWindowElementDeleteMixin,
    MainWindowWindowInsertMixin,
):
    """Compatibility aggregation mixin after splitting element responsibilities."""
    pass