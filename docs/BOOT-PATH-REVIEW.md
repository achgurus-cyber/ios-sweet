# Boot Path Review & Flashless Execution Audit: Samsung Galaxy A24 (SM-A245F / MT6789)

**Date**: 2026-10-27  
**Target Hardware**: Samsung Galaxy A24 (`SM-A245F`), MediaTek MT6789 (Helio G99)  
**Current Device Mode**: Download Mode (`ODIN MODE`, USB connected)  
**Baseline Git Commit**: `bb03a66` (branch `a24-port`)  
**Audit Objective**: Evaluate the technical feasibility of executing Apple XNU on physical hardware *without flashing, without partition alteration, and without disabling Secure Boot*.

---

## 1. Analysis of `tools/mkbootv4.py` and `a24-xnu-boot.img`

### 1.1 Source Code Inspection (`tools/mkbootv4.py`)
- **Format Generated**: Standard Android Boot Image Header v4 (AOSP layout).
- **Header Structure**:
  - `0x00`: Magic `ANDROID!` (8 bytes)
  - `0x08`: `kernel_size` = 253,952 bytes (matches `a24-shim.Image`)
  - `0x0C`: `ramdisk_size` = 16,591,136 bytes (matches `a24-payload.bin`)
  - `0x10`: `os_version` = 402653592 (encoded AOSP release 12.0.0, patch 2025-08)
  - `0x14`: `header_size` = 1,584 bytes
  - `0x18`: `reserved[4]` (16 bytes, zeroed)
  - `0x28`: `header_version` = 4
  - `0x2C`: `cmdline` (1536 bytes, empty string; parameters passed via `a24-payload.bin`)
  - `0x62C`: `signature_size` = 0
- **Alignment**: Page size 4,096 bytes. Total image size: 16,850,944 bytes (4,114 pages).

### 1.2 Divergence from SM-A245F Boot Chain Requirements
1. **Missing Samsung Footer / Magic**:
   - Factory Samsung boot partitions contain `SEANDROIDENFORCE` magic appended at the boundary of kernel/ramdisk/signature data (offset 20,197,376 in stock).
   - `a24-xnu-boot.img` does not contain `SEANDROIDENFORCE`.
2. **Missing AVB 2.0 Footer**:
   - The stock A24 partition uses a 64 MiB eMMC/UFS layout with an `AVBf` footer at offset 67,104,768 pointing to descriptor metadata.
   - `a24-xnu-boot.img` has size 16.85 MiB and lacks the trailing AVB footer structure.
3. **Container Mismatch for Download Mode**:
   - Samsung Download Mode (`ODIN MODE`) does not accept standalone `.img` files over USB; it requires a POSIX `ustar` archive (`.tar` or `.tar.md5`) where file members match partition identifiers declared in the device PIT (Partition Information Table).

---

## 2. Audit of Project Repository for Temporary / Flashless Boot Methods

| Source / Subproject | Mechanism Used for Testing | Compatibility with SM-A245F |
|---|---|---|
| `ios-sweet` (Redmi Note 10 Pro) | `fastboot boot shim-boot.img` | **INCOMPATIBLE**: Relies on Qualcomm stock unlocked ABL Fastboot bootloader. Samsung does not implement Fastboot. |
| `ios-topaz` (Redmi Note 12 4G) | `fastboot boot shim-boot.img` | **INCOMPATIBLE**: Relies on Qualcomm stock unlocked ABL Fastboot bootloader. Samsung does not implement Fastboot. |
| `ios-a24-port` (Galaxy A24) | `tools/qemu-sweet.py` (Host QEMU) | **HOST ONLY**: Emulates virt-8.2 on PC; provides no physical device tethered bootloader. |
| `ios-a24-port/tools` | None implemented | **ABSENT**: Zero scripts or utilities exist in the repository to perform RAM-boot, tethered boot, or kexec on MT6789. |

**Audit Result**: There is **no documented or implemented flashless/tethered boot mechanism** in the project for Samsung Galaxy A24.

---

## 3. Analysis of Supported Samsung / MediaTek Hardware Interfaces

### 3.1 Samsung Download Mode (Loke Protocol / Odin / Heimdall)
- **Supported Capabilities**:
  - `ODIN_CMD_SESSION_START` / Handshake
  - `PIT_READ` / `PIT_WRITE`
  - `PARTITION_FLASH_WRITE` (Streams TAR members directly to physical UFS/eMMC blocks)
  - `DEVICE_REBOOT`
- **Missing Capabilities**:
  - **No `RAM_BOOT` or `EXEC_IN_DRAM` command exists** in the Samsung Loke protocol specification or implementation. Download Mode was engineered exclusively as an offline factory flashing and recovery interface.
- **Acceptance of `a24-xnu-boot.img`**:
  - If wrapped into an Odin TAR and submitted, Download Mode executes signature verification before flashing or during early boot:
    - Rejects unsigned `boot.img` with `SECURE CHECK FAIL: (boot)`.
    - Rejects AVB-disabled `vbmeta.img` with `SECURE CHECK FAIL: (vbmeta)`.

### 3.2 MediaTek BootROM / Preloader (MT6789 USB VCOM)
- **Status on Production Samsung Devices**:
  - MT6789 BootROM is protected by Samsung SLA (Serial Link Authentication) and DAA (Download Agent Authentication).
  - Preloader communication requires challenge-response cryptographic tokens signed by Samsung's engineering CA.
- **Constraints**:
  - Open, unauthenticated execution in DRAM is disabled by hardware eFuses.
  - Bypassing SLA/DAA requires known MTK BootROM vulnerabilities (e.g. `mtkclient` control-transfer overflow) or hardware testpoint grounding.
  - In accordance with project instructions (*"Не запускай BROM/DA-эксплойты, не используй тестпоинт и не пытайся обходить авторизацию"*), no exploit or testpoint bypass was or will be attempted.

---

## 4. Verification and Forensic Audit of Stock Recovery TARs

### 4.1 Artifact Inventory & Cryptographic Hashes

| Archive | File Size | SHA-256 Checksum | Internal Member | Member Size | Member SHA-256 |
|---|---|---|---|---|---|
| `stock_restore.tar` | 20,203,520 Б | `f5c2cdb4c4de2b5f2828bb335b791504f23e943721aac76df4cab5a77d016f9c` | `boot.img` | 20,197,376 Б | `7926a4a88c0e2d7bc99c29cda2d34f3b8ea8fe01641f164cc65f5e35827eaed5` |
| `stock_repack_pass.tar` | 20,203,520 Б | `f153467311bcf8266471baa699e93f248ee8b3f94381a5f4e90ca5b9f1e1a167` | `boot.img` | 20,193,280 Б | `c28f827f04f41235707dd74d982d1ee5bf326418b904373243c84faef76a2091` |
| `stock_boot.img` (Raw Dump) | 67,108,864 Б | `9ac63e6a612763a3190d7f2d23031fc311eefca22bd91d3e7feef5fa4e222e84` | *(Partition dump)* | 67,108,864 Б | `9ac63e6a612763a3190d7f2d23031fc311eefca22bd91d3e7feef5fa4e222e84` |

### 4.2 Decompiled Firmware Identification
- **Decompressed Linux Kernel**:
  - Banner: `Linux version 5.10.226-android12-9-31117096 (build-user@build-host) (Android (7284624, based on r416183b) clang version 12.0.5) #1 SMP PREEMPT Tue Jul 29 10:18:14 UTC 2025`
  - Decompressed Kernel Size: 41,544,192 bytes (GZIP compressed to 18,737,157 bytes).
- **Target Device String**: `SM-A245F` (Samsung Galaxy A24 LTE).
- **Header OS Version Code**: `402653592` (Android 12/13/14 base with August 2025 security patch level).

### 4.3 Structural Differences Between Archives
- `stock_restore.tar`: Contains `boot.img` of 20,197,376 bytes including the 4,096-byte trailer block.
- `stock_repack_pass.tar`: Contains `boot.img` of 20,193,280 bytes (`signature_size = 0`, truncated by exactly 4,096 bytes).
- `stock_boot.img`: Raw 64 MiB partition containing the full eMMC/UFS layout, `SEANDROIDENFORCE` magic, and AVB 2.0 footer (`AVBf`).

### 4.4 Critical Forensic Evaluation: Are They a "Guarantee of Restoration"?
**NO. They do not constitute a full recovery guarantee.**
1. **Scope Limitation**: Both TAR archives contain **strictly the `boot` partition**.
2. **Missing Firmware Partitions**: Neither archive contains `vbmeta.img`, `vendor_boot.img`, `dtbo.img`, `init_boot.img`, `super.img`, or `preloader`.
3. **Failure Scenarios**: If `vbmeta` or `vendor_boot` is modified or desynchronized, flashing `stock_restore.tar` alone will **not** restore device bootability; Little Kernel will continue halting with AVB verification errors.
4. Full guaranteed restoration requires an official Samsung 4-file factory firmware package (`AP`, `BL`, `CP`, `CSC`) matching the exact binary carrier/revision fused into the device RPMB.

---

## 5. Classification: Facts, Assumptions, and Blockers

### 5.1 Confirmed Technical Facts
1. Samsung Galaxy A24 (`SM-A245F`) uses Samsung Little Kernel (`sboot`) and Download Mode (`ODIN MODE`).
2. Download Mode does not support `fastboot boot` or any in-memory DRAM execution protocol; all operations write to persistent storage.
3. The XNU build (`kernel.development.a24`, `out-a24.adt`, `a24-shim.Image`, `init`) was verified in host QEMU virt-8.2, confirming EL0 userspace execution and demand paging under an emulated virtual environment.
4. The repository contains no implementation of tethered RAM booting for MediaTek MT6789.
5. Flashing unsigned images through Odin is blocked by Samsung Secure Boot (`SECURE CHECK FAIL`).
6. Booting modified partitions via Little Kernel is blocked by AVB 2.0 descriptor checks (`AVB hash mismatch`).

### 5.2 Assumptions & Hypotheses
1. *Assumption*: The MediaTek Little Kernel framebuffer address dynamically assigned to `/chosen/atag,videolfb-fb_base_l` will remain mapped and accessible when control transfers to `a24-shim.Image`.
2. *Assumption*: PSCI `CPU_ON` calls via `smc #0` to MT6789 ARM Trusted Firmware (BL31) will succeed without triggering EL3 permission traps when booted in single-core mode (`cpus=1`).
3. *Hypothesis*: If a custom recovery (such as TWRP) or an engineering kernel with root access is booted, XNU could theoretically be chainloaded via `kexec` from Linux userspace. *(Unverified hypothesis; no kexec wrapper currently exists).*

### 5.3 Concrete Blockers
- **Blocker 1**: No flashless boot protocol exists on SM-A245F without exploiting MTK BootROM.
- **Blocker 2**: Samsung Download Mode rejects writing custom `boot.img` or `vbmeta.img` without an authorized Samsung RSA release signature.
- **Blocker 3**: AVB 2.0 chain of trust in Little Kernel rejects modified boot images against stock `vbmeta` descriptors.

---

## 6. Primary Verdict

**Question**: *Существует ли уже реализованный и совместимый с SM-A245F способ запустить этот XNU на физическом телефоне без записи во flash?*

**Verdict**: **НЕТ.**  
На текущий момент в проекте `ios-a24-port` и в штатной архитектуре Samsung Galaxy A24 (`SM-A245F`) **отсутствует** реализованный, безопасный и совместимый способ временной загрузки ядра XNU без записи во flash-память. Все известные методы временной загрузки в семействе проектов (`fastboot boot`) специфичны для Qualcomm Snapdragon (Xiaomi ABL) и аппаратно не поддерживаются загрузчиком Samsung.
