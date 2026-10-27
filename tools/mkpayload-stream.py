#!/usr/bin/env python3
"""Stream a SWEETXNU payload with a large RAM disk without loading it into RAM."""
import argparse
import errno
import os
import struct
import sys

import mkpayload as mk

PAGE = 0x4000
ALIGN = 16


def align(value, boundary):
    return (value + boundary - 1) & ~(boundary - 1)


def data_ranges(fd, size):
    """Yield source extents; fall back to bounded reads when sparse seeks fail."""
    if hasattr(os, "SEEK_DATA") and hasattr(os, "SEEK_HOLE"):
        pos = 0
        try:
            while pos < size:
                try:
                    data = os.lseek(fd, pos, os.SEEK_DATA)
                except OSError as exc:
                    if exc.errno == errno.ENXIO:
                        return
                    raise
                if data >= size:
                    return
                hole = min(os.lseek(fd, data, os.SEEK_HOLE), size)
                yield data, hole
                pos = hole
            return
        except OSError:
            pass
    yield 0, size


def copy_sparse(source_path, output, output_offset, size):
    fd = os.open(source_path, os.O_RDONLY)
    try:
        for start, end in data_ranges(fd, size):
            pos = start
            while pos < end:
                count = min(8 * 1024 * 1024, end - pos)
                if hasattr(os, "pread"):
                    chunk = os.pread(fd, count, pos)
                else:
                    os.lseek(fd, pos, os.SEEK_SET)
                    chunk = os.read(fd, count)
                if len(chunk) != count:
                    raise IOError(f"unexpected EOF in RAM disk at {pos}")
                output.seek(output_offset + pos)
                output.write(chunk)
                pos += count
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kernel")
    parser.add_argument("adt")
    parser.add_argument("out")
    parser.add_argument("--cmdline", default="debug=0xc serial=3 cpus=1 keepsyms=1")
    parser.add_argument("--ramdisk", required=True)
    args = parser.parse_args()

    kernel = bytearray(open(args.kernel, "rb").read())
    macho = mk.parse_macho(kernel)
    fixups = mk.apply_chained_fixups(kernel, macho)
    segments = [seg for seg in macho["segs"] if seg["vmsize"]]
    text = macho["segs"][0]
    if text["name"] != "__TEXT" or text["fileoff"] != 0:
        raise ValueError("unexpected XNU Mach-O layout")
    virt_base = text["vmaddr"] & ~(0x2000000 - 1)
    kernel_end = align(max(seg["vmaddr"] + seg["vmsize"] for seg in segments), PAGE)
    adt_blob = open(args.adt, "rb").read()
    phys_base, mem_size = mk.adt_dram(adt_blob)

    pieces = []
    for seg in segments:
        data = bytes(kernel[seg["fileoff"]:seg["fileoff"] + seg["filesize"]])
        pieces.append((seg["vmaddr"], seg["vmsize"], data, None))

    rd_file_size = os.path.getsize(args.ramdisk)
    rd_size = align(rd_file_size, PAGE)
    rd_va = kernel_end
    kernel_end = rd_va + rd_size
    rd_pa = rd_va - virt_base + phys_base
    pieces.append((rd_va, rd_size, None, args.ramdisk))
    adt_blob = mk.add_ramdisk_to_adt(adt_blob, rd_pa, rd_size)

    header_size = mk.SEG_TABLE + 32 * len(pieces)
    cursor = header_size
    table = []
    for vmaddr, vmsize, data, path in pieces:
        file_size = len(data) if data is not None else rd_file_size
        table.append((vmaddr, vmsize, cursor, file_size))
        cursor = align(cursor + file_size, ALIGN)
    adt_offset = cursor
    output_size = align(adt_offset + len(adt_blob), ALIGN)

    header = bytearray(header_size)
    struct.pack_into("<8sII", header, 0, b"SWEETXNU", 1, len(pieces))
    struct.pack_into("<7Q", header, 0x10, virt_base, macho["entry"], adt_offset,
                     len(adt_blob), kernel_end, phys_base, mem_size)
    cmdline = args.cmdline.encode()[:mk.BOOT_LINE_LENGTH - 1]
    header[mk.CMDLINE:mk.CMDLINE + len(cmdline)] = cmdline
    for index, entry in enumerate(table):
        struct.pack_into("<4Q", header, mk.SEG_TABLE + 32 * index, *entry)

    with open(args.out, "w+b") as output:
        output.write(header)
        for (_, _, data, path), (_, _, offset, file_size) in zip(pieces, table):
            if data is not None:
                output.seek(offset)
                output.write(data)
            else:
                copy_sparse(path, output, offset, file_size)
        output.seek(adt_offset)
        output.write(adt_blob)
        output.truncate(output_size)

    print(f"kernel={args.kernel} segments={len(pieces) - 1} chained_fixups={fixups}")
    print(f"ramdisk={hex(rd_pa)} size={hex(rd_size)} source_bytes={rd_file_size}")
    print(f"output={args.out} bytes={output_size} ram={hex(phys_base)}+{hex(mem_size)}")


if __name__ == "__main__":
    main()
