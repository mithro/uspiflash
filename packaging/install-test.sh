#!/bin/sh
# Run by deb.yml's "Install test" in a clean debian:<suite> container after
# installing the built python3-uspiflash and uspiflash-linux (and python3-spiflash
# from its repo). Only the amd64 job runs it: it alone has both packages.
set -eu
uspiflash --version
uspiflash --version | grep -q '(spiflash '
python3 -c 'import uspiflash, spiflash; print(uspiflash.__version__, spiflash.__version__)'
cd "$(mktemp -d)"
# SPI NOR only (generate's default), and every chip type, NAND included.
uspiflash generate -o nor.h --level full
uspiflash generate -o all.h --level full --type nor --type nand
for h in nor all; do
    printf '#define USF_IMPLEMENTATION\n#include "%s.h"\n' "$h" > "$h.c"
    for opt in -O0 -O2; do
        gcc -std=c99 -Wall -Wextra -Wpedantic -Wundef -Werror "$opt" -c "$h.c"
    done
done
# uspiflash-linux: its version, and offline lookups (no spidev device needed):
# a NOR chip with its commands, a NAND chip, and an unknown id (exit 1).
uspiflash-linux --version | grep -q '^uspiflash-linux: uspiflash '
uspiflash-linux id ef4018 --opcodes | grep -q '0x6b  READ_1_1_4'
uspiflash-linux id c8b148 | grep -q '(nand)'
if uspiflash-linux id ee7777; then exit 1; fi
