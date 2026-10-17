"""Minimal NES harness for FC 天地を喰らうII 諸葛孔明伝 (Capcom, MMC3 / mapper 4, CHR-RAM) on py65.

Reuses the register-level PPU / CPU loop of chuugen/tools/nes_emu.py and swaps in the MMC3 bus:
8 KB PRG banks (R6/R7 + PRG mode), 1 KB / 2 KB CHR banks (R0-R5 + CHR inversion) over 8 KB CHR-RAM,
mirroring register, 8 KB PRG-RAM at $6000 and the scanline IRQ counter (clocked once per rendered
scanline at about PPU dot 260, plus the pre-render line, as the A12 rise does when BG uses $0000 and
sprites $1000).
"""
import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location("chuugen_nes_emu", os.path.join(REPO, "chuugen", "tools", "nes_emu.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
BUTTONS, read_nes = base.BUTTONS, base.read_nes
LINE = 341 / 3
EXTRA = ("chr_ram", "regs", "bank_select", "mirror", "irq_latch", "irq_count", "irq_reload", "irq_enabled",
         "irq_pending", "next_clock")


class Nes(base.Nes):
    def __init__(self, rom_path: str):
        self.regs = [0, 2, 4, 5, 6, 7, 0, 1]
        self.bank_select = self.mirror = 0
        self.irq_latch = self.irq_count = 0
        self.irq_reload = self.irq_enabled = self.irq_pending = False
        self.chr_ram = bytearray(0x2000)
        super().__init__(rom_path)
        self.chr_rom = self.chr_ram
        self.chrreg = self.chr_slots()
        self.last_frame_chr = (list(self.chrreg), [])
        self.next_clock = 0

    # ------------------------------------------------------------ mapper
    def prg_off(self, a: int) -> int:
        slot, n = (a - 0x8000) >> 13, self.prg_banks
        if slot == 3:
            bank = n - 1
        elif slot == 1:
            bank = self.regs[7]
        elif (slot == 0) ^ bool(self.bank_select & 0x40):
            bank = self.regs[6]
        else:
            bank = n - 2
        return (bank % n) * 0x2000 + (a & 0x1FFF)

    def chr_slots(self) -> list[int]:
        r = self.regs
        s = [r[0] & 0xFE, r[0] | 1, r[1] & 0xFE, r[1] | 1, r[2], r[3], r[4], r[5]]
        return s[4:] + s[:4] if self.bank_select & 0x80 else s

    def __getitem__(self, a: int) -> int:
        if 0x4020 <= a < 0x6000:
            return 0
        return super().__getitem__(a)

    def __setitem__(self, a: int, v: int) -> None:
        if a < 0x8000:
            if not 0x4020 <= a < 0x6000:
                super().__setitem__(a, v)
            return
        even = not a & 1
        if a < 0xA000:
            if even:
                self.bank_select = v
            else:
                self.regs[self.bank_select & 7] = v
            slots = self.chr_slots()
            c = self.cpu.processorCycles - self.frame_start
            for i, b in enumerate(slots):
                if b != self.chrreg[i]:
                    self.chr_writes.append((c, i, b))
            self.chrreg = slots
        elif a < 0xC000:
            if even:
                self.mirror = v & 1
        elif a < 0xE000:
            if even:
                self.irq_latch = v
            else:
                self.irq_count, self.irq_reload = 0, True
        elif even:
            self.irq_enabled = self.irq_pending = False
        else:
            self.irq_enabled = True

    def chr_byte(self, a: int) -> int:
        return self.chr_ram[(self.chrreg[a >> 10] * 0x400 + (a & 0x3FF)) & 0x1FFF]

    def vram_write(self, a: int, v: int) -> None:
        a &= 0x3FFF
        if a < 0x2000:
            self.chr_ram[(self.chrreg[a >> 10] * 0x400 + (a & 0x3FF)) & 0x1FFF] = v
        else:
            super().vram_write(a, v)

    def nt_ref(self, a: int):
        a &= 0xFFF
        page = (a >> 11) & 1 if self.mirror else (a >> 10) & 1
        return self.ciram, page * 0x400 + (a & 0x3FF)

    # ------------------------------------------------------------ run
    def clock_irq(self) -> None:
        if self.irq_count == 0 or self.irq_reload:
            self.irq_count, self.irq_reload = self.irq_latch, False
        else:
            self.irq_count -= 1
        if self.irq_count == 0 and self.irq_enabled:
            self.irq_pending = True

    def _run_until(self, cycle: int, sprite0: int | None = None) -> None:
        cpu, bps = self.cpu, self.breakpoints
        while cpu.processorCycles < cycle:
            if bps and cpu.pc in bps:
                bps[cpu.pc](self)
            cpu.step()
            c = cpu.processorCycles - self.frame_start
            while self.next_clock is not None and c >= self.next_clock:
                if self.mask & 0x18:
                    self.clock_irq()
                line = round((self.next_clock - 87) / LINE) + 1
                self.next_clock = line * LINE + 87 if line < 240 else None
            if self.irq_pending and not cpu.p & cpu.INTERRUPT:
                cpu.irq()
            if sprite0 is not None and cpu.processorCycles >= sprite0:
                self.status |= 0x40
                sprite0 = None

    def run_frame(self) -> None:
        # pre-render line clock (end of the previous frame), then lines 0-239
        if self.mask & 0x18:
            self.clock_irq()
        self.next_clock = 87
        super().run_frame()

    def snapshot(self) -> dict:
        st = super().snapshot()
        for k in EXTRA:
            st[k] = base.copy.copy(getattr(self, k))
        return st

    def restore(self, st: dict) -> None:
        super().restore(st)
        for k in EXTRA:
            setattr(self, k, base.copy.copy(st[k]))
        self.chr_rom = self.chr_ram
