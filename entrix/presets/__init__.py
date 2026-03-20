"""Project presets for repository-specific fitness behavior."""

from entrix.presets.base import ProjectPreset
from entrix.presets.routa import RoutaPreset


def get_project_preset() -> ProjectPreset:
    """Return the active project preset."""
    return RoutaPreset()
