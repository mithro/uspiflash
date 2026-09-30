"""Build the riscv64 guest: the kernel and an initramfs holding busybox, the
SPI controller's module, uspiflash-linux and ``init``.

Runs in the image ``tools/qemu/Dockerfile`` makes (``run.py`` runs it there,
as the calling user), with the standard library only. It reads the unpacked
kernel and busybox from ``/opt/riscv``, the tool's source and the generated
header from the arguments, and writes ``Image`` and ``initramfs.cpio.gz`` to
``--out``.

The initramfs holds:

- busybox (static); ``init`` makes its applet links when it starts, since
  the riscv64 binary cannot run here to list them;
- ``spi-sifive.ko``, decompressed (busybox ``insmod`` may not read
  ``.ko.xz``), and any module it depends on, in load order in ``/modules``;
  ``spi-nor`` and ``mtd`` are never included: spidev, not the MTD layer,
  owns the flash;
- ``/bin/uspiflash-linux``, cross-compiled statically;
- ``init``.
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import subprocess
import tempfile
from pathlib import Path

RISCV = Path("/opt/riscv")
#: The modules the guest loads, with their dependencies before them.
MODULES = ("spi-sifive",)
#: Modules that must never reach the guest: they would claim the flash (R3).
EXCLUDED = frozenset({"spi-nor", "mtd"})


def kernel_release() -> str:
    """The unpacked kernel's release, as its modules directory names it."""
    (release,) = (RISCV / "kernel/usr/lib/modules").iterdir()
    return release.name


def module_path(release: str, name: str) -> Path:
    """The ``.ko.xz`` file of module ``name`` (``-`` and ``_`` alike)."""
    root = RISCV / "kernel/usr/lib/modules" / release / "kernel"
    wanted = name.replace("_", "-")
    for path in sorted(root.rglob("*.ko.xz")):
        if path.name.removesuffix(".ko.xz").replace("_", "-") == wanted:
            return path
    msg = f"no module {name} in {root}"
    raise SystemExit(msg)


def load_order(release: str, names: tuple[str, ...]) -> list[Path]:
    """``names`` and everything ``modinfo -F depends`` says they need,
    dependencies first."""
    order: list[Path] = []

    def visit(name: str) -> None:
        if name.replace("_", "-") in EXCLUDED:
            msg = f"module {name} is excluded, but something needs it"
            raise SystemExit(msg)
        path = module_path(release, name)
        if path in order:
            return
        depends = subprocess.run(
            ["modinfo", "-F", "depends", str(path)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for dep in filter(None, depends.split(",")):
            visit(dep)
        order.append(path)

    for name in names:
        visit(name)
    return order


def build(args: argparse.Namespace, root: Path) -> None:
    """Populate ``root`` with the initramfs's files."""
    for d in ("bin", "dev", "proc", "sys", "lib/modules"):
        (root / d).mkdir(parents=True, exist_ok=True)
    shutil.copy(RISCV / "busybox/usr/bin/busybox", root / "bin/busybox")
    (root / "bin/sh").symlink_to("busybox")

    names = []
    for ko in load_order(kernel_release(), MODULES):
        name = ko.name.removesuffix(".xz")
        with (root / "lib/modules" / name).open("wb") as out:
            subprocess.run(["xz", "-d", "-c", str(ko)], stdout=out, check=True)
        names.append(f"/lib/modules/{name}")
    (root / "modules").write_text("".join(f"{n}\n" for n in names), encoding="ascii")

    subprocess.run(
        [
            "riscv64-linux-gnu-gcc",
            "-static",
            "-Os",
            *args.cflag,
            f"-DUSPIFLASH_LINUX_VERSION={args.version_define}",
            f"-I{args.include}",
            "-o",
            str(root / "bin/uspiflash-linux"),
            str(args.source),
        ],
        check=True,
    )
    shutil.copy(args.init, root / "init")
    (root / "init").chmod(0o755)


def cpio(root: Path) -> bytes:
    """``root`` as a newc cpio archive, owned by root, in a stable order."""
    names = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    return subprocess.run(
        ["cpio", "--quiet", "-o", "-H", "newc", "-R", "0:0", "--reproducible"],
        input="".join(f"{n}\n" for n in names).encode(),
        capture_output=True,
        cwd=root,
        check=True,
    ).stdout


def main() -> int:
    """Build ``Image`` and ``initramfs.cpio.gz`` in ``--out``."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--source", type=Path, required=True, help="uspiflash-linux.c")
    parser.add_argument("--include", type=Path, required=True, help="uspiflash.h's directory")
    parser.add_argument("--init", type=Path, required=True, help="the guest's init script")
    parser.add_argument("--version-define", required=True, help="USPIFLASH_LINUX_VERSION")
    parser.add_argument("--cflag", action="append", default=[], help="a compiler flag")
    parser.add_argument("--out", type=Path, required=True, help="the output directory")
    args = parser.parse_args()

    release = kernel_release()
    shutil.copy(RISCV / f"kernel/boot/vmlinux-{release}", args.out / "Image")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build(args, root)
        image = cpio(root)
    with (args.out / "initramfs.cpio.gz").open("wb") as f:
        f.write(gzip.compress(image, mtime=0))
    print(f"kernel {release}, initramfs {len(image)} bytes uncompressed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
