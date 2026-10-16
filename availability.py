"""Regras puras para interpretar o texto visível da página do produto."""

import re
from typing import NamedTuple


class PageStatus(NamedTuple):
    available: bool
    price: str | None
    reason: str


UNAVAILABLE_MARKERS = (
    "esse produto encontra-se indisponível",
    "produto encontra-se indisponível",
    "produto indisponível",
)
PURCHASE_MARKER = re.compile(r"\b(comprar|adicionar ao carrinho)\b", re.I)
PRICE_MARKER = re.compile(r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}")
PRODUCT_MARKER = re.compile(r"the legend of zelda ocarina of time", re.I)
RELATED_MARKER = re.compile(r"produtos relacionados", re.I)


def classify_visible_text(text: str) -> PageStatus:
    """Classifica o produto sem contar textos de elementos ocultos."""
    title = PRODUCT_MARKER.search(text)
    if title is None:
        return PageStatus(False, None, "O título do produto não foi reconhecido na página.")

    product_section = text[title.end():]
    related = RELATED_MARKER.search(product_section)
    if related is not None:
        product_section = product_section[:related.start()]

    normalized = " ".join(product_section.casefold().split())
    price_match = PRICE_MARKER.search(product_section)
    price = price_match.group(0) if price_match else None

    for marker in UNAVAILABLE_MARKERS:
        if marker in normalized:
            return PageStatus(False, price, "A página informa que o produto está indisponível.")

    if PURCHASE_MARKER.search(product_section):
        return PageStatus(True, price, "A página apresenta uma ação de compra visível.")

    return PageStatus(False, price, "Não foi encontrado um indicador claro de disponibilidade.")
