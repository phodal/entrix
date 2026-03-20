"""Project presets for repository-specific fitness behavior."""

from routa_fitness.presets.base import ProjectPreset
from routa_fitness.presets.routa import RoutaPreset


def get_project_preset() -> ProjectPreset:
    """Return the active project preset."""
    return RoutaPreset()
