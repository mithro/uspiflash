/* Test driver for a generated uspiflash header: one command per stdin line,
 * each answered by its output and a \x1e line. See tests/harness.py. */
#include <stdio.h>
#include <string.h>

#define USF_IMPLEMENTATION
#include USF_HEADER
#include "harness_names.h"

/* The most bytes one command carries (a 256-byte SFDP read, in part D). */
#define DATA_MAX 256u

/* Parses hex pairs from `s` into `buf`, which holds `max` bytes; returns how
 * many it wrote, never more than `max`. Task 12 replaces this with
 * simchip.h's identical sim_hex. */
static unsigned parse_hex(const char *s, uint8_t *buf, unsigned max)
{
    unsigned n = 0, v;
    while (n < max && s[0] && s[1] && sscanf(s, "%2x", &v) == 1) {
        buf[n++] = (uint8_t)v;
        s += 2;
    }
    return n;
}

#if USF_HAVE_MANUFACTURER || USF_HAVE_NAMES || USF_HAVE_DESCRIPTIONS || USF_HAVE_TEXT \
    || USF_HAVE_JSON
/* The character sink, for the levels that stream strings. */
static void out(void *ctx, char ch)
{
    (void)ctx;
    putchar(ch);
}
#endif

#if USF_HAVE_SOURCES || USF_HAVE_OPERATIONS
/* A source mask as names: the sources= line and each op's src=. */
static void srcs(uint8_t mask)
{
    unsigned i, first = 1;
    for (i = 0; i < 8; i++)
        if (mask >> i & 1) {
            printf(first ? "%s" : ",%s", SOURCE_NAMES[i]);
            first = 0;
        }
}
#endif

/* The accessor dump; tests compare it with uspiflash.oracle.accessors(). */
static void dump(const usf_chip *c)
{
    uint8_t id[USF_ID_MAX], n = usf_id(c, id), i;
    printf("family=%s type=%s bank=%u id=", FAMILY_NAMES[usf_family(c)],
           usf_type(c) ? "nand" : "nor", usf_bank(c));
    for (i = 0; i < n; i++)
        printf("%02x", id[i]);
    putchar('\n');
#if USF_HAVE_SIZE
    printf("size=%lu\n", (unsigned long)usf_size(c));
#endif
#if USF_HAVE_PAGE_SIZE
    printf("page=%lu\n", (unsigned long)usf_page_size(c));
#endif
#if USF_HAVE_SECTOR_SIZE
    printf("sector=%lu\n", (unsigned long)usf_sector_size(c));
#endif
#if USF_HAVE_VOLTAGE
    {
        uint16_t lo, hi;
        if (usf_voltage(c, &lo, &hi))
            printf("volt=%u-%u\n", lo, hi);
        else
            printf("volt=none\n");
    }
#endif
#if USF_HAVE_FEATURES
    {
        unsigned f, first = 1;
        printf("features=");
        for (f = 0; f < USF_FEATURE_COUNT; f++)
            if (usf_has_feature(c, (uint8_t)f)) {
                printf(first ? "%s" : " %s", FEATURE_NAMES[f]);
                first = 0;
            }
        putchar('\n');
    }
#endif
#if USF_HAVE_MANUFACTURER
    printf("mfr=");
    if (!usf_manufacturer(c, out, NULL))
        putchar('?');
    putchar('\n');
#endif
#if USF_HAVE_NAMES
    printf("names=");
    for (i = 0; i < usf_name_count(c); i++) {
        if (i)
            putchar(',');
        usf_name(c, i, out, NULL);
    }
    putchar('\n');
#endif
#if USF_HAVE_SOURCES
    printf("sources=");
    srcs(usf_sources(c));
    putchar('\n');
#endif
#if USF_HAVE_OPERATIONS
    {
        usf_op op;
        for (i = 0; usf_op_get(c, i, &op); i++) {
            printf("op=");
#if USF_HAVE_DESCRIPTIONS
            usf_op_name(op.id, out, NULL);   /* the name as the file stores it */
#else
            fputs(OP_NAMES[op.id], stdout);
#endif
            printf(" 0x%02x kind=%s proto=%s addr=%u ", op.opcode, KIND_NAMES[op.kind],
                   PROTO_NAMES[op.protocol], op.address_bytes);
            if (op.dummy_clocks == 0xFF)
                printf("dummy=var ");
            else
                printf("dummy=%u ", op.dummy_clocks);
            printf("data=%s bytes=%u src=",
                   op.data == 0 ? "none" : op.data == 1 ? "read" : "write", op.data_bytes);
            srcs(op.sources);
#if USF_HAVE_DESCRIPTIONS
            printf(" desc=");
            usf_op_description(op.id, out, NULL);
#endif
            putchar('\n');
        }
    }
#endif
}

int main(void)
{
    static char line[16384];
    while (fgets(line, sizeof line, stdin)) {
        char cmd = line[0];
        line[strcspn(line, "\n")] = 0;
        if (strchr("LATtJ", cmd)) {
            unsigned fam = 0, k;
            static char hex[1024];
            uint8_t data[DATA_MAX], n;
            unsigned len;
            usf_chip chips[USF_LOOKUP_MAX];
            if (sscanf(line + 2, "%u %1023s", &fam, hex) != 2)
                return 2;
            len = parse_hex(hex, data, DATA_MAX);
            /* usf_lookup takes a uint8_t length: pass at most 255 bytes. No
             * id and extended id together come near that, so the bytes left
             * out cannot change spiflash's answer. */
            n = usf_lookup((uint8_t)fam, data, (uint8_t)(len < 255u ? len : 255u), chips);
            if (cmd == 'L') {
                printf("%u\n", n);
                for (k = 0; k < n; k++)
                    printf("%u %u\n", chips[k].entry, chips[k].base);
            } else if (cmd == 'A') {
                for (k = 0; k < n; k++)
                    dump(&chips[k]);
            }
#if USF_HAVE_TEXT
            else if (cmd == 'T' || cmd == 't')
                usf_print(chips, n, cmd == 'T' ? USF_PRINT_OPCODES : 0, out, NULL);
#endif
#if USF_HAVE_JSON
            else if (cmd == 'J')
                usf_print_json(chips, n, out, NULL);
#endif
        }
        /* Task 12: P. */
        /* Part D: S. */
        fputs("\x1e\n", stdout);
        fflush(stdout);
    }
    return 0;
}
