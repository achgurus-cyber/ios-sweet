/*
 * Samsung Galaxy A24 (SM-A245F), MT6789 target facts collected from the
 * live FDT via read-only ADB. This is an experimental shim configuration;
 * it is not yet a validated boot image or a device-tested hardware driver.
 */
#pragma once

#define PLAT_GICD_BASE       0x0c000000UL
#define PLAT_GICR_BASE       0x0c040000UL
#define PLAT_GICR_SIZE       0x00200000UL
#define PLAT_GICR_PE_SIZE    0x00020000UL

/* GICv3 timer tuples in the live FDT: secure PPI 13, physical 14,
 * virtual 11, hypervisor 10. GIC PPI INTID = tuple number + 16. */
#define PLAT_VTIMER_INTID    27
#define PLAT_PTIMER_INTID    30
#define PLAT_SGI_INTID       1
#define PLAT_NR_CPUS         8

#define PLAT_UFS_BASE        0x11270000UL

/* Boot framebuffer reservation from the live FDT. The active pixel format,
 * stride and ownership after Samsung's boot stages still need validation. */
#define PLAT_FB_BASE         0xfe144000UL
#define PLAT_FB_SIZE         0x01ebb000UL
#define PLAT_FB_WIDTH        1080
#define PLAT_FB_HEIGHT       2340
#define PLAT_FB_STRIDE       (PLAT_FB_WIDTH * 4)
