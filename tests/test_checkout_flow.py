"""Testa o fluxo real do script em uma loja local fictícia, sem acessar a Gamer Hut."""

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest
from unittest.mock import MagicMock, Mock, patch

from playwright.sync_api import sync_playwright

from checkout_data import CheckoutData
from config import PRODUCT_ID, PRODUCT_URL
import watcher


TITLE = "The Legend Of Zelda Ocarina Of Time Switch 2 BR Midia Fisica"
TEST_TITLE = "Nintendo Switch Sports Switch Midia Fisica"
TEST_SKU = "045496598075"
TEST_PRODUCT_ID = "222222222"


class ShopHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path in {"/add", "/add-test"}:
            self.server.add_count += 1
            self.send_response(302)
            self.send_header("Set-Cookie", "cart=1; Path=/; SameSite=Lax")
            self.send_header("Location", "/carrinho/index")
            self.end_headers()
            return
        if self.path == "/product":
            html = f'''<h1 class="nome-produto">{TITLE}</h1>
                <div class="acoes-produto disponivel" data-produto-id="{PRODUCT_ID}">
                  <meta itemprop="availability" content="http://schema.org/InStock">
                  <meta itemprop="price" content="449.97">
                  <input name="qtde-carrinho" value="1">
                  <a class="botao-comprar" href="https://www.gamerhut.com.br/carrinho/produto/{PRODUCT_ID}/adicionar">Comprar</a>
                </div>
                <div>Capa FOIL EXCLUSIVA da pré-venda</div>
                <div class="acoes-produto" data-produto-id="999">
                  <a class="botao-comprar" href="/carrinho/produto/999/adicionar">Adicionar</a>
                </div>'''
        elif self.path == "/product-test":
            html = f'''<h1 class="nome-produto">{TEST_TITLE}</h1>
                <div class="acoes-produto disponivel SKU-{TEST_SKU}" data-produto-id="{TEST_PRODUCT_ID}">
                  <meta itemprop="availability" content="http://schema.org/InStock">
                  <meta itemprop="price" content="339.97">
                  <input name="qtde-carrinho" value="1">
                  <a class="botao-comprar" href="https://www.gamerhut.com.br/carrinho/produto/{TEST_PRODUCT_ID}/adicionar">Comprar</a>
                </div>'''
        elif self.path == "/carrinho/index":
            if "cart=1" not in self.headers.get("Cookie", ""):
                html = "Carrinho vazio"
            else:
                html = f'''<p>{self.server.cart_title}</p>
                    <button onclick="location.href='/checkout'">
                      <i>&#xf00c;</i> Finalizar compra
                    </button>'''
        elif self.path == "/checkout":
            html = f'''<h3>Para continuar, informe seu e-mail</h3>
                <input type="email" placeholder="meu@email.com.br">
                <p>{self.server.cart_title} — Quantidade: 1</p>'''
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


class CheckoutFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ShopHandler)
        cls.server.add_count = 0
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.server.add_count = 0
        self.server.cart_title = TITLE

    def tearDown(self):
        self.context.close()

    def test_poll_and_fetch_add_open_checkout_with_icon_and_shared_cookie(self):
        product_url = self.base_url + "/product"
        self.page.goto(product_url)
        with patch("watcher.PRODUCT_URL", product_url), patch(
            "watcher.load_checkout_data", return_value=CheckoutData()
        ):
            snapshot = watcher.poll_product(self.page, PRODUCT_ID)
            self.assertTrue(snapshot.available)
            self.assertEqual(self.page.url, product_url)
            # Apenas a URL da loja fictícia é acionada; não há requisição externa de carrinho.
            snapshot = replace(snapshot, add_to_cart_url=self.base_url + "/add")
            watcher.add_unit_and_open_checkout(self.page, snapshot)
            self.assertEqual(self.page.url, self.base_url + "/checkout")
            self.assertEqual(self.server.add_count, 1)
            self.assertEqual(self.page.locator("input[type=email]").input_value(), "")

    def test_ambiguous_finalize_buttons_do_not_trigger_navigation(self):
        self.page.set_content('''<button><i>&#xf00c;</i> Finalizar compra</button>
            <button>Finalizar compra</button>''')
        self.assertFalse(watcher.click_unique_visible_action(self.page, {"finalizar compra"}))

    def test_test_product_can_reach_local_checkout_without_loading_env(self):
        product_url = self.base_url + "/product-test"
        self.page.goto(product_url)
        self.server.cart_title = TEST_TITLE
        with patch("watcher.load_checkout_data", side_effect=AssertionError(".env não deve ser lido")):
            snapshot = watcher.poll_product(
                self.page,
                product_id=None,
                product_url=product_url,
                expected_sku=TEST_SKU,
                expected_title="nintendo switch sports switch",
                require_foil=False,
            )
            self.assertTrue(snapshot.available)
            snapshot = replace(snapshot, add_to_cart_url=self.base_url + "/add-test")
            watcher.add_unit_and_open_checkout(
                self.page,
                snapshot,
                product_url=product_url,
                cart_item_marker="nintendo switch sports",
                fill_personal_data=False,
            )

        self.assertEqual(self.page.url, self.base_url + "/checkout")
        self.assertEqual(self.server.add_count, 1)
        self.assertEqual(self.page.locator("input[type=email]").input_value(), "")


class SingleAttemptTests(unittest.TestCase):
    def test_test_flag_uses_immediate_mode(self):
        playwright = Mock()
        manager = MagicMock()
        manager.__enter__.return_value = playwright
        with patch("watcher.sync_playwright", return_value=manager), patch(
            "watcher.run_test_mode", return_value=0
        ) as run_test:
            self.assertEqual(watcher.main(["--test"]), 0)
        run_test.assert_called_once_with(playwright)

    def test_uncertain_add_result_is_not_repeated(self):
        page = Mock()
        snapshot = Mock(price="R$ 449,97")
        with patch("watcher.add_unit_and_open_checkout", side_effect=TimeoutError("resposta incerta")) as add, patch(
            "watcher.notify_user"
        ), patch("builtins.input", return_value=""):
            self.assertEqual(watcher.assist_once(page, snapshot), 0)
        add.assert_called_once_with(
            page,
            snapshot,
            product_url=PRODUCT_URL,
            cart_item_marker="the legend of zelda ocarina of time",
            fill_personal_data=True,
        )
        page.goto.assert_called_once()


if __name__ == "__main__":
    unittest.main()
