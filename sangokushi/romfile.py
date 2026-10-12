"""ROM access for the FC 三國志 scripts.

The source is the zip in roms/; a plain .nes path also works.
"""
import os
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROM = os.path.join(REPO, "roms", "Sangokushi (Japan).zip")


def read_rom(path: str = DEFAULT_ROM) -> bytes:
    """Whole iNES file: a .nes, or the single .nes inside a .zip."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            (name,) = [n for n in z.namelist() if n.lower().endswith(".nes")]
            return z.read(name)
    with open(path, "rb") as f:
        return f.read()
