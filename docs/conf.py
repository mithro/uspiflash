"""Sphinx configuration for https://uspiflash.readthedocs.io/."""

from __future__ import annotations

import uspiflash

project = "uspiflash"
author = "Tim Ansell"
project_copyright = "2026, Tim Ansell"
release = uspiflash.__version__
version = release

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
exclude_patterns = ["_build", "superpowers", "Thumbs.db", ".DS_Store"]
myst_enable_extensions = ["colon_fence", "deflist", "attrs_inline"]
myst_heading_anchors = 3
autosummary_generate = True
autodoc_default_options = {"members": True, "undoc-members": True, "member-order": "bysource"}
autodoc_typehints = "description"
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
html_theme = "furo"
html_title = "uspiflash"
html_static_path = ["_static"]
html_theme_options = {
    "source_repository": "https://github.com/mithro/uspiflash/",
    "source_branch": "main",
    "source_directory": "docs/",
}
