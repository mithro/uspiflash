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

/* Defines the C function `name`, which fakes the device and otherwise
 * forwards to the next definition of the symbol `symbol`. */
#define INTERPOSE_OPEN(name, symbol)                                 \
    int name(const char *path, int flags, ...)                       \
    {                                                                \
        mode_t mode = 0;                                             \
        if (flags & O_CREAT) {                                       \
            va_list ap;                                              \
            va_start(ap, flags);                                     \
            mode = (mode_t)va_arg(ap, int);                          \
            va_end(ap);                                              \
        }                                                            \
        return fake_open(path, flags, mode, symbol);                 \
    }

/* Both the symbols open and open64 are interposed, whichever a program
 * calls. With 64-bit file offsets (_FILE_OFFSET_BITS=64, which _TIME_BITS=64
 * implies, as on Debian's armhf since trixie), glibc's <fcntl.h> renames the
 * C function open to the symbol open64, so a definition of open is open64,
 * and the symbol open needs a C function of another name. */
#ifdef __USE_FILE_OFFSET64
int open_off32(const char *path, int flags, ...) __asm__("open");
INTERPOSE_OPEN(open_off32, "open")
INTERPOSE_OPEN(open, "open64")
#else
INTERPOSE_OPEN(open, "open")
INTERPOSE_OPEN(open64, "open64")
#endif

static int fake_ioctl(int fd, unsigned long request, void *arg, const char *real_name)
{
    ioctl_fn real;
    if (fd < 0 || fd != fake_fd) {
        next_symbol(real_name, &real, sizeof real);
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

/* As INTERPOSE_OPEN, for ioctl. */
#define INTERPOSE_IOCTL(name, symbol)                                \
    int name(int fd, unsigned long request, ...)                     \
    {                                                                \
        va_list ap;                                                  \
        void *arg;                                                   \
        va_start(ap, request);                                       \
        arg = va_arg(ap, void *);                                    \
        va_end(ap);                                                  \
        return fake_ioctl(fd, request, arg, symbol);                 \
    }

/* Likewise ioctl and, on a 32-bit machine, __ioctl_time64: with 64-bit
 * time_t there (_TIME_BITS=64), <sys/ioctl.h> renames ioctl to the symbol
 * __ioctl_time64. */
#ifdef __USE_TIME64_REDIRECTS
int ioctl_time32(int fd, unsigned long request, ...) __asm__("ioctl");
INTERPOSE_IOCTL(ioctl_time32, "ioctl")
INTERPOSE_IOCTL(ioctl, "__ioctl_time64")
#else
INTERPOSE_IOCTL(ioctl, "ioctl")
#if defined(__TIMESIZE) && __TIMESIZE == 32
int ioctl_time64(int fd, unsigned long request, ...) __asm__("__ioctl_time64");
INTERPOSE_IOCTL(ioctl_time64, "__ioctl_time64")
#endif
#endif
