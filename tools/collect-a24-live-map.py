#!/usr/bin/env python3
"""Read-only capture of Galaxy A24 boot memory metadata over ADB.

The output is device-specific diagnostic data and should stay outside git.
No root, reboot, or device write is requested by this script.
"""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def run(adb, *args):
    return subprocess.run([adb, *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb", help="ADB executable (default: PATH)")
    parser.add_argument("--output", help="output directory (default: system temp)")
    args = parser.parse_args()

    adb = shutil.which(args.adb) if os.path.basename(args.adb) == args.adb else args.adb
    if not adb or not Path(adb).is_file():
        sys.exit("ADB executable not found; install Android platform-tools or pass --adb")

    devices = run(adb, "devices")
    if devices.returncode:
        sys.exit(devices.stderr.decode(errors="replace").strip() or "adb devices failed")
    online = [line.split()[0] for line in devices.stdout.decode(errors="replace").splitlines()[1:]
              if len(line.split()) >= 2 and line.split()[1] == "device"]
    if len(online) != 1:
        sys.exit(f"Expected exactly one authorized online ADB device; found {len(online)}")

    model = run(adb, "-s", online[0], "shell", "getprop", "ro.product.model")
    model_text = model.stdout.decode(errors="replace").strip()
    if model.returncode or model_text != "SM-A245F":
        sys.exit(f"Refusing capture: expected SM-A245F, got {model_text or '(unknown)'}")

    if args.output:
        out = Path(args.output).expanduser().resolve()
    else:
        out = Path(os.getenv("TEMP", ".")) / time.strftime("a24-live-map-%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=False)

    metadata = []
    metadata.append("model=" + model_text)
    for prop in ("ro.build.fingerprint", "ro.build.version.release",
                 "ro.bootloader", "ro.boot.vbmeta.device_state",
                 "ro.boot.flash.locked", "ro.boot.verifiedbootstate"):
        result = run(adb, "-s", online[0], "shell", "getprop", prop)
        metadata.append(f"{prop}=" + result.stdout.decode(errors="replace").strip())

    for name, remote in (("live-fdt.dtb", "/sys/firmware/fdt"),
                         ("proc-iomem.txt", "/proc/iomem")):
        result = run(adb, "-s", online[0], "exec-out", "cat", remote)
        if result.returncode or not result.stdout:
            reason = result.stderr.decode(errors="replace").strip() or "unavailable or denied"
            metadata.append(f"{remote}=NOT_CAPTURED ({reason})")
            continue
        target = out / name
        target.write_bytes(result.stdout)
        metadata.append(f"{remote}=captured bytes={len(result.stdout)} sha256={hashlib.sha256(result.stdout).hexdigest()}")
        if name == "live-fdt.dtb" and not result.stdout.startswith(bytes.fromhex("d00dfeed")):
            metadata.append("WARNING: captured FDT file does not start with the standard FDT magic")

    (out / "capture.txt").write_text("\n".join(metadata) + "\n", encoding="utf-8")
    print(f"Read-only capture saved to: {out}")
    print("No device serial is written. Inspect capture.txt; unavailable files may need elevated read access.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
