#!/bin/bash
# Create an offline Android boot header v4 wrapper for the A24 shim.
# Requires the AOSP platform/system/tools/mkbootimg mkbootimg.py path in
# MKBOOTIMG_PY. This is not an Odin/AP archive and does not flash anything.
set -euo pipefail
cd "$(dirname "$0")"

: "${MKBOOTIMG_PY:?Set MKBOOTIMG_PY to AOSP mkbootimg.py}"
test -f "$MKBOOTIMG_PY"
test -f out-a24/a24-shim.Image

mkdir -p out-a24/empty-ramdisk
(cd out-a24/empty-ramdisk && find . -print0 | cpio --null -o -H newc --quiet | gzip -9 > ../empty-ramdisk.cpio.gz)

# Metadata is copied from the read-only captured A24 boot image. Samsung's
# vendor_boot remains a separate required partition and is not modified here.
python3 "$MKBOOTIMG_PY" \
	--header_version 4 \
	--os_version 12.0.0 \
	--os_patch_level 2025-08 \
	--kernel out-a24/a24-shim.Image \
	--ramdisk out-a24/empty-ramdisk.cpio.gz \
	--cmdline "" \
	--output out-a24/a24-diagnostic-boot.img

echo "Offline diagnostic boot image created; do not flash without a separately reviewed recovery plan and explicit user confirmation."
ls -l out-a24/a24-diagnostic-boot.img
