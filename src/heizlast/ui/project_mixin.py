from .load_save_mixin import MainWindowLoadSaveMixin
from .export_mixin import MainWindowExportMixin
from .settings_mixin import MainWindowSettingsMixin

class MainWindowProjectMixin(
    MainWindowLoadSaveMixin,
    MainWindowExportMixin,
    MainWindowSettingsMixin,
):
    """Compatibility aggregation mixin after splitting project responsibilities."""
    pass