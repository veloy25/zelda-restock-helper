"""Leitura local opcional dos dados de contato para preencher o checkout."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckoutData:
    name: str = ""
    email: str = ""
    phone: str = ""
    cpf: str = ""
    postal_code: str = ""
    address: str = ""
    address_number: str = ""
    complement: str = ""
    district: str = ""
    city: str = ""
    state: str = ""


ENV_FIELDS = {
    "name": "CHECKOUT_NAME",
    "email": "CHECKOUT_EMAIL",
    "phone": "CHECKOUT_PHONE",
    "cpf": "CHECKOUT_CPF",
    "postal_code": "CHECKOUT_POSTAL_CODE",
    "address": "CHECKOUT_ADDRESS",
    "address_number": "CHECKOUT_ADDRESS_NUMBER",
    "complement": "CHECKOUT_COMPLEMENT",
    "district": "CHECKOUT_DISTRICT",
    "city": "CHECKOUT_CITY",
    "state": "CHECKOUT_STATE",
}


def _read_env_file() -> dict[str, str]:
    """Lê pares simples CHAVE=VALOR do .env sem depender de pacote externo."""
    path = Path(__file__).with_name(".env")
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or key.strip() not in ENV_FIELDS.values():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = value.split(" #", maxsplit=1)[0].rstrip()
        values[key.strip()] = value
    return values


def load_checkout_data() -> CheckoutData:
    """Lê .env da pasta do projeto; variáveis já exportadas têm prioridade."""
    file_values = _read_env_file()
    return CheckoutData(**{
        field: os.getenv(key, file_values.get(key, "")).strip()
        for field, key in ENV_FIELDS.items()
    })


FIELD_PATTERNS = {
    "name": re.compile(r"\b(nome|name|comprador|destinat[aá]rio)\b", re.I),
    "email": re.compile(r"\b(e-?mail|correio eletr[oô]nico)\b", re.I),
    "phone": re.compile(r"\b(telefone|celular|phone|whats ?app)\b", re.I),
    "cpf": re.compile(r"\bcpf\b", re.I),
    "postal_code": re.compile(r"\b(cep|c[oó]digo postal|postal.?code)\b", re.I),
    "address": re.compile(r"\b(endere[cç]o|logradouro|address|rua|avenida)\b", re.I),
    "address_number": re.compile(r"\b(n[uú]mero|number|n[uú]m\.?|nº)\b", re.I),
    "complement": re.compile(r"\b(complemento|complement)\b", re.I),
    "district": re.compile(r"\b(bairro|distrito|neighborhood)\b", re.I),
    "city": re.compile(r"\b(cidade|munic[ií]pio|city)\b", re.I),
    "state": re.compile(r"\b(estado|uf|state)\b", re.I),
}
PAYMENT_FIELD = re.compile(r"(cart[aã]o|card|cvv|cvc|seguran[cç]a|validade|expira|senha|password)", re.I)


def fill_visible_personal_fields(page, data: CheckoutData) -> list[str]:
    """Preenche somente campos pessoais visíveis identificados sem ambiguidade.

    Campos de pagamento, senha, CVV e campos ocultos nunca são preenchidos.
    Retorna a lista dos tipos de campo preenchidos para exibição ao usuário.
    """
    filled: list[str] = []
    used_values: set[tuple[str, str]] = set()
    controls = page.locator("input:visible, textarea:visible")
    for index in range(controls.count()):
        control = controls.nth(index)
        metadata = control.evaluate(
            """el => {
                const labels = el.labels ? Array.from(el.labels).map(x => x.innerText).join(' ') : '';
                const parentLabel = el.closest('label')?.innerText || '';
                return [labels, parentLabel, el.getAttribute('aria-label'), el.placeholder,
                        el.name, el.id, el.autocomplete, el.type].filter(Boolean).join(' ');
            }"""
        )
        if PAYMENT_FIELD.search(metadata):
            continue

        matches = [key for key, pattern in FIELD_PATTERNS.items() if pattern.search(metadata)]
        if len(matches) != 1:
            continue
        key = matches[0]
        value = getattr(data, key)
        if not value or (key, value) in used_values:
            continue
        control.fill(value)
        filled.append(key)
        used_values.add((key, value))
    return filled
