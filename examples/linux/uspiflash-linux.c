/*
 * uspiflash-linux: identify the SPI flash chip on a Linux spidev device and
 * describe it the way `spiflash id --opcodes` does, or look an id up offline.
 *
 *   uspiflash-linux [-D /dev/spidevB.C] [-s HZ] [--json | --sfdp] [--opcodes]
 *   uspiflash-linux id HEX [--method jedec|rems|res1|res2|at25f|st95] [--json] [--opcodes]
 *   uspiflash-linux --version
 *
 * Built against a header made by `uspiflash generate --level full --type nor
 * --type nand` with every extra that changes the output (see the Makefile):
 * every chip type, as `spiflash id` knows them (generate alone keeps only
 * SPI NOR). Each library transaction is one SPI_IOC_MESSAGE(2): the command
 * bytes, then the answer, chip select held.
 */
#include <ctype.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>
#include <linux/spi/spidev.h>

/* The builder passes the generator's `uspiflash --version` line. */
#ifndef USPIFLASH_LINUX_VERSION
#define USPIFLASH_LINUX_VERSION "unknown"
#endif

/* The probe's wake-up wait after RES (tRES1): see USF_DELAY_US in the header. */
static void delay_us(unsigned us)
{
    struct timespec ts;
    ts.tv_sec = 0;
    ts.tv_nsec = (long)us * 1000L;
    nanosleep(&ts, NULL);
}
#define USF_DELAY_US(us) delay_us(us)

#define USF_IMPLEMENTATION
#include "uspiflash.h"

/* spiflash's --method names, in USF_FAMILY_* order. */
static const char *const families[] = {"jedec", "rems", "res1", "res2", "at25f", "st95"};

struct dev {
    int fd;
    uint32_t hz;
};

static void xfer(void *ctx, const uint8_t *tx, uint8_t txlen, uint8_t *rx, uint8_t rxlen)
{
    struct dev *d = (struct dev *)ctx;
    struct spi_ioc_transfer t[2];
    memset(t, 0, sizeof t);
    t[0].tx_buf = (uintptr_t)tx;
    t[0].len = txlen;
    t[0].speed_hz = d->hz;
    t[0].bits_per_word = 8;
    t[1].rx_buf = (uintptr_t)rx;
    t[1].len = rxlen;
    t[1].speed_hz = d->hz;
    t[1].bits_per_word = 8;
    if (ioctl(d->fd, SPI_IOC_MESSAGE(2), t) < 0) {
        perror("uspiflash-linux: SPI_IOC_MESSAGE");
        exit(2);
    }
}

static void put(void *ctx, char ch)
{
    (void)ctx;
    putchar(ch);
}

static int family_code(const char *name)
{
    int i;
    for (i = 0; i < 6; i++)
        if (strcmp(name, families[i]) == 0)
            return i;
    return -1;
}

static int nibble(char ch)
{
    return isdigit((unsigned char)ch) ? ch - '0' : tolower((unsigned char)ch) - 'a' + 10;
}

/* What spiflash's id parser ignores: whitespace (Python's \s, ASCII part),
 * ':', '_' and '-'. */
static int is_separator(unsigned char ch)
{
    return isspace(ch) || (ch >= 0x1c && ch <= 0x1f) || ch == ':' || ch == '_' || ch == '-';
}

/* An id as `spiflash id` reads it (spiflash.model.parse_id): separators
 * anywhere are dropped, then a leading "0x"; what is left must be a
 * non-empty, even number of hex digits ("0xEF4018", "ef:40:18", "ef 40 18").
 * Into data; the byte count, or -1 if `s` is not an id or is longer than max
 * bytes. */
static int parse_hex(const char *s, uint8_t *data, unsigned max)
{
    unsigned digits = 0, seen = 0, lead_zero = 0;
    for (; *s; s++) {
        unsigned char ch = (unsigned char)*s;
        if (is_separator(ch))
            continue;
        seen++;
        if (seen == 2 && lead_zero && (ch == 'x' || ch == 'X')) {
            digits = 0;                    /* the "0x" prefix */
            continue;
        }
        if (!isxdigit(ch) || digits / 2 == max)
            return -1;
        if (seen == 1)
            lead_zero = ch == '0';
        if (digits % 2)
            data[digits / 2] = (uint8_t)(data[digits / 2] | nibble((char)ch));
        else
            data[digits / 2] = (uint8_t)(nibble((char)ch) << 4);
        digits++;
    }
    return digits && digits % 2 == 0 ? (int)(digits / 2) : -1;
}

static void hex(const uint8_t *b, unsigned n)
{
    unsigned i;
    for (i = 0; i < n; i++)
        printf("%02x", b[i]);
}

/* The chip's own SFDP, as tests/c/harness.c's S command prints it
 * (uspiflash.oracle.sfdp_fields()'s format). */
static void print_sfdp(const usf_sfdp *f)
{
    static const char *const modes[] = {"1-1-2", "1-2-2", "1-1-4", "1-4-4", "2-2-2", "4-4-4"};
    unsigned k;
    printf("sfdp=%u.%u dwords=%u addr=%u erase4k=0x%02x dtr=%u size=%lu page=%u", f->rev_major,
           f->rev_minor, f->dwords, f->address_bytes, f->erase_4k_opcode, f->flags & USF_SFDP_DTR,
           (unsigned long)f->size, f->page_size);
    if (f->quad_enable == 0xFF)
        printf(" qe=none");
    else
        printf(" qe=%u", f->quad_enable);
    printf(" en4b=0x%02x ex4b=0x%02x\nerase", f->enter_4b, f->exit_4b);
    for (k = 0; k < 4; k++)
        if (f->erase_log2[k])
            printf(" %u:%u:0x%02x", k + 1, f->erase_log2[k], f->erase_opcode[k]);
    printf("\nread");
    for (k = 0; k < 6; k++)
        if (f->reads >> k & 1)
            printf(" %s:0x%02x:%u+%u", modes[k], f->read_opcode[k], f->read_clocks[k] >> 5,
                   f->read_clocks[k] & 31u);
    putchar('\n');
}

static int usage(void)
{
    fputs("usage: uspiflash-linux [-D DEVICE] [-s HZ] [--json | --sfdp] [--opcodes]\n"
          "       uspiflash-linux id HEX [--method FAMILY] [--json] [--opcodes]\n"
          "       uspiflash-linux --version\n",
          stderr);
    return 2;
}

int main(int argc, char **argv)
{
    const char *device = "/dev/spidev0.0", *method = "jedec", *idhex = NULL;
    int json = 0, opcodes = 0, want_sfdp = 0, i;
    uint32_t hz = 1000000;

    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-D") && i + 1 < argc)
            device = argv[++i];
        else if (!strcmp(argv[i], "-s") && i + 1 < argc)
            hz = (uint32_t)strtoul(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "--method") && i + 1 < argc)
            method = argv[++i];
        else if (!strcmp(argv[i], "--json"))
            json = 1;
        else if (!strcmp(argv[i], "--opcodes"))
            opcodes = 1;
        else if (!strcmp(argv[i], "--sfdp"))
            want_sfdp = 1;
        else if (!strcmp(argv[i], "--version")) {
            printf("uspiflash-linux: %s\n", USPIFLASH_LINUX_VERSION);
            return 0;
        } else if (!strcmp(argv[i], "id") && i + 1 < argc)
            idhex = argv[++i];
        else
            return usage();
    }
    if (json && want_sfdp)                /* the SFDP lines are text, not JSON */
        return usage();

    if (idhex) {                         /* offline, like `spiflash id` */
        uint8_t data[255];             /* usf_lookup takes up to 255 bytes */
        usf_chip chips[USF_LOOKUP_MAX];
        uint8_t found;
        int fam = family_code(method), n = parse_hex(idhex, data, sizeof data);
        if (fam < 0 || n < 0)
            return usage();
        found = usf_lookup((uint8_t)fam, data, (uint8_t)n, chips);
        if (json)
            usf_print_json(chips, found, put, NULL);
        else
            usf_print(chips, found, opcodes ? USF_PRINT_OPCODES : 0, put, NULL);
        return found ? 0 : 1;
    }

    {                                     /* probe a real device */
        struct dev d;
        usf_bus bus;
        usf_probe_result r;
        uint8_t mode = SPI_MODE_0, bits = 8;
        d.fd = open(device, O_RDWR);
        d.hz = hz;
        if (d.fd < 0) {
            perror(device);
            return 2;
        }
        if (ioctl(d.fd, SPI_IOC_WR_MODE, &mode) < 0 || ioctl(d.fd, SPI_IOC_WR_BITS_PER_WORD, &bits) < 0
            || ioctl(d.fd, SPI_IOC_WR_MAX_SPEED_HZ, &hz) < 0) {
            perror("uspiflash-linux: configuring the spidev device");
            return 2;
        }
        bus.xfer = xfer;
        bus.ctx = &d;
        usf_probe(&bus, &r);
        if (r.count) {
            if (json)
                usf_print_json(r.chip, r.count, put, NULL);
            else
                usf_print(r.chip, r.count, opcodes ? USF_PRINT_OPCODES : 0, put, NULL);
        } else if (r.len) {
            printf("no chip in the database answers %s ", families[r.family]);
            hex(r.id, r.len);
            putchar('\n');
        } else {
            printf("no answer from the chip (the bus reads all 0x00 or all 0xff)\n");
        }
        if (want_sfdp) {
            usf_sfdp s;
            if (usf_sfdp_read(&bus, &s))
                print_sfdp(&s);
            else
                printf("sfdp=none\n");
        }
        close(d.fd);
        return r.count ? 0 : r.len ? 1 : 2;
    }
}
