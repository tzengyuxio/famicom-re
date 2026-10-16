"""Minimal NES harness for FC 聖火列傳 (C&E, mapper 240) on py65.

Reuses the register-level PPU / CPU loop of chuugen/tools/nes_emu.py and swaps in the mapper-240 bus:
one register at $4020-$5FFF (bits 4-7 = 32 KB PRG bank at $8000, bits 0-3 = 8 KB CHR bank),
8 KB PRG-RAM at $6000 and fixed horizontal mirroring. The game switches the BG pattern table ($2000
bit 4) in the middle of the frame for its status windows, so $2000 writes are logged per frame and
screen() uses the value in effect on each scanline.
"""
import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location("chuugen_nes_emu", os.path.join(REPO, "chuugen", "tools", "nes_emu.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
BUTTONS, read_nes = base.BUTTONS, base.read_nes


class Nes(base.Nes):
    prg_bank = 0

    def __init__(self, rom_path: str):
        super().__init__(rom_path)
        self.chrreg = [0]
        self.last_frame_chr = ([0], [])
        self.ctrl_writes, self.last_frame_ctrl = [], (0, [])

    def ppu_write(self, r: int, v: int) -> None:
        if r == 0:
            self.ctrl_writes.append((self.cpu.processorCycles - self.frame_start, v))
        super().ppu_write(r, v)

    def run_frame(self) -> None:
        frame_ctrl, self.ctrl_writes = self.ctrl, []
        super().run_frame()
        self.last_frame_ctrl = (frame_ctrl, self.ctrl_writes)

    def line_ctrl(self) -> list[int]:
        """$2000 value in effect on each of the 240 scanlines of the last finished frame."""
        v, writes = self.last_frame_ctrl
        out, i = [], 0
        for line in range(240):
            while i < len(writes) and writes[i][0] < (line + 1) * 341 / 3:
                v = writes[i][1]
                i += 1
            out.append(v)
        return out

    def screen(self, sprites: bool = True) -> tuple[int, int, list[int]]:
        """What the TV shows for the last frame, as 256x240 NES colour numbers (per-scanline $2000)."""
        saved = self.ctrl
        lines = self.line_ctrl()
        w, h, px = 256, 240, [0] * (256 * 240)
        for start in range(240):
            if start and lines[start] == lines[start - 1]:
                continue
            end = start + 1
            while end < 240 and lines[end] == lines[start]:
                end += 1
            self.ctrl = lines[start]
            _, _, part = super().screen(sprites)
            px[start * 256:end * 256] = part[start * 256:end * 256]
        self.ctrl = saved
        return w, h, px

    def prg_off(self, a: int) -> int:
        return (self.prg_bank * 0x8000 + (a - 0x8000)) % len(self.prg)

    def __getitem__(self, a: int) -> int:
        if 0x4020 <= a < 0x6000:
            return 0
        return super().__getitem__(a)

    def __setitem__(self, a: int, v: int) -> None:
        if 0x4020 <= a < 0x6000:
            self.prg_bank, self.chrreg = v >> 4, [v & 0x0F]
            self.chr_writes.append((self.cpu.processorCycles - self.frame_start, 0, v & 0x0F))
        elif a < 0x8000:
            super().__setitem__(a, v)

    def chr_byte(self, a: int) -> int:
        return self.chr_rom[(self.chrreg[0] * 0x2000 + (a & 0x1FFF)) % len(self.chr_rom)]

    def nt_ref(self, a: int):
        return self.ciram, ((a >> 11) & 1) * 0x400 + (a & 0x3FF)

    def snapshot(self) -> dict:
        st = super().snapshot()
        st["prg_bank"] = self.prg_bank
        return st

    def restore(self, st: dict) -> None:
        super().restore(st)
        self.prg_bank = st["prg_bank"]
