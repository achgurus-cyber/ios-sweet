# A24 Odin candidate: format verified, not flashable

`tools/mk-a24-xnu-odin.py` packages the current Android-v4 XNU wrapper into a
single-member Odin TAR based on the matching SM-A245F EYL2 stock `boot.img`.
It is an offline format/package experiment only.

Latest generated artifact (outside git):

- `D:\CodexSamsungRootBuild\A24-XNU-Odin-Candidate-20261027\DO-NOT-FLASH-a24-xnu-a245f-eyl2-unvalidated.tar.md5`
- SHA-256: `fc2d00d1bafcc211d71c7bce88395b60dc0fdc092d83d6683f1ef6e57683f6fb`
- TAR member: one `boot.img`, 64 MiB, Android boot header v4.
- Kernel: 249,856-byte A24 XNU shim.
- Ramdisk bytes: 16,591,136-byte `SWEETXNU` payload.
- The Odin TAR footer MD5, member size, Android header, Samsung marker, AVB footer and vbmeta bytes were checked offline.

**Do not flash this file.** The checks above establish container integrity, not
bootability or device compatibility. The boot partition and its AVB descriptor
do not match after replacement; the stock vbmeta/footer are preserved, so the
boot digest is stale. The embedded XNU physical RAM range was generated before
the live A24 map and reserved-memory ranges were established. The last saved
read-only diagnostics also reported a locked bootloader. The payload contains
only the test PID 1, not iOS userland or SpringBoard, and no verified MediaTek
UFS root driver is available to mount a persistent iOS system.

Specifically, this payload advertises only `0x100000000..0x191c80000`
(`dram-size=0x91c80000`). The previously observed live Linux FDT reported
`0x40000000..0x1c0000000` plus multiple fixed reservations, and the exact LK
handoff map/reservations were not captured in the current workspace. These
ranges must not be treated as interchangeable.

Required before making a bootable Odin package: acquire the current live FDT
and reservations, update and validate the physical XNU memory map/load range,
validate a MediaTek UFS root path, prepare a consistent AVB policy for the
unlocked firmware, and observe successful shim/XNU entry on the actual A24.
The full matching stock EYL2 Samsung package remains the recovery path. No
partition has been written by this tool.
