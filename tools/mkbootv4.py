#!/usr/bin/env python3
"""Pack a kernel Image and ramdisk payload into an Android Boot Image Header v4.

Usage:
  mkbootv4.py --kernel KERNEL --ramdisk RAMDISK --output OUT [--os_version OS_VER] [--cmdline CMDLINE]
"""
import argparse
import struct


def pack_bootv4(kernel_path: str, ramdisk_path: str, out_path: str, os_version: int = 402653592, cmdline: str = ""):
    with open(kernel_path, "rb") as f:
        kdata = f.read()
    with open(ramdisk_path, "rb") as f:
        rdata = f.read()

    ksz = len(kdata)
    rsz = len(rdata)

    hdr = bytearray(4096)
    # Android Boot Header v4:
    # 0x00: magic (8s) 'ANDROID!'
    # 0x08: kernel_size (uint32)
    # 0x0C: ramdisk_size (uint32)
    # 0x10: os_version (uint32)
    # 0x14: header_size (uint32 = 1584)
    # 0x18: reserved[4] (4 * uint32)
    # 0x28: header_version (uint32 = 4)
    # 0x2C: cmdline (1536 bytes)
    # 0x62C: signature_size (uint32 = 0)
    struct.pack_into("<8sIIII4II", hdr, 0, b"ANDROID!", ksz, rsz, os_version, 1584, 0, 0, 0, 0, 4)

    cmd_bytes = cmdline.encode("utf-8")[:1535]
    hdr[44:44 + len(cmd_bytes)] = cmd_bytes
    struct.pack_into("<I", hdr, 44 + 1536, 0)  # signature_size = 0

    k_pad = ((ksz + 4095) // 4096) * 4096 - ksz
    r_pad = ((rsz + 4095) // 4096) * 4096 - rsz

    with open(out_path, "wb") as f:
        f.write(hdr)
        f.write(kdata)
        f.write(b"\0" * k_pad)
        f.write(rdata)
        f.write(b"\0" * r_pad)

    print(f"Created Android Boot v4 image: {out_path} ({4096 + ksz + k_pad + rsz + r_pad} bytes)")


def main():
    parser = argparse.ArgumentParser(description="AOSP Boot Image Header v4 Packager")
    parser.add_argument("--kernel", required=True, help="Path to kernel image (e.g. a24-shim.Image)")
    parser.add_argument("--ramdisk", required=True, help="Path to ramdisk/payload (e.g. a24-payload.bin)")
    parser.add_argument("--output", required=True, help="Output boot.img path")
    parser.add_argument("--os_version", type=int, default=402653592, help="OS version / patch level integer")
    parser.add_argument("--cmdline", default="", help="Kernel command line string")
    args = parser.parse_args()

    pack_bootv4(args.kernel, args.ramdisk, args.output, args.os_version, args.cmdline)


if __name__ == "__main__":
    main()
