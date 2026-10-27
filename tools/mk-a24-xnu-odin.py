#!/usr/bin/env python3
"""Package the project's current A24 XNU boot-v4 wrapper into an Odin TAR.

This is an experimental first-boot image, not a complete iOS installation.
It preserves the stock AVB footer/vbmeta bytes, so the AVB digest is stale and
the result is not suitable for flashing unless the exact device boot policy is
known to accept the modified boot partition. This tool never talks to a phone.
"""
import argparse
import hashlib
import io
import struct
import tarfile
from pathlib import Path

PAGE = 4096
PARTITION_SIZE = 64 * 1024 * 1024
SEANDROID = b"SEANDROIDENFORCE"
AVB_FOOTER = b"AVBf"


def align(value: int, boundary: int = PAGE) -> int:
    return (value + boundary - 1) // boundary * boundary


def make_odin_image(stock_path: Path, wrapper_path: Path, output_path: Path) -> None:
    stock = bytearray(stock_path.read_bytes())
    wrapper = wrapper_path.read_bytes()
    if len(stock) != PARTITION_SIZE or stock[:8] != b"ANDROID!":
        raise SystemExit("stock input must be a raw 64 MiB Android boot partition")
    if len(wrapper) < PAGE or wrapper[:8] != b"ANDROID!":
        raise SystemExit("wrapper input is not an Android boot image")

    stock_version = struct.unpack_from("<I", stock, 40)[0]
    wrapper_version = struct.unpack_from("<I", wrapper, 40)[0]
    if stock_version != 4 or wrapper_version != 4:
        raise SystemExit("both stock and XNU wrapper must use Android boot header v4")

    stock_footer_at = stock.rfind(AVB_FOOTER)
    if stock_footer_at != PARTITION_SIZE - 64:
        raise SystemExit("AVB footer is not at the end of the stock partition")
    footer = stock[stock_footer_at:]
    vbmeta_offset, vbmeta_size = struct.unpack_from(">QQ", footer, 20)
    if vbmeta_offset <= PAGE or vbmeta_size == 0 or vbmeta_offset + vbmeta_size > stock_footer_at:
        raise SystemExit("stock AVB footer has an invalid vbmeta range")
    if stock[vbmeta_offset:vbmeta_offset + 4] != b"AVB0":
        raise SystemExit("AVB footer does not point to an AVB0 vbmeta image")

    stock_marker_at = stock.find(SEANDROID)
    if stock_marker_at < PAGE or stock_marker_at >= vbmeta_offset:
        raise SystemExit("stock Samsung marker is missing or outside the boot data area")

    kernel_size, ramdisk_size = struct.unpack_from("<II", wrapper, 8)
    wrapper_header_size = struct.unpack_from("<I", wrapper, 20)[0]
    signature_size = struct.unpack_from("<I", wrapper, 1580)[0]
    if wrapper_header_size != 1584 or signature_size != 0:
        raise SystemExit("unexpected XNU wrapper header layout")
    kernel_off = PAGE
    ramdisk_off = PAGE + align(kernel_size)
    image_end = ramdisk_off + align(ramdisk_size)
    marker_end = image_end + len(SEANDROID)
    if marker_end > vbmeta_offset:
        raise SystemExit("XNU shim + payload would overlap the stock vbmeta image")
    if ramdisk_off + ramdisk_size > len(wrapper):
        raise SystemExit("XNU wrapper is truncated")

    kernel = wrapper[kernel_off:kernel_off + kernel_size]
    ramdisk = wrapper[ramdisk_off:ramdisk_off + ramdisk_size]
    if not kernel.startswith(b"\x00\x02\x00\x14"):
        raise SystemExit("wrapper kernel lacks the expected ARM64 Image header")
    if ramdisk[:8] != b"SWEETXNU":
        raise SystemExit("wrapper ramdisk is not the expected SWEETXNU payload")

    # Retain the matching Samsung header metadata. Rebuild only its kernel and
    # ramdisk sections, leaving the stock AVB block/footer in their exact slots.
    boot = bytearray(stock)
    boot[PAGE:vbmeta_offset] = bytes(vbmeta_offset - PAGE)
    boot[kernel_off:kernel_off + len(kernel)] = kernel
    boot[ramdisk_off:ramdisk_off + len(ramdisk)] = ramdisk
    boot[image_end:image_end + len(SEANDROID)] = SEANDROID
    struct.pack_into("<II", boot, 8, kernel_size, ramdisk_size)
    struct.pack_into("<I", boot, 1580, 0)
    if boot[stock_footer_at:] != footer or boot[vbmeta_offset:vbmeta_offset + vbmeta_size] != stock[vbmeta_offset:vbmeta_offset + vbmeta_size]:
        raise SystemExit("internal error: stock AVB footer/vbmeta changed")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        item = tarfile.TarInfo("boot.img")
        item.size = len(boot)
        item.mode = 0o644
        item.mtime = 0
        archive.addfile(item, io.BytesIO(boot))
    tar_bytes = tar_buffer.getvalue()
    if len(tar_bytes) % 512:
        raise SystemExit("Odin TAR body is not 512-byte aligned")
    embedded_name = output_path.name.removesuffix(".md5")
    footer_line = f"{hashlib.md5(tar_bytes).hexdigest()}  {embedded_name}\n".encode("ascii")
    output_path.write_bytes(tar_bytes + footer_line)

    print(f"Odin package: {output_path} ({output_path.stat().st_size} bytes)")
    print(f"SHA256: {hashlib.sha256(output_path.read_bytes()).hexdigest()}")
    print(f"boot.img: 64 MiB; kernel={kernel_size} bytes; SWEETXNU payload={ramdisk_size} bytes")
    print(f"AVB vbmeta preserved at {vbmeta_offset:#x}+{vbmeta_size:#x}; its boot digest is stale")
    print("WARNING: embedded A24 RAM map is not verified against current live FDT/reservations.")
    print("Offline format candidate only; no complete iOS root filesystem; DO NOT FLASH.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-boot", type=Path, required=True, help="matching raw Samsung boot.img")
    parser.add_argument("--xnu-wrapper", type=Path, required=True, help="Android-v4 wrapper containing A24 XNU shim and payload")
    parser.add_argument("--output", type=Path, required=True, help="output Odin .tar.md5")
    args = parser.parse_args()
    make_odin_image(args.stock_boot, args.xnu_wrapper, args.output)


if __name__ == "__main__":
    main()
