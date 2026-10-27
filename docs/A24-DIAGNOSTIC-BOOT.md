# Galaxy A24 diagnostic boot image

The offline builder `tools/mk-a24-diagnostic-odin.py` creates an experimental Odin `boot.tar.md5` using the matching SM-A245F stock boot partition and the A24 shim. The current handoff build is based on One UI 7 `A245FXXS9DYG1` / SEK.

`shim/build-a24.sh` now has separate `A24_MODE=diagnostic` and `A24_MODE=xnu` builds. The diagnostic mode parks before MMU/GIC/PSCI. The XNU mode retains the payload loader; caught shim exceptions park on-screen instead of deliberately resetting. The offline generic Android-v4 XNU wrapper is `out-a24/a24-xnu-boot-current.img` (16,846,848 bytes, SHA-256 `f5d42f98a03cabfe514d5be6824af73d909f32307a88013ff22983f3985e41c5`). It still contains a QEMU-derived A24 memory map and is not a physical-device or Odin-ready image.

The user reports that the previously flashed build displayed Samsung's logo and unlock warning, then went black and powered off before any diagnostic text appeared. The cause is not proven. Source review found that `start.S` assumed EL1 even though project notes identify LK/sboot entry at EL2 as possible. The latest untested candidate normalizes EL2 to EL1 before setting EL1 vectors and entering C. Both diagnostic and XNU shim modes compile with this change. This is a plausible early-boot defect, not a confirmed explanation; framebuffer access and boot-chain acceptance also remain unverified.

The image contains the shim and a valid empty initramfs only. It contains no XNU payload and no Android userspace. The current first-stage diagnostic build is intentionally minimal: if entered, it reports the shim entry, DTB/FDT validity and LK framebuffer properties, then parks. It does not switch the MMU, access GIC registers, or issue PSCI calls. This behavior has only been reasoned from source; it has not been observed on a physical A24.

## Power-button behavior

The official DYG1 vendor FDT identifies the SoC PMIC wrapper at `0x10026000` and an `mediatek,mt6366-keys` node. Its key configuration sets `mediatek,long-press-mode = <2>` and maps the PMIC `home` key to Linux keycode `0x73` (`KEY_VOLUMEUP`). The Linux PMIC-key binding defines mode 2 as the power key plus home key long-press shutdown. This is stock-kernel configuration, not proof that the setting is active when this shim replaces Linux. The shim currently has no MT6366/PWRAP key driver or safe software power-off path; do not claim that a short or long press of Power alone will shut down this image. Implement and validate MT6366/PWRAP access before adding single-key shutdown, rather than guessing PMIC registers.

## Latest offline candidate (not device-tested)

- Path: `out-a24/a24-diagnostic-oneui7-el1handoff-untested.tar.md5` (generated and ignored by git)
- Source boot partition: decoded from the official One UI 7 SEK AP package for `SM-A245F`
- TAR member: `boot.img`, exactly 64 MiB
- Android header: v4; stock Samsung marker and AVB footer retained in place
- Shim: ARM64 Linux Image, 180,224 bytes
- Initramfs: 46-byte gzip containing an empty `newc` archive
- Odin TAR MD5: verified by `samloader verify-md5`
- Package SHA-256: `e51e1564f276f875b75e5a7f8333056121b9a6095699f54604635cf6695da74b`
- TAR length is 512-byte aligned; footer uses the official-style `MD5␠␠filename.tar` layout and was independently re-calculated.
- The A24 first-stage path parks immediately after reporting framebuffer/DTB info; caught exceptions also park instead of invoking reset. This removes the earlier intentional reset and avoids unvalidated MMU/GIC/PSCI operations. The package footer MD5 was independently recalculated and matches. Hardware watchdog, framebuffer validity, bootloader acceptance, and physical entry remain unverified.

## Limits and recovery

- This is not a Samsung-signed boot image. Its AVB descriptor no longer authenticates the replaced kernel and initramfs. It requires an already-unlocked bootloader and may still be rejected by this firmware's boot chain.
- Odin checksum verification proves package transport integrity only. It does not prove that Odin will accept it or that the phone will enter the shim.
- This replaces the active boot partition. Android will not boot from this image; use the official matching One UI 7 AP package to restore stock boot if needed. Keep the full official BL/AP/CP/CSC package available on the PC.
- Do not flash this while the bootloader is locked. Do not use PIT, repartition, NAND erase, or unrelated partitions.
- No physical A24 boot has been attempted or confirmed. Treat this as a controlled diagnostic experiment, not as a ready/known-good device boot image.
