"""Small helpers that write C source text."""

from __future__ import annotations


def byte_array(name: str, data: bytes, per_line: int = 16) -> str:
    """``static const USF_ROM uint8_t usf__<name>[] = {...};``: tables are
    internal symbols (``usf__*``). Never empty: C forbids a zero-length
    initialiser, so an empty table holds one unused 0."""
    body = data or b"\0"
    lines = [
        "    " + ", ".join(f"0x{b:02x}" for b in body[i : i + per_line]) + ","
        for i in range(0, len(body), per_line)
    ]
    size = f"/* {len(data)} bytes */" if data else "/* empty: nothing reads it */"
    head = f"static const USF_ROM uint8_t usf__{name}[] = {{ {size}\n"
    return head + "\n".join(lines) + "\n};\n"


def defines(values: dict[str, int]) -> str:
    """``#define USF_<NAME> <value>`` lines, sorted by name."""
    return "".join(f"#define USF_{k} {v}\n" for k, v in sorted(values.items()))
