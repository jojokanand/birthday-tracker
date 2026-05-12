"""Birthday Tracker backend package.

Exposes the :class:`fastapi.FastAPI` application factory and the package version.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("birthday-tracker")
except PackageNotFoundError:  # pragma: no cover - happens in editable installs pre-build
    __version__ = "0.0.0"

__all__ = ["__version__"]
