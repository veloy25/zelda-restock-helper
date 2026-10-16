"""Interpreta a resposta HTML da página sem navegar a aba visível."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


PRICE_PATTERN = re.compile(r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}")
PRODUCT_TITLE = re.compile(r"the legend of zelda ocarina of time", re.I)
FOIL_COPY = re.compile(r"capa\s+foil\s+exclusiva", re.I)


@dataclass(frozen=True)
class ProductSnapshot:
    available: bool
    product_id: str | None
    price: str | None
    add_to_cart_url: str | None
    quantity: int | None
    correct_edition: bool
    reason: str


class _ProductHTMLParser(HTMLParser):
    def __init__(self, expected_product_id: str | None, expected_sku: str | None = None):
        super().__init__(convert_charrefs=True)
        self.expected_product_id = expected_product_id
        self.expected_sku = expected_sku
        self.product_id: str | None = None
        self.action_classes: set[str] = set()
        self.action_depth: int | None = None
        self.action_text: list[str] = []
        self.add_path: str | None = None
        self.quantity: int | None = None
        self.availability: str | None = None
        self.meta_price: str | None = None
        self.title_text: list[str] = []
        self.in_title = False
        self.skip_depth = 0
        self.stack: list[str] = []
        self.body_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        if tag == "div" and "acoes-produto" in classes:
            candidate_id = attr.get("data-produto-id")
            if self.expected_product_id is not None:
                is_target = candidate_id == self.expected_product_id
            elif self.expected_sku is not None:
                is_target = f"SKU-{self.expected_sku}" in classes
            else:
                is_target = True
            if is_target:
                self.product_id = candidate_id
                self.action_classes = classes
                self.action_depth = len(self.stack) + 1
        if self.action_depth is not None and tag == "meta":
            itemprop = attr.get("itemprop", "").casefold()
            content = attr.get("content", "") or ""
            if itemprop == "availability":
                self.availability = content.rsplit("/", maxsplit=1)[-1]
            elif itemprop == "price":
                self.meta_price = content
        if self.action_depth is not None and tag == "input" and attr.get("name") == "qtde-carrinho":
            try:
                self.quantity = int(attr.get("value", "1"))
            except ValueError:
                self.quantity = None
        if self.action_depth is not None and tag == "a" and "botao-comprar" in classes:
            href = attr.get("href")
            if href:
                absolute_href = urljoin("https://www.gamerhut.com.br/", href)
                parsed_href = urlparse(absolute_href)
                path = parsed_href.path
                if re.fullmatch(r"/carrinho/produto/\d+/adicionar/?", path):
                    path_product_id = re.search(r"/produto/(\d+)/", path)
                    if (
                        parsed_href.scheme == "https"
                        and parsed_href.netloc == "www.gamerhut.com.br"
                        and path_product_id
                        and path_product_id.group(1) == self.product_id
                    ):
                        self.add_path = absolute_href

        if tag == "h1" and "nome-produto" in classes:
            self.in_title = True
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.in_title = False
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index] == tag:
                del self.stack[index:]
                break
        if self.action_depth is not None and len(self.stack) < self.action_depth:
            self.action_depth = None

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self.in_title:
            self.title_text.append(data)
        self.body_text.append(data)
        if self.action_depth is not None:
            self.action_text.append(data)


def inspect_product_html(
    html: str,
    base_url: str,
    expected_product_id: str | None = None,
    *,
    expected_sku: str | None = None,
    expected_title: str | re.Pattern[str] = PRODUCT_TITLE,
    require_foil: bool = True,
) -> ProductSnapshot:
    """Detecta a oferta no bloco do produto, exigindo o link real de compra."""
    parser = _ProductHTMLParser(expected_product_id, expected_sku)
    parser.feed(html)
    all_text = " ".join(" ".join(parser.body_text).split())
    action_text = " ".join(" ".join(parser.action_text).split())
    title = " ".join(" ".join(parser.title_text).split())
    title_pattern = (
        re.compile(re.escape(expected_title), re.I)
        if isinstance(expected_title, str)
        else expected_title
    )
    title_matches = bool(title_pattern.search(title))
    foil_matches = bool(FOIL_COPY.search(all_text))
    correct_edition = title_matches and (foil_matches or not require_foil)
    price_match = PRICE_PATTERN.search(action_text)
    price = price_match.group(0) if price_match else None
    if not price and parser.meta_price:
        try:
            price = f"R$ {float(parser.meta_price.replace(',', '.')):,.2f}"
            price = price.replace(",", "X").replace(".", ",").replace("X", ".")
        except ValueError:
            price = None
    add_url = urljoin(base_url, parser.add_path) if parser.add_path else None
    marked_available = parser.availability.casefold() in {"instock", "backorder", "preorder"} if parser.availability else True
    available = bool(
        correct_edition
        and parser.product_id
        and "indisponivel" not in {part.casefold() for part in parser.action_classes}
        and marked_available
        and add_url
        and parser.quantity in {None, 1}
    )

    if not title_matches:
        reason = "O título do produto esperado não foi confirmado."
    elif require_foil and not foil_matches:
        reason = "O título e a descrição da edição com capa foil não foram confirmados."
    elif not parser.product_id:
        reason = "O bloco de compra do produto não foi identificado."
    elif (
        "indisponivel" in {part.casefold() for part in parser.action_classes}
        or (parser.availability and not marked_available)
    ):
        reason = "A página ainda marca o produto como indisponível."
    elif parser.quantity not in {None, 1}:
        reason = "A quantidade configurada não é exatamente uma unidade."
    elif not add_url:
        reason = "Não foi encontrado o link de compra dentro do bloco do produto."
    else:
        reason = "Link de compra presente no bloco da edição foil."

    return ProductSnapshot(
        available=available,
        product_id=parser.product_id,
        price=price,
        add_to_cart_url=add_url,
        quantity=parser.quantity,
        correct_edition=correct_edition,
        reason=reason,
    )
