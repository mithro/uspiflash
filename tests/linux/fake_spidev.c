/* LD_PRELOAD shim: opening $FAKE_SPIDEV gives a simulated SPI flash
 * ($FAKE_SPIDEV_SPEC, tests/c/simchip.h's spec) and SPI_IOC_MESSAGE(2)
 * transactions are answered by it; with $FAKE_SPIDEV_LOG set, each is
 * logged to stderr. Test support only. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include <sys/ioctl.h>
#include <linux/spi/spidev.h>

#include "simchip.h"

static struct sim sim;
static int fake_fd = -1;

typedef int (*open_fn)(const char *, int, ...);
typedef int (*ioctl_fn)(int, unsigned long, ...);

/* The next definition of `name`. ISO C has no conversion from dlsym's
 * object pointer to a function pointer, so the bytes are copied (POSIX
 * guarantees they are the same). */
static void next_symbol(const char *name, void *fn, size_t size)
{
    void *p = dlsym(RTLD_NEXT, name);
    memcpy(fn, &p, size);
}

static int fake_open(const char *path, int flags, mode_t mode, const char *real_name)
{
    open_fn real;
    const char *fake = getenv("FAKE_SPIDEV");
    next_symbol(real_name, &real, sizeof real);
    if (fake && strcmp(path, fake) == 0) {
        const char *spec = getenv("FAKE_SPIDEV_SPEC");
        sim.log = getenv("FAKE_SPIDEV_LOG") ? stderr : NULL;
        sim_parse(&sim, spec ? spec : "");
        fake_fd = real("/dev/null", O_RDWR);
        return fake_fd;
    }
    return real(path, flags, mode);
}

int open(const char *path, int flags, ...)
{
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = (mode_t)va_arg(ap, int);
        va_end(ap);
    }
    return fake_open(path, flags, mode, "open");
}

int open64(const char *path, int flags, ...)
{
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = (mode_t)va_arg(ap, int);
        va_end(ap);
    }
    return fake_open(path, flags, mode, "open64");
}

int ioctl(int fd, unsigned long request, ...)
{
    ioctl_fn real;
    va_list ap;
    void *arg;
    va_start(ap, request);
    arg = va_arg(ap, void *);
    va_end(ap);
    if (fd < 0 || fd != fake_fd) {
        next_symbol("ioctl", &real, sizeof real);
        return real(fd, request, arg);
    }
    if (request == SPI_IOC_MESSAGE(2)) {
        struct spi_ioc_transfer *t = (struct spi_ioc_transfer *)arg;
        sim_xfer(&sim, (const uint8_t *)(uintptr_t)t[0].tx_buf, (uint8_t)t[0].len,
                 (uint8_t *)(uintptr_t)t[1].rx_buf, (uint8_t)t[1].len);
        return (int)(t[0].len + t[1].len);
    }
    return 0;  /* mode, bits per word and speed settings all "succeed" */
}
