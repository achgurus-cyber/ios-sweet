# Galaxy A24 diagnostic boot image

The offline builder `tools/mk-a24-diagnostic-odin.py` creates an experimental Odin `boot.tar.md5` using the matching SM-A245F stock boot partition and the A24 shim. The current handoff build is based on One UI 7 `A245FXXS9DYG1` / SEK.

The image contains the shim and a valid empty initramfs only. It contains no XNU payload and no Android userspace. If the shim is entered, it should print its diagnostic screen, report that no XNU initrd exists, then continue through the existing MMU/GIC/PSCI diagnostic path. This behavior has only been reasoned from source; it has not been observed on a physical A24.

## Current artifact

- Path: `out-a24/a24-diagnostic-oneui7-boot.tar.md5` (generated and ignored by git)
- Source boot partition: decoded from the official One UI 7 SEK AP package for `SM-A245F`
- TAR member: `boot.img`, exactly 64 MiB
- Android header: v4; stock Samsung marker and AVB footer retained in place
- Shim: ARM64 Linux Image, 249,856 bytes
- Initramfs: 46-byte gzip containing an empty `newc` archive
- Odin TAR MD5: verified by `samloader verify-md5`
- Package SHA-256: `73f684d2d253a3db688dd5361aa6e60b79071a5a9da8b7080f30e2918344932b`
- TAR length is 512-byte aligned; footer uses the official-style `MD5␠␠filename.tar` layout and was independently re-calculated.
- The A24 diagnostic path parks after its checks and on a caught exception instead of calling PSCI reset. This removes the earlier build's intentional 40-second reboot loop; hardware watchdog or an earlier boot-chain reset remains unverified.

## Limits and recovery

- This is not a Samsung-signed boot image. Its AVB descriptor no longer authenticates the replaced kernel and initramfs. It requires an already-unlocked bootloader and may still be rejected by this firmware's boot chain.
- Odin checksum verification proves package transport integrity only. It does not prove that Odin will accept it or that the phone will enter the shim.
- This replaces the active boot partition. Android will not boot from this image; use the official matching One UI 7 AP package to restore stock boot if needed. Keep the full official BL/AP/CP/CSC package available on the PC.
- Do not flash this while the bootloader is locked. Do not use PIT, repartition, NAND erase, or unrelated partitions.
- No physical A24 boot has been attempted or confirmed. Treat this as a controlled diagnostic experiment, not as a ready/known-good device boot image.
