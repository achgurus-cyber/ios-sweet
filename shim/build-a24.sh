#!/bin/bash
# Compile the A24-specific experimental shim core only.
# This deliberately does not package an Odin/AP tar or write to a device.
set -euo pipefail
cd "$(dirname "$0")"

CC=${CC:-aarch64-linux-gnu-gcc}
OBJCOPY=${OBJCOPY:-aarch64-linux-gnu-objcopy}
READELF=${READELF:-aarch64-linux-gnu-readelf}
CFLAGS="-DPLATFORM_A24 -O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
mkdir -p out-a24

for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c; do
	$CC $CFLAGS -c "$f" -o "out-a24/${f%.*}.o"
done

abs=$($READELF -r out-a24/shim.o out-a24/console.o out-a24/mmu.o out-a24/fdt.o out-a24/loader.o out-a24/ufs.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }

$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
	out-a24/start.o out-a24/shim.o out-a24/console.o out-a24/mmu.o out-a24/fdt.o out-a24/loader.o out-a24/ufs.o \
	-o out-a24/a24-shim.elf
$OBJCOPY -O binary out-a24/a24-shim.elf out-a24/a24-shim.Image
hex=$(aarch64-linux-gnu-nm out-a24/a24-shim.elf | awk '$3=="_end"{print $1}')
size=$((16#$hex))
truncate -s "$size" out-a24/a24-shim.Image

echo "Built experimental A24 shim core (not an Odin image):"
ls -l out-a24/a24-shim.elf out-a24/a24-shim.Image
