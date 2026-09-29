#!/bin/sh
# Run by deb.yml's "Install test" in a clean debian:<suite> container after
# installing the built python3-uspiflash (and python3-spiflash from its repo).
set -eu
uspiflash --version
uspiflash --version | grep -q '(spiflash '
python3 -c 'import uspiflash, spiflash; print(uspiflash.__version__, spiflash.__version__)'
cd "$(mktemp -d)"
uspiflash generate -o uspiflash.h --level full
printf '#define USF_IMPLEMENTATION\n#include "uspiflash.h"\n' > impl.c
for opt in -O0 -O2; do
    gcc -std=c99 -Wall -Wextra -Wpedantic -Wundef -Werror "$opt" -c impl.c
done
