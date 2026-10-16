"""Configuração do monitor local da Gamer Hut."""

from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
BROWSER_PROFILE_DIR = PROJECT_DIR / ".browser-profile"

PRODUCT_URL = (
    "https://www.gamerhut.com.br/"
    "the-legend-of-zelda-ocarina-of-time-switch-2-br-midia-fisica"
)
# Identificador do catálogo verificado na página oficial; evita selecionar produtos relacionados.
PRODUCT_ID = "403769646"

# Destino alternativo usado somente com `python watcher.py --test`.
# O SKU identifica o bloco principal do produto sem confundir itens relacionados.
TEST_PRODUCT_URL = (
    "https://www.gamerhut.com.br/"
    "nintendo-switch-sports-switch-midia-fisica"
)
TEST_PRODUCT_SKU = "045496598075"
TEST_PRODUCT_TITLE = "nintendo switch sports switch"
TEST_CART_ITEM_MARKER = "nintendo switch sports"

# O navegador é aberto antes do lote e pré-carrega a página do produto.
# Duas consultas por segundo reduzem a janela de detecção sem abrir instâncias paralelas.
DROP_CHECK_SECONDS = 0.5
DROP_WINDOW_BEFORE_SECONDS = 30
DROP_WINDOW_AFTER_SECONDS = 60

# Próximas aberturas anunciadas pela loja. Todas com fuso explícito de São Paulo.
DROP_TIMES = [
    datetime.fromisoformat("2026-10-16T09:00:00-03:00"),
    datetime.fromisoformat("2026-10-21T21:00:00-03:00"),
    datetime.fromisoformat("2026-10-26T18:00:00-03:00"),
    datetime.fromisoformat("2026-10-31T09:00:00-03:00"),
]

# O monitor termina após o cronograma anunciado. Atualize se houver novos lotes.
WATCH_UNTIL = datetime.fromisoformat("2026-11-01T00:00:00-03:00")
from pathlib import Path

# Perfil Chromium separado do navegador pessoal; mantém cookies entre execuções.
PROJECT_DIR = Path(__file__).resolve().parent
BROWSER_PROFILE_DIR = PROJECT_DIR / ".browser-profile"

