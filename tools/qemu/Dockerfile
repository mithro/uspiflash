# QEMU for riscv64 (sifive_u), a riscv64 cross compiler, and the unpacked
# riscv64 kernel and busybox the guest is built from. run.py builds this
# image and runs build_image.py and QEMU in it (tools/qemu/README.md).
#
# The base image and the apt snapshot are uspiflash.ledger.IMAGE and
# SNAPSHOT (the `sizes` job's), so the packages are the same whatever the
# live mirror holds today. run.py passes them in, with the kernel's and
# busybox's versions and their .debs' sha256s.
ARG IMAGE
FROM ${IMAGE}

ARG SNAPSHOT
ARG KERNEL
ARG KERNEL_VERSION
ARG KERNEL_SHA256
ARG BUSYBOX_VERSION
ARG BUSYBOX_SHA256

RUN rm -f /etc/apt/sources.list.d/debian.sources \
 && echo "deb http://snapshot.debian.org/archive/debian/${SNAPSHOT}/ trixie main" > /etc/apt/sources.list \
 && echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99snapshot \
 && dpkg --add-architecture riscv64 \
 && apt-get update -q \
 && apt-get install -y -q --no-install-recommends \
      qemu-system-riscv opensbi \
      gcc-riscv64-linux-gnu libc6-dev-riscv64-cross \
      cpio xz-utils kmod python3 \
 && rm -rf /var/lib/apt/lists/*

# Downloaded and unpacked, not installed: they are riscv64 files for the guest.
RUN mkdir -p /opt/riscv && cd /opt/riscv \
 && apt-get update -q \
 && apt-get download \
      "busybox-static:riscv64=${BUSYBOX_VERSION}" \
      "linux-image-${KERNEL}:riscv64=${KERNEL_VERSION}" \
 && printf '%s  %s\n' "${BUSYBOX_SHA256}" busybox-static_*.deb \
      "${KERNEL_SHA256}" linux-image-*.deb | sha256sum -c \
 && dpkg-deb -x busybox-static_*.deb busybox \
 && dpkg-deb -x linux-image-*.deb kernel \
 && rm ./*.deb \
 && rm -rf /var/lib/apt/lists/*
