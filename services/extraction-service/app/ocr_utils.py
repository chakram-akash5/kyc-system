import os
from PIL import Image, ImageFilter, ImageEnhance
from pdf2image import convert_from_path
import pytesseract
from app.utils import download_file


def preprocess(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    image = image.filter(ImageFilter.SHARPEN)
    image = ImageEnhance.Contrast(image).enhance(2.0)
    return image


def run_ocr_on_image(image: Image.Image) -> str:
    image = preprocess(image)
    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(image, config=config, lang="eng").strip()


def run_ocr(document_path: str) -> str:
    downloaded = False

    if document_path.startswith("http"):
        document_path = download_file(document_path)
        downloaded = True

    try:
        if document_path.lower().endswith(".pdf"):
            images = convert_from_path(document_path)
            return "\n".join(run_ocr_on_image(img) for img in images).strip()

        return run_ocr_on_image(Image.open(document_path))

    finally:
        if downloaded:
            try:
                os.remove(document_path)
            except Exception:
                pass