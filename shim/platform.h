#pragma once

#ifdef PLATFORM_A24
#include "platform_a24.h"
#else
#define PLAT_GICD_BASE       0x17a00000UL
#define PLAT_GICR_BASE       0x17a60000UL
#define PLAT_GICR_SIZE       0x00100000UL
#define PLAT_GICR_PE_SIZE    0x00020000UL
#define PLAT_VTIMER_INTID    19
#define PLAT_PTIMER_INTID    18
#define PLAT_SGI_INTID       1
#define PLAT_NR_CPUS         8
#define PLAT_UFS_BASE        0x01d84000UL
#define PLAT_FB_BASE         0x9c000000UL
#define PLAT_FB_SIZE         0x01000000UL
#define PLAT_FB_WIDTH        1080
#define PLAT_FB_HEIGHT       2400
#define PLAT_FB_STRIDE       (PLAT_FB_WIDTH * 4)
#endif
