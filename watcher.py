"""Monitor de disponibilidade com abertura assistida no navegador."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from checkout_data import fill_visible_personal_fields, load_checkout_data
from product_response import ProductSnapshot, inspect_product_html
from config import (
    DROP_CHECK_SECONDS,
    DROP_WINDOW_AFTER_SECONDS,
    DROP_WINDOW_BEFORE_SECONDS,
    DROP_TIMES,
    BROWSER_PROFILE_DIR,
    PRODUCT_ID,
    PRODUCT_URL,
    TEST_CART_ITEM_MARKER,
    TEST_PRODUCT_SKU,
    TEST_PRODUCT_TITLE,
    TEST_PRODUCT_URL,
    WATCH_UNTIL,
)


def open_persistent_browser_context(playwright):
    """Abre Chromium com cookies/localStorage locais entre execuções."""
    return playwright.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_PROFILE_DIR),
        headless=False,
        locale="pt-BR",
    )


def first_or_new_page(context):
    """Reutiliza a aba inicial do perfil ou cria uma quando necessário."""
    return context.pages[0] if context.pages else context.new_page()


def notify_user(price: str | None, product_url: str | None = None) -> None:
    product_url = product_url or PRODUCT_URL
    price_text = price or "Preço não identificado automaticamente"
    print("\n" + "!" * 60)
    print("O produto pode estar disponível na Gamer Hut!")
    print(f"{price_text} — confira o preço e o frete diretamente no site.")
    print(product_url)
    print("Confira se o jogo aparece no carrinho e revise os campos preenchidos.")
    print("Revise os dados e informe manualmente qualquer campo ausente e o pagamento.")
    print("A adição ao carrinho não garante reserva; o programa não envia o pedido.")
    print("!" * 60 + "\n")
    print("\a", end="", flush=True)


def click_unique_visible_action(page, labels: set[str]) -> bool:
    """Clica apenas quando há exatamente uma ação visível com o rótulo esperado."""
    candidates = page.locator(
        "button:visible, a:visible, input[type='button']:visible, input[type='submit']:visible"
    )
    # Um único round trip para todos os rótulos. Ícones não fazem parte do nome da ação.
    candidate_labels = candidates.evaluate_all(
        r"""elements => elements.map(el => {
            const copy = el.cloneNode(true);
            copy.querySelectorAll('i, svg, [aria-hidden="true"]').forEach(x => x.remove());
            const label = el.getAttribute('aria-label') ||
                (el.matches('input') ? el.value : copy.textContent) || '';
            return label.replace(/[\uE000-\uF8FF]/g, '').trim();
        })"""
    )
    matches = []
    for index, label in enumerate(candidate_labels):
        if label and re.sub(r"\s+", " ", label).casefold() in labels:
            matches.append(index)
    if len(matches) != 1:
        return False
    candidates.nth(matches[0]).click(timeout=3_000)
    return True


def poll_product(
    page,
    product_id: str | None,
    *,
    product_url: str | None = None,
    expected_sku: str | None = None,
    expected_title: str | re.Pattern[str] | None = None,
    require_foil: bool = True,
) -> ProductSnapshot:
    """Consulta o HTML por fetch same-origin, sem navegar a aba visível."""
    product_url = product_url or PRODUCT_URL
    if expected_title is None:
        expected_title = "the legend of zelda ocarina of time"
    result = page.evaluate(
        """async url => {
            const response = await fetch(url, {
                method: 'GET',
                cache: 'no-store',
                credentials: 'same-origin',
                headers: {'Cache-Control': 'no-cache, no-store', 'Pragma': 'no-cache'},
                signal: AbortSignal.timeout(10000)
            });
            return {status: response.status, html: await response.text()};
        }""",
        product_url,
    )
    if result["status"] != 200:
        raise RuntimeError(f"Consulta da página respondeu HTTP {result['status']}.")
    return inspect_product_html(
        result["html"],
        product_url,
        product_id,
        expected_sku=expected_sku,
        expected_title=expected_title,
        require_foil=require_foil,
    )


def add_unit_and_open_checkout(
    page,
    snapshot: ProductSnapshot,
    *,
    product_url: str | None = None,
    cart_item_marker: str = "the legend of zelda ocarina of time",
    fill_personal_data: bool = True,
) -> list[str]:
    """Aciona a URL de compra exposta pelo próprio produto, sem recarregar a aba."""
    product_url = product_url or PRODUCT_URL
    if not snapshot.available or not snapshot.add_to_cart_url:
        print("A página indicou disponibilidade, mas não forneceu um link de compra seguro.")
        return []

    add_result = page.evaluate(
        """async url => {
            const response = await fetch(url, {
                method: 'GET', cache: 'no-store', credentials: 'same-origin',
                signal: AbortSignal.timeout(10000)
            });
            return {status: response.status, finalUrl: response.url};
        }""",
        snapshot.add_to_cart_url,
    )
    if add_result["status"] < 200 or add_result["status"] >= 400:
        print(f"A Gamer Hut não confirmou a adição ao carrinho (HTTP {add_result['status']}).")
        return []

    cart_url = urljoin(product_url, "/carrinho/index")
    page.goto(cart_url, wait_until="domcontentloaded", timeout=20_000)
    cart_text = page.locator("body").inner_text(timeout=10_000).casefold()
    if cart_item_marker.casefold() not in cart_text:
        print("O carrinho não confirmou o produto; deixei o carrinho aberto para conferência manual.")
        return []

    if not click_unique_visible_action(page, {"finalizar compra"}):
        print("Não reconheci uma única ação de checkout; o carrinho está aberto para você.")
        return []

    # Aguarda o campo observado no checkout; não assume que o clique já terminou a navegação.
    try:
        page.locator(
            "input[type='email']:visible, input[autocomplete='email']:visible, "
            "input[placeholder*='@']:visible"
        ).first.wait_for(state="visible", timeout=10_000)
    except PlaywrightTimeoutError:
        print("A primeira etapa do checkout não foi confirmada; confira a página manualmente.")
        return []

    if not fill_personal_data:
        print("Modo de teste: deixei os dados pessoais em branco.")
        return []

    data = load_checkout_data()
    filled = fill_visible_personal_fields(page, data)
    if filled:
        print("Campos preenchidos automaticamente: " + ", ".join(filled))
    else:
        print("Nenhum campo pessoal reconhecido; preencha os dados diretamente no checkout.")
    return filled


def assist_once(
    page,
    snapshot: ProductSnapshot,
    *,
    product_url: str | None = None,
    cart_item_marker: str = "the legend of zelda ocarina of time",
    fill_personal_data: bool = True,
) -> int:
    """Uma tentativa de carrinho por execução, inclusive quando a resposta é incerta."""
    product_url = product_url or PRODUCT_URL
    notify_user(snapshot.price, product_url)
    try:
        add_unit_and_open_checkout(
            page,
            snapshot,
            product_url=product_url,
            cart_item_marker=cart_item_marker,
            fill_personal_data=fill_personal_data,
        )
    except Exception as exc:
        print(f"A tentativa de carrinho/checkout falhou: {type(exc).__name__}: {exc}")
        print("Confira o carrinho manualmente: a solicitação não será repetida automaticamente.")
        try:
            page.goto(urljoin(product_url, "/carrinho/index"), wait_until="domcontentloaded", timeout=20_000)
        except Exception:
            pass
    page.bring_to_front()
    if fill_personal_data:
        input("Conclua manualmente no navegador; pressione Enter para encerrar o monitor.")
    else:
        input("Confira a tela sem concluir o pedido; pressione Enter para fechar o teste.")
    return 0


def run_test_mode(playwright) -> int:
    """Abre a página de teste agora, sem esperar o cronograma do Zelda."""
    context = open_persistent_browser_context(playwright)
    try:
        page = first_or_new_page(context)
        print("Modo de teste imediato: Nintendo Switch Sports para Switch.")
        print("O programa fará uma checagem; se ainda estiver disponível, tentará adicionar uma unidade e abrir o checkout.")
        print("Não preencherá o .env nem enviará pedido ou pagamento. Ctrl+C encerra.\n")
        page.goto(TEST_PRODUCT_URL, wait_until="domcontentloaded", timeout=30_000)
        try:
            snapshot = poll_product(
                page,
                product_id=None,
                product_url=TEST_PRODUCT_URL,
                expected_sku=TEST_PRODUCT_SKU,
                expected_title=TEST_PRODUCT_TITLE,
                require_foil=False,
            )
        except Exception as exc:
            print(f"Não consegui confirmar o estoque: {type(exc).__name__}: {exc}")
            print("Nenhuma tentativa de carrinho foi feita.")
            input("Confira a página aberta; pressione Enter para fechar o teste.")
            return 1
        stamp = datetime.now().astimezone().strftime("%H:%M:%S")
        price_text = f" | {snapshot.price}" if snapshot.price else ""
        print(f"[{stamp}] {'DISPONÍVEL' if snapshot.available else 'indisponível'}{price_text}")
        if snapshot.available:
            return assist_once(
                page,
                snapshot,
                product_url=TEST_PRODUCT_URL,
                cart_item_marker=TEST_CART_ITEM_MARKER,
                fill_personal_data=False,
            )
        print("Nenhuma tentativa de carrinho foi feita. Confira a disponibilidade na página aberta.")
        input("Pressione Enter para fechar o teste.")
        return 0
    finally:
        context.close()


def run_scheduled_mode(playwright) -> int:
    print("Aguardando os horários anunciados dos lotes da Gamer Hut.")
    print("O navegador abrirá antes de cada lote e ficará pronto no produto. Ctrl+C encerra.\n")
    for drop in DROP_TIMES:
        now = datetime.now().astimezone()
        burst_start = drop - timedelta(seconds=DROP_WINDOW_BEFORE_SECONDS)
        burst_end = drop + timedelta(seconds=DROP_WINDOW_AFTER_SECONDS)
        if now >= burst_end or now >= WATCH_UNTIL:
            continue

        while now < burst_start:
            wait_seconds = min(30, max(1, int((burst_start - now).total_seconds())))
            time.sleep(wait_seconds)
            now = datetime.now().astimezone()

        if datetime.now().astimezone() >= burst_end:
            continue

        context = open_persistent_browser_context(playwright)
        try:
            page = first_or_new_page(context)
            print(f"Navegador aberto para o lote de {drop.strftime('%d/%m às %H:%M')}.")
            # A aba visível carrega uma vez; as verificações seguintes são HTTP em segundo plano.
            page.goto(PRODUCT_URL, wait_until="domcontentloaded", timeout=30_000)
            product_id = PRODUCT_ID
            print(
                f"Consultas em segundo plano de {burst_start.strftime('%H:%M:%S')} "
                f"a {burst_end.strftime('%H:%M:%S')} (horário de Brasília)."
            )
            while datetime.now().astimezone() < burst_end:
                check_started = time.monotonic()
                try:
                    snapshot = poll_product(page, product_id)
                    stamp = datetime.now().astimezone().strftime("%H:%M:%S")
                    price_text = f" | {snapshot.price}" if snapshot.price else ""
                    print(f"[{stamp}] {'DISPONÍVEL' if snapshot.available else 'indisponível'}{price_text}")
                except Exception as exc:
                    print(f"Falha temporária ao consultar a página: {type(exc).__name__}: {exc}")
                    time.sleep(max(0, DROP_CHECK_SECONDS - (time.monotonic() - check_started)))
                    continue

                if snapshot.available:
                    return assist_once(page, snapshot)

                time.sleep(max(0, DROP_CHECK_SECONDS - (time.monotonic() - check_started)))
        finally:
            context.close()

    print("Horários anunciados verificados. Atualize config.py se houver novos lotes.")
    return 0


def run_login_setup(playwright) -> int:
    """Permite que a pessoa autentique manualmente no perfil persistente."""
    context = open_persistent_browser_context(playwright)
    try:
        page = first_or_new_page(context)
        page.goto("https://www.gamerhut.com.br/", wait_until="domcontentloaded", timeout=30_000)
        page.bring_to_front()
        print("Faça login manualmente na Gamer Hut, se desejar manter sua sessão neste computador.")
        print("A sessão fica no perfil local .browser-profile/. Não informe sua senha ao programa.")
        input("Depois de confirmar o login, pressione Enter para salvar a sessão e fechar.")
        return 0
    finally:
        context.close()

def main(argv: list[str] | None = None) -> int:
    argument_parser = argparse.ArgumentParser(description="Monitor local da Gamer Hut")
    argument_parser.add_argument(
        "--test",
        action="store_true",
        help="abre agora uma página de teste com um produto alternativo",
    )
    argument_parser.add_argument(
        "--login",
        action="store_true",
        help="abre a Gamer Hut para login manual e salvar a sessão localmente",
    )
    args = argument_parser.parse_args(argv)
    if args.test and args.login:
        argument_parser.error("--test e --login não podem ser usados juntos")
    try:
        with sync_playwright() as playwright:
            if args.login:
                return run_login_setup(playwright)
            if args.test:
                return run_test_mode(playwright)
            return run_scheduled_mode(playwright)
    except KeyboardInterrupt:
        print("\nMonitor encerrado pelo usuário.")
        return 130
    except Exception as exc:
        print(f"Não foi possível iniciar o navegador Playwright: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
