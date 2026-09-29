"""Sphinx configuration for https://uspiflash.readthedocs.io/."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import uspiflash
from uspiflash import research

if TYPE_CHECKING:
    from sphinx.application import Sphinx

# The {fields} directive (docs/_ext/fields_table.py), not installed as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent / "_ext"))

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
    "fields_table",
]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
exclude_patterns = ["_build", "superpowers", "Thumbs.db", ".DS_Store"]
myst_enable_extensions = ["colon_fence", "deflist", "attrs_inline", "attrs_block"]
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


def _generate_experiment_pages(app: Sphinx) -> None:
    """Write ``_generated/experiments/<slug>.md`` for each experiment
    (spec §7.4), each ``{include}``-ing that experiment's own README, so
    ``experiments.md``'s glob toctree picks every one of them up."""
    root = research.find_root(Path(app.confdir))
    generated = Path(app.confdir) / "_generated" / "experiments"
    generated.mkdir(parents=True, exist_ok=True)
    for slug in research.slugs(root):
        text = f"# {slug}\n\n```{{include}} ../../../experiments/{slug}/README.md\n```\n"
        (generated / f"{slug}.md").write_text(text)


def setup(app: Sphinx) -> dict[str, bool]:
    """Regenerate the experiments index before each build (idempotent:
    writing the same generated files again changes nothing)."""
    app.connect("builder-inited", _generate_experiment_pages)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
