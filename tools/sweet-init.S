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
	 * The kernel enters a static binary with sp at argc, aligned only to
	 * what the argument/apple strings happened to need. Using a misaligned
	 * sp as a base register raises an SP alignment fault (SIGBUS) on real
	 * hardware (QEMU does not check), so align it like crt0/dyld do.
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
	adr	x2, mmap_ok_msg
	sub	x2, x2, x1
	bl	write_console

	/* Verify EL0 userspace virtual memory (mmap + demand paging) */
	mov	x0, #0
	mov	x1, #0x4000		/* 16 KiB page */
	mov	x2, #PROT_RW		/* PROT_READ | PROT_WRITE */
	mov	x3, #MAP_ANON_PRIV	/* MAP_ANON | MAP_PRIVATE */
	mov	x4, #-1		/* fd = -1 */
	mov	x5, #0		/* offset = 0 */
	mov	x16, #SYS_mmap
	svc	#0x80
	b.cs	mmap_failed
	mov	x20, x0

	/* Trigger translation fault: store and verify pattern */
	movz	x21, #0x4554		/* 'ET' */
	movk	x21, #0x5357, lsl #16	/* 'SW' */
	str	x21, [x20]
	ldr	x22, [x20]
	cmp	x21, x22
	b.ne	mmap_failed

	adr	x1, mmap_ok_msg
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
path:
	.asciz	"/dev/console"
hello:
	.ascii	"\n*** SWEET userspace: init running as PID "
hello_tail:
	.ascii	" ***\n"
mmap_ok_msg:
	.ascii	"SWEET init: userspace mmap 16KB anon page PASSED\n"
mmap_fail_msg:
	.ascii	"SWEET init: userspace mmap FAILED\n"
alive:
	.ascii	"SWEET init: still alive\n"
alive_end:
