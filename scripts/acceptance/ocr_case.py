"""Real bilingual OCR regression; run inside the pinned analysis image.

All inputs are generated synthetic fixtures, never company disclosures.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

sys.path.insert(0, "/opt/eiqas")
from worker import parse_document


def image_page(chinese=True):
    image = Image.new("RGB", (1650, 2338), "white")
    draw = ImageDraw.Draw(image)
    font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    font = ImageFont.truetype(font_path, 46)
    title = "合成扫描样例：非企业披露" if chinese else "Synthetic scanned fixture"
    draw.text((100, 110), title, fill="black", font=font)
    draw.text((100, 210), "单位：万元" if chinese else "Unit: CNY ten thousand", fill="black", font=font)
    values = [["指标" if chinese else "Metric", "2024", "2025"], ["收入" if chinese else "Revenue", "1200", "1350"], ["成本" if chinese else "Cost", "800", "860"]]
    for row, cells in enumerate(values):
        for column, text in enumerate(cells):
            draw.text((140 + column * 470, 380 + row * 190), text, fill="black", font=font)
    for x in [100, 570, 1040, 1510]:
        draw.line([(x, 340), (x, 910)], fill="black", width=4)
    for y in [340, 530, 720, 910]:
        draw.line([(100, y), (1510, y)], fill="black", width=4)
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    images = [image_page(True), image_page(False)]
    paths = []
    for index, image in enumerate(images):
        path = args.output / f"scan-{index + 1}.png"
        image.save(path)
        paths.append(path)
    pdf = args.output / "synthetic-mixed.pdf"
    document = canvas.Canvas(str(pdf), pagesize=A4)
    for path in paths:
        document.drawImage(str(path), 0, 0, width=A4[0], height=A4[1])
        document.showPage()
    document.drawString(50, 780, "Synthetic native-text control page")
    document.drawString(50, 750, "Revenue 1200; Cost 800; Year 2024")
    document.save()
    result = parse_document(pdf, "application/pdf")
    (args.output / "extraction.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    blocks = result["blocks"]
    text = " ".join(block["text"] for block in blocks)
    text = re.sub(r"[,\s]", "", text)
    checks = {
        "physical_pages": result["page_count"] == 3,
        "critical_1200": "1200" in text,
        "critical_1350": "1350" in text,
        "scan_table_numbers": all(any(block.get("page") == page and block.get("text", "").strip() == value and "row" in block for block in blocks) for page in [1, 2] for value in ["1200", "1350", "800", "860"]),
        "chinese_text": any("收入" in block["text"] for block in blocks),
        "english_text": any("Revenue" in block["text"] for block in blocks),
        "table_locators": any("row" in block and "column" in block for block in blocks),
        "scan_is_ocr": any(block.get("ocr") and block.get("page") in [1, 2] for block in blocks),
        "native_is_not_ocr": any(block.get("page") == 3 and block.get("ocr") is False for block in blocks),
        "valid_locations": all(1 <= block["page"] <= 3 for block in blocks if block.get("page") is not None),
    }
    low = args.output / "synthetic-low-resolution.pdf"
    images[0].resize((220, 312)).resize(images[0].size).save(low, "PDF", resolution=200)
    try:
        low_result = parse_document(low, "application/pdf")
        (args.output / "low-resolution-extraction.json").write_text(json.dumps(low_result, ensure_ascii=False, indent=2))
        checks["low_resolution_recorded"] = bool(low_result["blocks"])
    except Exception as exc:
        (args.output / "low-resolution-extraction.json").write_text(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        checks["low_resolution_recorded"] = True
    manifest = {
        "synthetic": True,
        "engine": result["engine"],
        "source_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "checks": checks,
        "status": "passed" if all(checks.values()) else "failed",
        "note": "Automated actual OCR regression. Human correction and reader acceptance remain separate.",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps(manifest, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
