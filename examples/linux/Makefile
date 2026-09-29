# Build uspiflash-linux: a header generated from the installed uspiflash,
# then the tool, statically linked by default (`make LDFLAGS=` for dynamic).
UV      ?= uv
CC      ?= cc
LDFLAGS ?= -static
CFLAGS  ?= -Os
# Every chip type and every extra that changes the output, as `spiflash id`.
GENERATE = --level full --type nor --type nand --with sfdp --with sfdp_dumps \
           --with datasheet --with datasheets --with records --with provenance
VERSION := $(shell $(UV) run uspiflash --version)
override CFLAGS += -std=c99 -Wall -Wextra -Wpedantic -Wundef -Wshadow -Werror -D_DEFAULT_SOURCE

build/uspiflash-linux: uspiflash-linux.c build/uspiflash.h
	$(CC) $(CFLAGS) '-DUSPIFLASH_LINUX_VERSION="$(VERSION)"' -Ibuild $(LDFLAGS) -o $@ $<

build/uspiflash.h:
	mkdir -p build
	$(UV) run uspiflash generate -o $@ $(GENERATE)

clean:
	rm -rf build

.PHONY: clean
