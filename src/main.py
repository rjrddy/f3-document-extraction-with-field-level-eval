"""Real OCR over synthetic financial documents, with field and review evaluation."""

import json
import random
import re
from pathlib import Path
import matplotlib
import matplotlib.pyplot as plt
import pytesseract
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def make_document(index: int) -> tuple[Image.Image, dict, str]:
    rng = random.Random(index)
    template = ["invoice-a", "invoice-b", "statement"][index % 3]
    truth = {
        "id": f"SYN-{index:04d}",
        "date": f"2026-01-{index % 28 + 1:02d}",
        "total": f"{rng.randint(100, 9999)}.{rng.randint(0, 99):02d}",
    }
    image = Image.new("RGB", (900, 500), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(
        str(Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"),
        26 if template != "statement" else 20,
    )
    lines = [
        f"SYNTHETIC {template.upper()}",
        "Supplier: Synthetic Example",
        f"Document: {truth['id']}",
        f"Date: {truth['date']}",
        f"Total: {truth['total']}",
    ]
    for j, line in enumerate(lines):
        draw.text((40, 35 + j * 70), line, font=font, fill="black")
    if template == "invoice-b":
        image = image.rotate(1.5, fillcolor="white")
    if template == "statement":
        image = image.filter(ImageFilter.GaussianBlur(1.1))
    return image, truth, template


def extract(image: Image.Image) -> tuple[dict, float]:
    data = pytesseract.image_to_data(image, config="--psm 6", output_type=pytesseract.Output.DICT)
    text = " ".join(data["text"])
    scores = [float(c) for t, c in zip(data["text"], data["conf"]) if t.strip() and float(c) >= 0]
    fields = {}
    for key, pattern in {
        "id": r"Document:\s*(SYN-\d{4})",
        "date": r"Date:\s*(\d{4}-\d{2}-\d{2})",
        "total": r"Total:\s*(\d+\.\d{2})",
    }.items():
        match = re.search(pattern, text, re.I)
        fields[key] = match.group(1) if match else None
    return fields, sum(scores) / len(scores) if scores else 0


def benchmark() -> dict:
    folder = Path("evidence/documents")
    folder.mkdir(exist_ok=True)
    rows = []
    for i in range(30):
        image, truth, template = make_document(i)
        image.save(folder / f"{i}.png")
        actual, confidence = extract(image)
        rows.append(
            {
                "document": i,
                "template": template,
                "truth": truth,
                "actual": actual,
                "confidence": confidence,
                "correct": actual == truth,
            }
        )
    fields = {
        key: sum(r["actual"][key] == r["truth"][key] for r in rows) / len(rows)
        for key in ["id", "date", "total"]
    }
    per_template = {
        name: {
            key: sum(r["actual"][key] == r["truth"][key] for r in rows if r["template"] == name)
            / 10
            for key in fields
        }
        for name in ["invoice-a", "invoice-b", "statement"]
    }
    curve = []
    for threshold in [0, 70, 85, 90, 95, 99]:
        auto = [r for r in rows if r["confidence"] >= threshold and all(r["actual"].values())]
        curve.append(
            {
                "threshold": threshold,
                "review_rate": 1 - len(auto) / len(rows),
                "auto_accuracy": sum(r["correct"] for r in auto) / len(auto) if auto else None,
            }
        )
    Path("evidence/extractions.json").write_text(json.dumps(rows, indent=2))
    Path("evidence/per-field.json").write_text(json.dumps(per_template, indent=2))
    Path("evidence/review-curve.json").write_text(json.dumps(curve, indent=2))
    plt.plot(
        [r["review_rate"] for r in curve],
        [r["auto_accuracy"] if r["auto_accuracy"] is not None else float("nan") for r in curve],
        marker="o",
    )
    plt.xlabel("review fraction")
    plt.ylabel("auto-extracted document accuracy")
    plt.savefig("evidence/tradeoff.svg")
    plt.close()
    Path("evidence/field-table.md").write_text(
        "| Template | ID accuracy | Date accuracy | Total accuracy |\n|---|---|---|---|\n"
        + "".join(
            f"| {name} | {v['id']} | {v['date']} | {v['total']} |\n"
            for name, v in per_template.items()
        )
    )
    return {
        "synthetic_documents": len(rows),
        "id_accuracy": fields["id"],
        "date_accuracy": fields["date"],
        "total_accuracy": fields["total"],
        "exact_document_accuracy": sum(r["correct"] for r in rows) / len(rows),
    }


if __name__ == "__main__":
    print(json.dumps(benchmark(), indent=2))
