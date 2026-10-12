"""Minimal MMC5 + 6502 harness for calling KOEI p-code functions of FC 水滸伝 (needs py65).

Only what the face routine touches is emulated: PRG banking ($5113-$5117), the MMC5
multiplier ($5205/$5206), ExRAM, PRG-RAM, a write-only PPU ($2006/$2007) and the NMI
handler, which is entered whenever the main code spins waiting for vblank.
"""
from py65.devices.mpu6502 import MPU

WAIT_LOOPS = {0xFB91, 0xFB9A, 0xFACC}  # wait for NMI: PPU transfer queue ($72 / $0713), palette fade


class Mem:
    def __init__(self, prg: bytes):
        self.prg = prg
        self.ram = bytearray(0x800)
        self.wram = bytearray(0x10000)
        self.exram = bytearray(0x400)
        self.vram = bytearray(0x4000)
        self.vaddr = self.vhi = self.latch = 0
        self.m1 = self.m2 = 0
        # power-on state set by RESET ($F526/$F561); $070C-$070E shadow the bank registers
        self.regs = {0x5113: 5, 0x5114: 0x80, 0x5115: 0x81, 0x5116: 0x80 | 30, 0x5117: 0x80 | 31}
        self.ram[0x711] = 1  # ExRAM mode 1 flag checked by the NMI ExRAM copier

    def map_a000(self, bank: int) -> None:
        self.regs[0x5115] = 0x80 | bank
        self.ram[0x70C], self.ram[0x70D], self.ram[0x70E] = self.regs[0x5113], self.regs[0x5114], self.regs[0x5115]

    def __len__(self):
        return 0x10000

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(0x10000))]
        if a < 0x2000:
            return self.ram[a & 0x7FF]
        if a < 0x4000:
            if a & 7 == 2:
                self.latch = 0
                return 0x80
            return 0
        if a == 0x5204:
            return 0x40
        if a == 0x5205:
            return (self.m1 * self.m2) & 0xFF
        if a == 0x5206:
            return (self.m1 * self.m2) >> 8
        if 0x5C00 <= a < 0x6000:
            return self.exram[a - 0x5C00]
        if 0x6000 <= a < 0x8000:
            return self.wram[(self.regs[0x5113] & 7) * 0x2000 + a - 0x6000]
        if a >= 0x8000:
            reg = 0x5114 + ((a - 0x8000) >> 13)
            return self.prg[(self.regs[reg] & 0x1F) * 0x2000 + (a & 0x1FFF)]
        return 0

    def __setitem__(self, a, v):
        if isinstance(a, slice):
            for i, x in zip(range(*a.indices(0x10000)), v):
                self[i] = x
        elif a < 0x2000:
            self.ram[a & 0x7FF] = v
        elif a < 0x4000 and a & 7 == 6:
            if self.latch == 0:
                self.vhi, self.latch = v, 1
            else:
                self.vaddr, self.latch = (self.vhi << 8 | v) & 0x3FFF, 0
        elif a < 0x4000 and a & 7 == 7:
            self.vram[self.vaddr] = v
            self.vaddr = (self.vaddr + 1) & 0x3FFF
        elif 0x5113 <= a <= 0x5117:
            self.regs[a] = v
        elif a == 0x5205:
            self.m1 = v
        elif a == 0x5206:
            self.m2 = v
        elif 0x5C00 <= a < 0x6000:
            self.exram[a - 0x5C00] = v
        elif 0x6000 <= a < 0x8000:
            self.wram[(self.regs[0x5113] & 7) * 0x2000 + a - 0x6000] = v


def call_pcode(mem: Mem, entry: int, bank_a000: int, args: list[int], on_step=None,
               sp: int = 0x0580, max_steps: int = 3_000_000) -> None:
    """JSR to a p-code function (entry starts with JSR $E424) with 16-bit args on the p-code stack.

    on_step(cpu) may return True to stop early.
    """
    mem.map_a000(bank_a000)
    mem[0x02], mem[0x03] = sp & 0xFF, sp >> 8
    for i, v in enumerate(args):  # first arg at FP+$0B = SP+2
        mem[sp + 2 + 2 * i], mem[sp + 3 + 2 * i] = v & 0xFF, v >> 8
    harness = 0x0700
    for i, b in enumerate([0x20, entry & 0xFF, entry >> 8, 0x4C, 0x03, 0x07]):
        mem[harness + i] = b
    cpu = MPU(memory=mem, pc=harness)
    nmi = mem[0xFFFA] | mem[0xFFFB] << 8
    in_nmi, nmi_sp = False, 0
    for _ in range(max_steps):
        if cpu.pc == harness + 3:
            return
        if cpu.pc in WAIT_LOOPS and not in_nmi:
            cpu.stPushWord(cpu.pc)
            cpu.stPush(cpu.p)
            cpu.pc, in_nmi, nmi_sp = nmi, True, cpu.sp
        if in_nmi and mem[cpu.pc] == 0x40 and cpu.sp == nmi_sp:  # RTI
            in_nmi = False
        if not in_nmi and on_step and on_step(cpu):
            return
        cpu.step()
    raise RuntimeError(f"p-code call did not return (pc={cpu.pc:04X})")


FACE_ROUTINE = 0xAEBB   # bank 16 at $A000; arg 3 = face code
FAR_COPY = 0xF2D6       # native: copy len bytes from (selector, src) to dst


def trace_face_copies(prg: bytes, code: int) -> list[tuple[int, int, int, int]]:
    """Far copies (selector, src, dst, len) made by the face routine, up to its 8-byte palette copy."""
    copies = []

    def on_step(cpu):
        if cpu.pc != FAR_COPY:
            return False
        m = cpu.memory
        sp = m[2] | m[3] << 8
        a = [m[sp + 2 + i] | m[sp + 3 + i] << 8 for i in range(0, 10, 2)]
        copies.append((a[0], a[2], a[3], a[4]))
        return a[4] == 8

    call_pcode(Mem(prg), FACE_ROUTINE, 16, [0, 0, code, 0, 0], on_step)
    return copies



BATTLE_INIT = 0xA47A      # bank 11: load terrain ($A41C), apply season ($A3BE), load regions ($A33B)
BATTLE_DRAW = 0xA319      # bank 11: draw all 14x12 cells with bank 9 $92CF (bank 9 at $8000)
SYSCALL = 0xEE39          # native: service number is the last value pushed; 8 = draw a tile/ExRAM image


def trace_battle_map(prg: bytes, province: int, month: int) -> tuple[list[tuple[int, int, int, int]], bytes, bytes]:
    """Run the game's battle map setup and drawing for a province.

    Returns the image draws (col, row, tile ptr, ExRAM ptr) and the decoded 14x12 buffers:
    block kinds at $7A8C and province ids at $7C84.

    The battle record pointed to by $7A66 holds the province at byte 0; the month ($71F6) picks the
    season. Service 8 is recorded and skipped, since the real one waits for frames forever here.
    """
    mem = Mem(prg)
    mem[0x7A66], mem[0x7A67] = 0x00, 0x61
    mem[0x6100], mem[0x71F6] = province, month
    call_pcode(mem, BATTLE_INIT, 11, [])
    mem.regs[0x5114] = 0x80 | 9
    draws = []

    def on_step(cpu):
        if cpu.pc == SYSCALL:
            m = cpu.memory
            sp = m[2] | m[3] << 8
            a = [m[sp + 2 + i] | m[sp + 3 + i] << 8 for i in range(0, 16, 2)]
            if a[0] == 8:
                draws.append((a[1], a[2], a[5], a[6]))
                cpu.pc = cpu.stPopWord() + 1  # return without running the service
        return False

    call_pcode(mem, BATTLE_DRAW, 11, [], on_step)
    return draws, bytes(mem[0x7A8C + i] for i in range(168)), bytes(mem[0x7C84 + i] for i in range(168))
