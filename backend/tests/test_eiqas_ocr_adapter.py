"""Docling places language/PSM flags before the input raster."""

from eiqas_research.ocr_cli import input_index


def test_docling_and_direct_tesseract_argument_orders(tmp_path):
    image = tmp_path / "page.png"
    image.write_bytes(b"synthetic input")
    assert input_index(["-l", "chi_sim+eng", "--psm", "6", str(image), "stdout", "tsv"]) == 4
    assert input_index([str(image), "stdout", "-l", "eng"]) == 0
    assert input_index(["--list-langs"]) is None
