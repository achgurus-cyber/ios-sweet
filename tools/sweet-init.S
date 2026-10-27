/*
 * First userspace program for SWEET bring-up: mockfs serves the RAM disk
 * itself as /sbin/launchd, so this static binary is PID 1. It proves that
 * exec, the user/kernel boundary, devfs and the console all work, then
 * stays alive (init exiting panics the kernel).
 *
 * tools/mkinit.py wraps the assembled __text into a static Mach-O, so this
 * must stay position independent with no relocations and no writable data:
 * every reference is adr (PC-relative), the PID digit lives on the stack.
 *
 * Raw XNU syscalls: number in x16, svc #0x80, carry set on error.
 */
#define SYS_write	4
#define SYS_open	5
#define SYS_getpid	20
#define SYS_select	93
#define SYS_mmap	197

#define O_RDWR		2
#define PROT_RW		3
#define MAP_ANON_PRIV	0x1002

	.text
	.globl	_start
	.p2align 2
_start:
	/*
	 * Align SP like crt0/dyld do to avoid SP alignment fault (SIGBUS).
	 */
	mov	x9, sp
	and	x9, x9, #~15
	mov	sp, x9

	adr	x0, path
	mov	x1, #O_RDWR
	mov	x2, #0
	mov	x16, #SYS_open
	svc	#0x80
	b.cs	hang			/* no console: nothing to report to */
	mov	x19, x0

	adr	x1, hello
	adr	x2, hello_tail
	sub	x2, x2, x1
	bl	write_console

	mov	x16, #SYS_getpid
	svc	#0x80
	add	w0, w0, #'0'		/* PID 1 expected: one digit */
	sub	sp, sp, #16
	strb	w0, [sp]
	mov	x1, sp
	mov	x2, #1
	bl	write_console
	add	sp, sp, #16

	adr	x1, hello_tail
	adr	x2, mmap_intro
	sub	x2, x2, x1
	bl	write_console

	/*
	 * Test 1: Allocate 16 KiB anonymous page via SYS_mmap.
	 */
	mov	x0, #0
	mov	x1, #0x4000		/* 16 KiB page */
	mov	x2, #PROT_RW		/* PROT_READ | PROT_WRITE */
	mov	x3, #MAP_ANON_PRIV	/* MAP_ANON | MAP_PRIVATE */
	mov	x4, #-1			/* fd = -1 */
	mov	x5, #0			/* offset = 0 */
	mov	x16, #SYS_mmap
	svc	#0x80
	b.cs	mmap_failed
	mov	x20, x0			/* x20 = allocated page VA */

	/* Print allocated address */
	adr	x1, mmap_intro
	adr	x2, mmap_chk_intro
	sub	x2, x2, x1
	bl	write_console

	mov	x0, x20
	bl	print_hex64

	/*
	 * Test 2: Multi-point write across the page to verify Translation Fault
	 * and demand paging at page start, middle, and boundaries.
	 */
	ldr	x21, pat0
	str	x21, [x20, #0]

	ldr	x22, pat1
	add	x10, x20, #0x1000
	str	x22, [x10]

	ldr	x23, pat2
	add	x10, x20, #0x2000
	str	x23, [x10]

	ldr	x24, pat3
	mov	x11, #0x3ff8
	str	x24, [x20, x11]

	/* Read back all 4 values */
	ldr	x21, [x20, #0]
	add	x10, x20, #0x1000
	ldr	x22, [x10]
	add	x10, x20, #0x2000
	ldr	x23, [x10]
	ldr	x24, [x20, x11]

	/* Compute verification checksum */
	eor	x25, x21, x22
	eor	x26, x23, x24
	add	x27, x25, x26

	/* Print checksum */
	adr	x1, mmap_chk_intro
	adr	x2, mmap_pass_msg
	sub	x2, x2, x1
	bl	write_console

	mov	x0, x27
	bl	print_hex64

	/* Compare against expected: 0x9b28fb21feeeeeea */
	ldr	x28, expected_chk
	cmp	x27, x28
	b.ne	mmap_failed

	adr	x1, mmap_pass_msg
	adr	x2, mmap_fail_msg
	sub	x2, x2, x1
	bl	write_console
	b	tick

mmap_failed:
	adr	x1, mmap_fail_msg
	adr	x2, alive
	sub	x2, x2, x1
	bl	write_console

tick:
	/* select(0, NULL, NULL, NULL, &5s) as a portable sleep */
	mov	x0, #0
	mov	x1, #0
	mov	x2, #0
	mov	x3, #0
	adr	x4, five_sec
	mov	x16, #SYS_select
	svc	#0x80

	adr	x1, alive
	adr	x2, alive_end
	sub	x2, x2, x1
	bl	write_console
	b	tick

/* print_hex64: print uint64_t in x0 as 0x16hex\n */
print_hex64:
	stp	x29, x30, [sp, #-48]!
	mov	x29, sp
	stp	x19, x20, [sp, #16]
	str	x0, [sp, #32]
	sub	sp, sp, #32
	mov	x9, sp
	mov	w10, #'0'
	strb	w10, [x9], #1
	mov	w10, #'x'
	strb	w10, [x9], #1
	mov	w11, #60
1:	lsr	x12, x0, x11
	and	x12, x12, #0xf
	cmp	x12, #10
	blo	2f
	add	x12, x12, #('a' - 10)
	b	3f
2:	add	x12, x12, #'0'
3:	strb	w12, [x9], #1
	subs	w11, w11, #4
	b.ge	1b
	mov	w10, #'\n'
	strb	w10, [x9], #1
	mov	x1, sp
	mov	x2, #19
	bl	write_console
	add	sp, sp, #32
	ldp	x19, x20, [sp, #16]
	ldp	x29, x30, [sp], #48
	ret

/* write(x19, x1, x2) */
write_console:
	mov	x0, x19
	mov	x16, #SYS_write
	svc	#0x80
	ret

hang:
	b	hang

	.p2align 3
five_sec:
	.quad	5			/* tv_sec */
	.quad	0			/* tv_usec (int32 + padding) */
pat0:
	.quad	0x1122334455667788
pat1:
	.quad	0xaabbccddeeff0011
pat2:
	.quad	0xdeadbeefcafebabe
pat3:
	.quad	0x0123456789abcdef
expected_chk:
	.quad	0x9b28fb21feeeeeea

path:
	.asciz	"/dev/console"
hello:
	.ascii	"\n*** SWEET userspace: init running as PID "
hello_tail:
	.ascii	" ***\n"
mmap_intro:
	.ascii	"SWEET init: mmap 16KB anon page returned addr="
mmap_chk_intro:
	.ascii	"SWEET init: memory verification checksum="
mmap_pass_msg:
	.ascii	"SWEET init: 4-point page boundary check PASSED\n"
mmap_fail_msg:
	.ascii	"SWEET init: memory verification FAILED\n"
alive:
	.ascii	"SWEET init: still alive\n"
alive_end:
