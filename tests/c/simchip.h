/* A simulated SPI flash for the tests: answers id commands from a table
 * (a "spec", see tests/test_probe.py) and RDSFDP (0x5A) from an SFDP image,
 * logging every transaction. Shared by tests/c/harness.c and
 * tests/linux/fake_spidev.c. */
#ifndef SIMCHIP_H
#define SIMCHIP_H

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct sim_reply {
    uint8_t cmd, txlen, len;
    uint8_t data[16];
};

struct sim {
    struct sim_reply replies[8];
    unsigned nreplies;
    uint8_t fill;
    uint8_t sfdp[4096];
    unsigned sfdp_len;
    FILE *log;                    /* where to log transactions, or NULL */
};

static unsigned sim_hex(const char *s, uint8_t *buf, unsigned max)
{
    unsigned n = 0, v;
    while (n < max && s[0] && s[1] && sscanf(s, "%2x", &v) == 1) {
        buf[n++] = (uint8_t)v;
        s += 2;
    }
    return n;
}

/* Parse "CC/N=HEX ... fill=FF sfdp=HEX" into s (s->log is left alone). */
static void sim_parse(struct sim *s, const char *spec)
{
    static char buf[16384];
    char *tok;
    FILE *log = s->log;
    memset(s, 0, sizeof *s);
    s->log = log;
    s->fill = 0xFF;
    strncpy(buf, spec, sizeof buf - 1);
    buf[sizeof buf - 1] = 0;
    for (tok = strtok(buf, " "); tok; tok = strtok(NULL, " ")) {
        unsigned cmd, txlen;
        char hex[64];
        if (!strncmp(tok, "fill=", 5)) {
            s->fill = (uint8_t)strtoul(tok + 5, NULL, 16);
        } else if (!strncmp(tok, "sfdp=", 5)) {
            s->sfdp_len = sim_hex(tok + 5, s->sfdp, sizeof s->sfdp);
        } else if (s->nreplies < 8 && sscanf(tok, "%2x/%u=%63s", &cmd, &txlen, hex) == 3) {
            struct sim_reply *r = &s->replies[s->nreplies++];
            r->cmd = (uint8_t)cmd;
            r->txlen = (uint8_t)txlen;
            r->len = (uint8_t)sim_hex(hex, r->data, sizeof r->data);
        }
    }
}

static void sim_log(FILE *f, const uint8_t *b, uint8_t n)
{
    uint8_t i;
    for (i = 0; i < n; i++)
        fprintf(f, "%02x", b[i]);
}

static void sim_xfer(void *ctx, const uint8_t *tx, uint8_t txlen, uint8_t *rx, uint8_t rxlen)
{
    struct sim *s = (struct sim *)ctx;
    unsigned i, k;
    for (i = 0; i < rxlen; i++)
        rx[i] = s->fill;
    if (tx[0] == 0x5A && txlen == 5 && s->sfdp_len) {
        /* RDSFDP: 3 address bytes, 8 dummy clocks (the fifth byte). */
        unsigned addr = (unsigned)tx[1] << 16 | (unsigned)tx[2] << 8 | tx[3];
        for (i = 0; i < rxlen; i++)
            rx[i] = addr + i < s->sfdp_len ? s->sfdp[addr + i] : 0xFF;
    } else {
        for (k = 0; k < s->nreplies; k++)
            if (s->replies[k].cmd == tx[0] && s->replies[k].txlen == txlen) {
                for (i = 0; i < rxlen && i < s->replies[k].len; i++)
                    rx[i] = s->replies[k].data[i];
                break;
            }
    }
    if (s->log) {
        fputs("> ", s->log);
        sim_log(s->log, tx, txlen);
        fputs(" < ", s->log);
        sim_log(s->log, rx, rxlen);
        fputc('\n', s->log);
    }
}

#endif
