#!/bin/bash
# Compile the A24-specific experimental shim core only.
# This deliberately does not package an Odin/AP tar or write to a device.
set -euo pipefail
cd "$(dirname "$0")"

if command -v aarch64-linux-gnu-gcc >/dev/null 2>&1; then
	CC=${CC:-aarch64-linux-gnu-gcc}
	OBJCOPY=${OBJCOPY:-aarch64-linux-gnu-objcopy}
	READELF=${READELF:-aarch64-linux-gnu-readelf}
	NM=${NM:-aarch64-linux-gnu-nm}
	# This is a freestanding image with its own _start; do not let the GCC
	# driver inject hosted crt objects or libc into the bare-metal link.
	LD_CMD=("$CC" -nostdlib -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N)
elif command -v /usr/lib/llvm-18/bin/clang >/dev/null 2>&1; then
	CC=${CC:-"/usr/lib/llvm-18/bin/clang --target=aarch64-linux-gnu"}
	OBJCOPY=${OBJCOPY:-/usr/lib/llvm-18/bin/llvm-objcopy}
	READELF=${READELF:-/usr/lib/llvm-18/bin/llvm-readelf}
	NM=${NM:-/usr/lib/llvm-18/bin/llvm-nm}
	LD_CMD=(/usr/lib/llvm-18/bin/ld.lld -T shim.ld --build-id=none -N)
else
	echo "error: neither aarch64-linux-gnu-gcc nor llvm-18 clang found" >&2
	exit 1
fi

CFLAGS="-DPLATFORM_A24 -O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
mkdir -p out-a24

for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c; do
	$CC $CFLAGS -c "$f" -o "out-a24/${f%.*}.o"
done

abs=$($READELF -r out-a24/shim.o out-a24/console.o out-a24/mmu.o out-a24/fdt.o out-a24/loader.o out-a24/ufs.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }

"${LD_CMD[@]}" \
	out-a24/start.o out-a24/shim.o out-a24/console.o out-a24/mmu.o out-a24/fdt.o out-a24/loader.o out-a24/ufs.o \
	-o out-a24/a24-shim.elf

tmp_img="/tmp/a24-shim.$$.Image"
$OBJCOPY -O binary out-a24/a24-shim.elf "$tmp_img"
cp "$tmp_img" out-a24/a24-shim.Image
rm -f "$tmp_img"

hex=$($NM out-a24/a24-shim.elf | awk '$3=="_end"{print $1}')
size=$((16#$hex))
truncate -s "$size" out-a24/a24-shim.Image

echo "Built experimental A24 shim core (not an Odin image):"
ls -l out-a24/a24-shim.elf out-a24/a24-shim.Image
