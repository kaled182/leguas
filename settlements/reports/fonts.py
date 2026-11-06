"""Embute a fonte dos PDF.

O reportlab não embute a Helvetica no PDF. Cada leitor usa a sua cópia,
e no Pré-visualizar do macOS o "€" fica por cima do 1.º algarismo.
A Liberation Sans tem as mesmas medidas da Helvetica. Registada com os
nomes "Helvetica*", entra no PDF e o layout fica igual.
"""
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = "/usr/share/fonts/truetype/liberation"
FACES = {
    "Helvetica": "LiberationSans-Regular.ttf",
    "Helvetica-Bold": "LiberationSans-Bold.ttf",
    "Helvetica-Oblique": "LiberationSans-Italic.ttf",
    "Helvetica-BoldOblique": "LiberationSans-BoldItalic.ttf",
}


def embed_helvetica():
    """Troca a Helvetica pela Liberation Sans. Sem os ficheiros, não faz nada."""
    paths = {name: os.path.join(FONT_DIR, f) for name, f in FACES.items()}
    if not all(os.path.exists(p) for p in paths.values()):
        return False
    for name, path in paths.items():
        # registerFont ignora uma fonte TTF com um nome já em cache.
        pdfmetrics._fonts.pop(name, None)
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily(
        "Helvetica", normal="Helvetica", bold="Helvetica-Bold",
        italic="Helvetica-Oblique", boldItalic="Helvetica-BoldOblique",
    )
    return True
