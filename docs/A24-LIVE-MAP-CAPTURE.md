# Galaxy A24 live memory-map capture

`tools/collect-a24-live-map.py` captures read-only boot metadata from one
authorized ADB-connected Galaxy A24 (`SM-A245F`). It records selected build
and boot properties, then attempts to save `/sys/firmware/fdt` and
`/proc/iomem`. Captures go to a timestamped directory under `%TEMP%` by
default, outside this repository.

Run it after Android has booted and USB debugging is authorized:

```powershell
python tools/collect-a24-live-map.py
```

To choose a destination:

```powershell
python tools/collect-a24-live-map.py --output D:\A24-live-map
```

The script refuses to run unless exactly one online ADB device reports model
`SM-A245F`. It does not reboot, use root, or write to the phone. Android may
deny access to either kernel interface; in that case `capture.txt` records the
failure. Do not treat `/proc/iomem` alone as a bootloader handoff map. The
captured FDT and reserved-memory nodes must be decoded and checked against the
actual payload placement before using any RAM region for XNU.

The capture can contain device-specific details. Keep it out of git and share
it only if needed for debugging.
