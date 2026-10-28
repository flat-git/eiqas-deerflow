#!/opt/eiqas-venv/bin/python
"""Tesseract CLI adapter: remove long grid lines without changing coordinates.

Docling receives the original PDF for layout. Only its temporary OCR raster is
cleaned, so raw originals and physical-page/bounding-box provenance are retained.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def clean_grid(source: Path, target: Path) -> bool:
    import cv2
    import numpy as np
    from PIL import Image

    image = Image.open(source).convert("RGB")
    pixels = np.array(image)
    gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)[1]
    height, width = gray.shape
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(60, width // 25), 1)))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(60, height // 35))))
    mask = cv2.bitwise_or(horizontal, vertical)
    if not np.any(mask):
        return False
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    pixels[mask > 0] = 255
    Image.fromarray(pixels).save(target, dpi=(300, 300))
    return True


def input_index(arguments: list[str]) -> int | None:
    for index, argument in enumerate(arguments):
        if not argument.startswith("-") and Path(argument).is_file():
            return index
    return None


def main() -> int:
    arguments = sys.argv[1:]
    index = input_index(arguments)
    if index is None:
        os.execv("/usr/bin/tesseract", ["tesseract", *arguments])
    with tempfile.TemporaryDirectory(prefix="eiqas-ocr-") as directory:
        target = Path(directory) / "clean.png"
        if clean_grid(Path(arguments[index]), target):
            arguments[index] = str(target)
        return subprocess.run(["/usr/bin/tesseract", *arguments], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
