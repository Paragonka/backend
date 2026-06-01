#!/usr/bin/env python3
"""
Build Tailwind CSS + download DaisyUI.
No Node.js required.
Output: static/tailwind.css, static/daisyui.css
"""

import sys
import urllib.request
from pathlib import Path

from pytailwindcss import install, run

ROOT = Path(__file__).parent
INPUT = ROOT / "static" / "src" / "input.css"
TAILWIND_OUT = ROOT / "static" / "tailwind.css"
DAISYUI_OUT = ROOT / "static" / "daisyui.css"
DAISYUI_CDN = "https://cdn.jsdelivr.net/npm/daisyui@4.12.14/dist/full.min.css"


def _build_tailwind() -> None:
    if not INPUT.exists():
        print(f"⚠ Input CSS not found: {INPUT}", file=sys.stderr)

        return

    if TAILWIND_OUT.exists():
        TAILWIND_OUT.unlink()

    install()
    run(
        ["-i", str(INPUT), "-o", str(TAILWIND_OUT), "--minify"],
        cwd=ROOT,
    )

    if TAILWIND_OUT.exists():
        print(
            f"✓ Tailwind built: {TAILWIND_OUT} "
            f"({TAILWIND_OUT.stat().st_size / 1024:.1f} KB)"
        )


def _download_daisyui() -> None:
    print("Downloading DaisyUI from CDN...")
    # Development tool for downloading DaisyUI from the CDN
    urllib.request.urlretrieve(DAISYUI_CDN, DAISYUI_OUT)

    if DAISYUI_OUT.exists():
        print(
            f"✓ DaisyUI downloaded: {DAISYUI_OUT} "
            f"({DAISYUI_OUT.stat().st_size / 1024:.1f} KB)"
        )


def build_css() -> None:
    _build_tailwind()
    _download_daisyui()


if __name__ == "__main__":
    build_css()
