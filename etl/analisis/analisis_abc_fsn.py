"""Compatibility entry point for running the current full analysis pipeline."""

from pathlib import Path
import subprocess
import sys


ETL_ROOT = Path(__file__).resolve().parent
COMMANDS = [
    ["analisis/klasifikasi_abc.py"],
    ["analisis/klasifikasi_fsn.py"],
    ["analisis/matriks_abc_fsn.py"],
    ["analisis/analisisrop.py"],
]


if __name__ == "__main__":
    for command in COMMANDS:
        subprocess.run([sys.executable, *command], cwd=ETL_ROOT, check=True)
