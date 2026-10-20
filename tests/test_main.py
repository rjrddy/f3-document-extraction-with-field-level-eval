from main import extract, make_document
from PIL import Image


def test_real_ocr_on_clean_synthetic_invoice():
    image, truth, _ = make_document(0)
    actual, confidence = extract(image)
    assert actual == truth and confidence > 0


def test_blank_document_requires_review():
    actual, confidence = extract(Image.new("RGB", (900, 500), "white"))
    assert all(v is None for v in actual.values()) and confidence == 0
