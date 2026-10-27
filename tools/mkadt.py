#!/usr/bin/env python3
"""Build the minimal Apple Device Tree used by the experimental XNU ports.

Only what the early boot path actually reads (see NOTES.md). A24 mode requires
RAM bounds collected from the live device; it will not reuse Sweet addresses.
"""
import hashlib, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402

# Kernel-managed RAM: above every Qualcomm XPU carve-out (see NOTES.md)
PHYS_BASE = 0xb0000000
MEM_SIZE = 0x4d000000
# Panic log buffer, carved from the TOP of the dram range and exposed to XNU as
# /pram + /chosen/embedded-panic-log-size. Without it, pe_init.c's
# check_for_panic_log() leaves gPanicBase == 0, debug_log_init() bails out twice
# and the kernel hangs right after "kdp_core zlib memory" — reproduced on QEMU
# and independently on ios-fajita.
PANIC_LOG_SIZE = 0x100000
# --highmem (phone only): the whole upper DDR bank. The live FDT memory node is
# <0x80000000 2G>, <0x1_00000000 0xfcc00000>; every fixed reserved-memory
# carve-out is in the low bank and the dynamic pools are limited below 4G.
HIGH_PHYS_BASE = 0x100000000
HIGH_MEM_SIZE = 0xfcc00000
# /arm-io children are relative to this; it must not be 0 (serial_init bails)
SOC_BASE = 0x01000000

GICD, GICD_SIZE = 0x17a00000, 0x10000
GICR, GICR_SIZE = 0x17a60000, 0x100000
FB, FB_SIZE = 0x9c000000, 0x1700000
SWEET_ECID = 0x5357454554000001  # 'SWEET' + 1, synthetic
FB_W, FB_H, FB_STRIDE = 1080, 2400, 1080 * 4
# Internal UFS host (ufshc@1d84000 "ufs_mem"); QEMU virt has none
UFS, UFS_SIZE = 0x01d84000, 0x3000
TIMEBASE = 19200000
VTIMER_INTID = 19
# QEMU virt (-M virt,gic-version=3 -cpu cortex-a76): GICD/GICR and the generic timer's CNTFRQ
QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE = 0x08000000, 0x080a0000, 62500000
QEMU_VTIMER_INTID = 27

# Galaxy A24 values decoded from its live FDT. RAM banks and reserved ranges
# are deliberately not guessed here; a caller must provide a vetted map.
A24_GICD, A24_GICD_SIZE = 0x0c000000, 0x40000
A24_GICR, A24_GICR_SIZE = 0x0c040000, 0x200000
A24_FB, A24_FB_SIZE = 0xfe144000, 0x1ebb000
A24_FB_W, A24_FB_H = 1080, 2340
A24_FB_STRIDE = A24_FB_W * 4  # provisional until boot framebuffer stride is read
A24_UFS, A24_UFS_SIZE = 0x11270000, 0x2300
A24_TIMEBASE = 13000000  # MT6789 armv8-timer clock-frequency is 13.0 MHz (0xc65d40)

BOOT_MANIFEST_HASH = hashlib.sha384(b'sweet boot manifest').digest()

# The iOS userland is the iPhone X (iPhone10,3 / D22AP) IPSW. MobileGestalt
# derives product type, device class, home-button-less UI, artwork etc. from
# the root identity and /product of the real D22AP device tree. That tree is
# an Apple artifact (kept out of git): extract it from the IPSW with
#   tools/remotezip.py URL DeviceTree.d22ap.im4p DIR
#   ipsw img4 im4p extract DIR/Firmware/all_flash/DeviceTree.d22ap.im4p -o d22ap.adt
D22AP_ADT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../research/ipsw-x/d22ap.adt')


def d22ap_product(path=D22AP_ADT):
    """/product properties of the real D22AP tree, without the syscfg
    placeholders iBoot would fill in (flag bit set) and the node bookkeeping."""
    if not os.path.exists(path):
        print(f'warning: {path} missing, no /product node', file=sys.stderr)
        return None
    root, _ = adt.parse(open(path, 'rb').read())
    for c in root.children:
        if dict((k, v) for k, f, v in c.props).get('name') == b'product\0':
            return [(k, v) for k, f, v in c.props if not f and k not in ('name', 'AAPL,phandle')]
    raise SystemExit(f'{path}: no /product node')

u32 = lambda *v: struct.pack('<%dI' % len(v), *v)
u64 = lambda *v: struct.pack('<%dQ' % len(v), *v)
cstr = lambda s: s.encode() + b'\0'


def node(name, props=(), children=()):
    n = adt.Node()
    n.props = [('name', 0, cstr(name))] + [(k, 0, v) for k, v in props]
    n.children = list(children)
    return n


def build(seed=None, qemu=False, highmem=False, a24=False, ram_ranges=None, smp=None):
    """Build a target ADT. A24 requires vetted RAM ranges (base, size) tuples."""
    if a24 and not ram_ranges:
        raise SystemExit('A24 requires one or more vetted --ram-range BASE:SIZE values')
    if a24 and highmem:
        raise SystemExit('--highmem is Sweet-only; provide the A24 RAM range explicitly')
    if a24:
        ram_ranges = sorted((int(base), int(size)) for base, size in ram_ranges)
        if any(base < 0 or size <= 0 or base + size > (1 << 36)
               for base, size in ram_ranges):
            raise SystemExit('A24 RAM ranges must be positive and within the configured 36-bit PA space')
        if any(a + size_a > b for (a, size_a), (b, _) in zip(ram_ranges, ram_ranges[1:])):
            raise SystemExit('A24 RAM ranges must not overlap')
        phys_base, mem_size = ram_ranges[0]
        if len(ram_ranges) != 1:
            raise SystemExit('A24 loader currently supports one contiguous kernel region only')
    else:
        phys_base, mem_size = (HIGH_PHYS_BASE, HIGH_MEM_SIZE) if highmem else (PHYS_BASE, MEM_SIZE)
    # Carve the panic log off the top so the kernel never allocates over it.
    panic_base = phys_base + mem_size - PANIC_LOG_SIZE
    mem_size -= PANIC_LOG_SIZE
    if a24 and not qemu:
        gicd, gicr, timebase = A24_GICD, A24_GICR, A24_TIMEBASE
        fb, fb_size, fb_w, fb_h, fb_stride = A24_FB, A24_FB_SIZE, A24_FB_W, A24_FB_H, A24_FB_STRIDE
        ufs_base, ufs_size = A24_UFS, A24_UFS_SIZE
    elif qemu:
        gicd, gicr, timebase = QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE
        fb, fb_size, fb_w, fb_h, fb_stride = FB, FB_SIZE, FB_W, FB_H, FB_STRIDE
        ufs_base, ufs_size = (UFS, UFS_SIZE) if not a24 else (A24_UFS, A24_UFS_SIZE)
    else:
        gicd, gicr, timebase = GICD, GICR, TIMEBASE
        fb, fb_size, fb_w, fb_h, fb_stride = FB, FB_SIZE, FB_W, FB_H, FB_STRIDE
        ufs_base, ufs_size = UFS, UFS_SIZE
    seed = seed if seed is not None else os.urandom(64)
    phandle = iter(range(1, 1000))
    ph = lambda: ('AAPL,phandle', u32(next(phandle)))

    chosen = node('chosen', [
        ph(),
        ('dram-base', u64(phys_base)),
        ('dram-size', u64(mem_size)),
        ('random-seed', seed),
        ('debug-enabled', u32(1)),
        ('embedded-panic-log-size', u32(PANIC_LOG_SIZE)),
        ('firmware-version', cstr('sweet-shim')),
        ('system-firmware-version', cstr('sweet-shim')),
        # iBoot's SHA-384 of the boot manifest; /sbin/mount -P 1 exits unless
        # it exists (bind mounts /private/preboot/<hex>/usr/standalone/firmware,
        # tolerating a missing directory). Fixed stand-in value.
        ('boot-manifest-hash', BOOT_MANIFEST_HASH),
        # libimg4 (cryptexd) aborts "failed to get crypto algorithm" without
        # it; real A11+ device trees say sha2-384.
        ('crypto-hash-method', cstr('sha2-384')),
        # MobileGestalt's screen class: display-scale (u32, default 0) comes
        # from /chosen, the pixel size from IOMobileFramebuffer. Scale 0 makes
        # SpringBoard's FBSDisplayMode "infxinf@0x" invalid. 1080x2400 @3x =
        # 360x800 points (like iPhone X class devices).
        ('display-scale', u32(3)),
        # XNU derives IOPlatformUUID (gethostuuid) from these on arm; without
        # them CFPreferences cannot use kCFPreferencesCurrentHost (no ByHost
        # files), so e.g. DataMigration never records LastSystemVersion and
        # migrates on every boot. Synthetic ECID (not the phone's); chip-id
        # of the A11 that the iPhone X userland expects.
        ('unique-chip-id', struct.pack('<Q', SWEET_ECID)),
        ('chip-id', u32(0x8015)),
        # Security status as on a dev-fused, undemoted board (tuple 0,0,1,1):
        # MobileGestalt reads these from /chosen, and mobileactivationd's
        # DeviceType then takes its native "Hactivation" branch (state
        # Activated without an activation record; no SEP, no baseband here).
        ('certificate-production-status', u32(0)),
        ('effective-production-status-ap', u32(0)),
        ('certificate-security-mode', u32(1)),
        ('effective-security-mode-sep', u32(1)),
    ], [node('memory-map', [ph()]),
        # Local boot policy (kern_csr.c): SIP relaxed like `csrutil disable`
        # (lp-sip0: untrusted kexts, unrestricted FS, task_for_pid, kernel
        # debugger, dtrace, nvram), lp-sip1: unauthenticated (unsealed) root.
        # The iOS shared cache is in no trust cache, so dyld can only map it
        # with CSR_ALLOW_UNRESTRICTED_FS (vm_unix.c shared region checks).
        node('asmb', [ph(), ('lp-sip0', u64(0x6f)), ('lp-sip1', u32(1))])])

    # SWEET/A24 SMP: all eight cores in physical-core order (0-5 Cortex-A55,
    # 6-7 Cortex-A76), one scheduler cluster for now. The kernel defaults to
    # one CPU and uses cpus=N to select an initial prefix (N <= 8).
    # QEMU defaults to single-CPU tree unless --smp is passed.
    num_cpus = smp if smp is not None else (1 if qemu else 8)
    cpu_nodes = []
    for core in range(num_cpus):
        cpu_nodes.append(node(f'cpu{core}', [
            ph(),
            ('device_type', cstr('cpu')),
            ('compatible', (cstr('mediatek,mt6789-cpu') + cstr('ARM,v8')
                            if a24 else cstr('qcom,kryo470') + cstr('ARM,v8'))),
            # Both A24 and Sweet number cores in MPIDR Aff1 (0x000..0x700).
            ('reg', u32(core << 8)),
            ('cpu-id', u32(core)),   # descriptive: XNU assigns IDs by DT order
            ('cluster-id', u32(0)),  # current XNU adaptation uses one SMP cluster
            ('cluster-type', u32(0)),  # homogeneous CLUSTER_TYPE_SMP, not AMP
            ('die-cluster-id', u32(0)),
            ('cluster-core-id', u32(core)),
            ('l2-cache-id', u32(core)),  # distinct per-core L2 nodes in live FDT
            ('l3-cache-id', u32(0)),     # shared L3
            ('state', cstr('running' if core == 0 else 'stopped')),
            ('timebase-frequency', u32(timebase)),
            ('clock-frequency', u32((2200000000 if core >= 6 else 2000000000) if a24 else (2304000000 if core >= 6 else 1804800000))),
            ('bus-frequency', u32(100000000)),
            ('memory-frequency', u32(1866000000)),
            ('peripheral-frequency', u32(timebase)),
            ('fixed-frequency', u32(timebase)),
        ]))
    cpus = node('cpus', [ph(), ('#address-cells', u32(1)),
                         ('#size-cells', u32(0))], cpu_nodes)

    gic = node('gic', [
        ph(),
        ('compatible', cstr('arm,gic-v3')),
        ('interrupt-controller', b''),
        ('virtual-timer-intid', u32(QEMU_VTIMER_INTID if qemu or a24 else VTIMER_INTID)),
        ('reg', u64(gicd - SOC_BASE, (A24_GICD_SIZE if (a24 and not qemu) else GICD_SIZE),
                    gicr - SOC_BASE, (A24_GICR_SIZE if (a24 and not qemu) else GICR_SIZE))),
    ])
    disp0 = node('disp0', [
        ph(),
        ('device_type', cstr('display-subsystem')),
        ('compatible', cstr('sweet,display')),
        ('canvas-width', u32(1080 if a24 else 1125)),
        ('canvas-height', u32(2340 if a24 else 2436)),
    ])
    arm_io_children = [gic,
        # No hardware: watchdogd checks IODeviceTree:/arm-io/wdt for no-pmu and
        # otherwise crashes trying to set the PMU boot stage (customer builds
        # ignore the -wdt_no_pmu boot-arg).
        node('wdt', [ph(), ('no-pmu', u32(1))])]
    # The physical A24 display is still unvalidated; expose the synthetic
    # display only in QEMU so iOS userland can initialize its display manager.
    if not a24 or qemu:
        arm_io_children.append(disp0)
    arm_io = node('arm-io', [
        ph(),
        ('device_type', cstr('sweet-io')),
        ('compatible', cstr('sweet-io') + cstr('arm-io')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
        ('ranges', u64(0, SOC_BASE, 0x100000000 - SOC_BASE)),
    ], arm_io_children)

    fbcon = node('sweet-fbcon', [
        ph(),
        ('reg', u64(fb, fb_size)),
        ('width', u32(fb_w)),
        ('height', u32(fb_h)),
        ('stride', u32(fb_stride)),
    ])

    # bsd/dev/sweet_ufs.c: the UFS host ABL leaves running (absolute physical reg).
    ufs = node('sweet-ufs', [
        ph(),
        ('compatible', cstr('mediatek,mt8183-ufshci') if a24 else cstr('qcom,ufshc')),
        ('reg', u64(ufs_base, ufs_size)),
    ])

    # pmap_compute_max_asids requires the node even when no overrides are set.
    # An absent pmap-max-asids property selects XNU's own MAX_ASIDS default.
    # No effaceable storage: keybagd then reads /private/var/keybags/systembag.kb
    # as a plain plist instead of decrypting it with the effaceable key.
    defaults = node('defaults', [ph(), ('no-effaceable-storage', u32(1))])

    # MobileGestalt HomeButtonType = IODeviceTree:/buttons home-button-type
    # (D22AP: 2, no Home button; absent = 0 = Home-button device).
    buttons = node('buttons', [
        ph(),
        ('button-names', cstr('volup') + cstr('voldown') + cstr('hold')),
        ('home-button-type', u32(2)),
        ('opposed-power-vol-buttons', u32(1)),
    ])

    product_props = d22ap_product()
    product = [node('product', [ph()] + product_props)] if product_props else []

    # Panic log region. /pram reg = <phys size>; it sits just above the
    # dram-size we expose, so XNU maps it but never allocates into it.
    pram = node('pram', [ph(), ('reg', u64(panic_base) + u64(PANIC_LOG_SIZE))])

    # Identity of the iPhone X whose userland runs here: compatible[0] is
    # hw.model/hw.target (D22AP), model is hw.machine/hw.product
    # (iPhone10,3). 'xiaomi,sweet' stays for SweetPlatformExpert matching.
    if a24:
        # A24 is the carrier platform; expose only the neutral ARM identity
        # and retain iPhone identity in the userspace /product description.
        compatible = cstr('D22AP') + cstr('iPhone10,3') + cstr('samsung,a24') + cstr('mediatek,MT6789') + cstr('AppleARM')
    else:
        compatible = cstr('D22AP') + cstr('iPhone10,3') + cstr('xiaomi,sweet') + cstr('qcom,sm7150') + cstr('AppleARM')
    return node('device-tree', [
        ph(),
        ('compatible', compatible),
        ('model', cstr('iPhone10,3')),
        ('target-type', cstr('D22')),
        ('target-sub-type', cstr('D22AP')),
        ('manufacturer', cstr('Apple Inc.')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
    ], [chosen, defaults, cpus, arm_io, buttons, pram] +
       ([] if (a24 and not qemu) else [fbcon]) + product + ([] if qemu or a24 else [ufs]))


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        raise SystemExit('usage: mkadt.py OUT.adt [--dump] [--qemu] [--highmem] [--a24 --ram-range BASE:SIZE]')
    out = args[0]
    ram_ranges = []
    smp = None
    for i, arg in enumerate(args):
        if arg == '--smp':
            try:
                smp = int(args[i + 1])
            except (IndexError, ValueError):
                raise SystemExit('--smp must be an integer, e.g. --smp 2')
        elif arg == '--ram-range':
            try:
                base, size = args[i + 1].split(':', 1)
                ram_ranges.append((int(base, 0), int(size, 0)))
            except (IndexError, ValueError):
                raise SystemExit('--ram-range must be BASE:SIZE, e.g. 0x80000000:0x10000000')
    root = build(qemu='--qemu' in args, highmem='--highmem' in args,
                 a24='--a24' in args, ram_ranges=ram_ranges, smp=smp)
    blob = adt.serialize(root)
    open(out, 'wb').write(blob)
    if '--dump' in args:
        adt.dump(adt.parse(blob)[0])
    print(f'{out}: {len(blob)} bytes', file=sys.stderr)
