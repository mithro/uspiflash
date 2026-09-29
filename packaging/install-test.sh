#!/bin/sh
# Run by deb.yml's "Install test" in a clean debian:<suite> container after
# installing the built python3-uspiflash (and python3-spiflash from its repo).
set -eu
uspiflash --version
uspiflash --version | grep -q '(spiflash '
python3 -c 'import uspiflash, spiflash; print(uspiflash.__version__, spiflash.__version__)'
