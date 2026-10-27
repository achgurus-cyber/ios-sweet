#!/usr/bin/env python3
"""Build an experimental A24 diagnostic boot.tar.md5 from a matching stock boot.

This replaces the Android kernel with the A24 shim and installs an empty
initramfs. It does not contain XNU or Android userspace. The result is only
for an already-unlocked SM-A245F on the exact matching firmware. AVB metadata
is intentionally not re-signed; an unlocked bootloader is required. This tool
does not flash a device.
"""
import argparse
import hashlib
import io
import struct
import tarfile
from pathlib import Path

PAGE = 4096
BOOT_PARTITION_SIZE = 64 * 1024 * 1024
SEANDROID = b"SEANDROIDENFORCE"
AVB_FOOTER = b"AVBf"


def align(value: int, boundary: int = PAGE) -> int:
    return (value + boundary - 1) // boundary * boundary


def empty_newc_gzip() -> bytes:
    # A valid empty newc archive with the required TRAILER!!! entry.
    fields = [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 11]
    header = b"070701" + b"".join(f"{x:08x}".encode("ascii") for x in fields)
    cpio = header + b"TRAILER!!!\0"
    cpio += b"\0" * ((-len(cpio)) % 4)
    import gzip

    return gzip.compress(cpio, mtime=0)


def build(stock_path: Path, kernel_path: Path, output_path: Path) -> None:
    stock = bytearray(stock_path.read_bytes())
    kernel = kernel_path.read_bytes()
    if len(stock) != BOOT_PARTITION_SIZE or stock[:8] != b"ANDROID!":
        raise SystemExit("input must be a raw 64 MiB Android boot partition")
    if struct.unpack_from("<I", stock, 40)[0] != 4:
        raise SystemExit("input is not Android boot header v4")
    if len(kernel) > 0x4000000:
        raise SystemExit("shim kernel is unexpectedly large")
    marker = stock.find(SEANDROID)
    if marker < 0 or stock.rfind(AVB_FOOTER) != BOOT_PARTITION_SIZE - 64:
        raise SystemExit("stock Samsung marker or AVB footer not found at expected location")

    old_kernel_size, old_ramdisk_size = struct.unpack_from("<II", stock, 8)
    signature_size = struct.unpack_from("<I", stock, 1580)[0]
    kernel_off = PAGE
    ramdisk_off = kernel_off + align(old_kernel_size)
    signature_off = ramdisk_off + align(old_ramdisk_size)
    if signature_size == 0 or signature_off + signature_size != marker:
        raise SystemExit("unexpected Samsung boot section layout; refusing to repack")

    ramdisk = empty_newc_gzip()
    if len(kernel) > align(old_kernel_size) or len(ramdisk) > align(old_ramdisk_size):
        raise SystemExit("replacement does not fit the original boot section allocation")

    stock[kernel_off : kernel_off + align(old_kernel_size)] = b"\0" * align(old_kernel_size)
    stock[kernel_off : kernel_off + len(kernel)] = kernel
    stock[ramdisk_off : ramdisk_off + align(old_ramdisk_size)] = b"\0" * align(old_ramdisk_size)
    stock[ramdisk_off : ramdisk_off + len(ramdisk)] = ramdisk
    stock[signature_off : signature_off + signature_size] = b"\0" * signature_size
    struct.pack_into("<II", stock, 8, len(kernel), len(ramdisk))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Samsung's footer follows the padded TAR directly. Keep the checksum
    # line format used by official packages (two spaces before the filename); this is only
    # transport integrity, not an AVB or bootloader signature.
    tar_bytes = io.BytesIO()
    with tarfile.open(fileobj=tar_bytes, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        info = tarfile.TarInfo("boot.img")
        info.size = len(stock)
        info.mode = 0o644
        info.mtime = 0
        tf.addfile(info, io.BytesIO(stock))
    payload = tar_bytes.getvalue()
    if len(payload) % 512:
        raise SystemExit("TAR payload is not 512-byte aligned")
    tar_name = output_path.name.removesuffix(".md5")
    footer = f"{hashlib.md5(payload).hexdigest()}  {tar_name}\n".encode("ascii")
    output_path.write_bytes(payload + footer)
    print(f"Wrote experimental diagnostic package: {output_path} ({output_path.stat().st_size} bytes)")
    print(f"SHA256: {hashlib.sha256(output_path.read_bytes()).hexdigest()}")
    print("Contains shim + empty initramfs only; no XNU. Requires unlocked bootloader; AVB is not re-signed.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stock-boot", required=True, type=Path, help="Raw 64 MiB boot partition from matching SM-A245F firmware")
    ap.add_argument("--kernel", required=True, type=Path, help="A24 shim ARM64 Image")
    ap.add_argument("--output", required=True, type=Path, help="Output Odin .tar.md5")
    args = ap.parse_args()
    build(args.stock_boot, args.kernel, args.output)


if __name__ == "__main__":
    main()
