"""Sphinx configuration for the Birthday Tracker backend documentation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the package importable so autodoc can introspect it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

project = "Birthday Tracker"
author = "jyothsnakanand"
release = os.environ.get("BIRTHDAY_TRACKER_VERSION", "0.1.0")

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # Google-style docstrings
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinxcontrib.autodoc_pydantic",  # Pydantic v2 model rendering
]

# autodoc-pydantic: cleaner output, no duplicate field descriptions.
autodoc_pydantic_model_show_json = False
autodoc_pydantic_settings_show_json = False
autodoc_pydantic_model_show_config_summary = False
autodoc_pydantic_settings_show_config_summary = False

# Napoleon settings — Google style only, no NumPy.
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
