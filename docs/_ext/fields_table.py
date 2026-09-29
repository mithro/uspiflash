"""A Sphinx extension: the ``{fields}`` directive.

Builds the *Levels* and *Extras* tables straight from
:mod:`uspiflash.levels` (``LEVELS``, ``LEVEL_OP_KINDS`` and each ``Field``
member's attribute docstring), so ``docs/usage.md``'s tables cannot drift
from the code. Usage::

    ```{fields} levels
    ```

    ```{fields} extras
    ```
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from itertools import pairwise
from typing import TYPE_CHECKING

from docutils import nodes
from docutils.parsers.rst import Directive
from spiflash.enums import OperationKind

from uspiflash.levels import LEVEL_OP_KINDS, LEVELS, Field

if TYPE_CHECKING:
    from sphinx.application import Sphinx

#: The two tables this directive can build.
_KINDS = ("levels", "extras")


def _field_docs() -> dict[Field, str]:
    """Each ``Field`` member's attribute docstring (the string literal right
    after its assignment), keyed by the member.

    ``ast`` reads the source rather than the runtime object: Python does not
    keep an attribute docstring as the member's ``__doc__``."""
    src = textwrap.dedent(inspect.getsource(Field))
    (cls,) = ast.parse(src).body
    if not isinstance(cls, ast.ClassDef):
        msg = "Field is not a class"
        raise TypeError(msg)
    docs: dict[Field, str] = {}
    body = cls.body
    for member, doc in pairwise(body):
        if not (isinstance(member, ast.Assign) and len(member.targets) == 1):
            continue
        target = member.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if not (isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant)):
            continue
        if not isinstance(doc.value.value, str):
            continue
        docs[Field[target.id]] = inspect.cleandoc(doc.value.value)
    missing = [f for f in Field if f not in docs]
    if missing:
        msg = f"Field members without an attribute docstring: {missing}"
        raise ValueError(msg)
    return docs


def _inline(text: str) -> list[nodes.Node]:
    """``text`` split on backtick-quoted spans into literal/plain nodes."""
    out: list[nodes.Node] = []
    for i, part in enumerate(text.split("`")):
        if not part:
            continue
        out.append(nodes.literal(part, part) if i % 2 else nodes.Text(part))
    return out


def _row(cells: list[str]) -> nodes.row:
    row = nodes.row()
    for cell in cells:
        entry = nodes.entry()
        para = nodes.paragraph()
        para += _inline(cell)
        entry += para
        row += entry
    return row


def _table(classes: list[str], headers: list[str], rows: list[list[str]]) -> nodes.table:
    table = nodes.table(classes=classes)
    tgroup = nodes.tgroup(cols=len(headers))
    table += tgroup
    for _ in headers:
        tgroup += nodes.colspec(colwidth=1)
    thead = nodes.thead()
    thead += _row(headers)
    tgroup += thead
    tbody = nodes.tbody()
    for r in rows:
        tbody += _row(r)
    tgroup += tbody
    return table


def _levels_table() -> nodes.table:
    docs = _field_docs()
    seen_fields: set[Field] = set()
    seen_kinds: frozenset[OperationKind] = frozenset()
    rows: list[list[str]] = []
    for level, fields in LEVELS.items():
        added = [f for f in Field if f in fields and f not in seen_fields]
        seen_fields |= fields
        adds = "; ".join(f"`{f.value}`: {docs[f]}" for f in added)
        kinds = LEVEL_OP_KINDS[level]
        new_kinds = [k for k in OperationKind if k in kinds and k not in seen_kinds]
        seen_kinds |= kinds
        if new_kinds:
            names = ", ".join(k.value for k in new_kinds)
            note = f"operations gain the {names} kind(s)"
            adds = f"{adds}; {note}" if adds else note
        rows.append([f"`{level}`", adds])
    return _table(["fields-levels"], ["Level", "Adds"], rows)


def _extras_table() -> nodes.table:
    docs = _field_docs()
    full = LEVELS["full"]
    rows = [[f"`{f.value}`", docs[f]] for f in Field if f not in full]
    return _table(["fields-extras"], ["Extra (`--with`)", "Adds"], rows)


class FieldsDirective(Directive):
    """``{fields} levels`` or ``{fields} extras``."""

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    has_content = False

    def run(self) -> list[nodes.Node]:
        which = self.arguments[0]
        if which == "levels":
            return [_levels_table()]
        if which == "extras":
            return [_extras_table()]
        msg = f"{{fields}}: unknown argument {which!r}, want one of {_KINDS}"
        raise self.error(msg)


def setup(app: Sphinx) -> dict[str, bool]:
    """Register the ``{fields}`` directive."""
    app.add_directive("fields", FieldsDirective)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
