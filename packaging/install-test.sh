#!/bin/sh
# Run by deb.yml's "Install test" in a clean debian:<suite> container after
# installing the built python3-uspiflash (and python3-spiflash from its repo).
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
