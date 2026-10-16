import unittest

from product_response import inspect_product_html


PRODUCT_ID = "403769646"
BASE_URL = "https://www.gamerhut.com.br/the-legend-of-zelda-ocarina-of-time-switch-2-br-midia-fisica"


def page(action: str, extra: str = "") -> str:
    return f"""<html><body>
      <div class="produto-detalhes-detalhes">
        <h1 class="nome-produto titulo">The Legend Of Zelda Ocarina Of Time Switch 2 BR Midia Fisica</h1>
        <div class="acoes-produto SKU-045496907877 pp-{PRODUCT_ID}" data-produto-id="{PRODUCT_ID}">
          <div class="precos-wrap"><meta itemprop="price" content="449.97">
            {action}
          </div>
        </div>
        <div class="descricao">1 (um) Capa FOIL EXCLUSIVA da pré-venda</div>
      </div>
      {extra}
    </body></html>"""


class ProductResponseTests(unittest.TestCase):
    def test_test_mode_can_select_alternate_product_by_sku_without_foil_rule(self):
        test_sku = "045496598075"
        test_product_id = "222222222"
        html = f'''<html><body>
          <h1 class="nome-produto">Nintendo Switch Sports Switch Midia Fisica</h1>
          <div class="acoes-produto SKU-{test_sku}" data-produto-id="{test_product_id}">
            <meta itemprop="availability" content="http://schema.org/InStock">
            <meta itemprop="price" content="319.97">
            <input name="qtde-carrinho" value="1">
            <a class="botao-comprar" href="/carrinho/produto/{test_product_id}/adicionar">Comprar</a>
          </div>
          <div class="acoes-produto SKU-999" data-produto-id="999">
            <a class="botao-comprar" href="/carrinho/produto/999/adicionar">Outro produto</a>
          </div>
        </body></html>'''

        result = inspect_product_html(
            html,
            "https://www.gamerhut.com.br/nintendo-switch-sports",
            expected_sku=test_sku,
            expected_title="nintendo switch sports switch",
            require_foil=False,
        )

        self.assertTrue(result.available)
        self.assertEqual(result.product_id, test_product_id)
        self.assertEqual(result.price, "R$ 319,97")
        self.assertEqual(
            result.add_to_cart_url,
            f"https://www.gamerhut.com.br/carrinho/produto/{test_product_id}/adicionar",
        )

    def test_detects_in_stock_from_target_product_purchase_link(self):
        html = page(
            '<meta itemprop="availability" content="http://schema.org/InStock">'
            f'<a class="botao botao-comprar principal" href="/carrinho/produto/{PRODUCT_ID}/adicionar">Comprar</a>'
        )
        result = inspect_product_html(html, BASE_URL, PRODUCT_ID)
        self.assertTrue(result.available)
        self.assertEqual(result.product_id, PRODUCT_ID)
        self.assertEqual(result.price, "R$ 449,97")
        self.assertEqual(
            result.add_to_cart_url,
            f"https://www.gamerhut.com.br/carrinho/produto/{PRODUCT_ID}/adicionar",
        )

    def test_out_of_stock_marker_wins_without_add_button(self):
        html = page(
            '<meta itemprop="availability" content="http://schema.org/OutOfStock">',
            f'<a class="botao botao-comprar" href="/carrinho/produto/{PRODUCT_ID}/adicionar">Comprar</a>',
        ).replace("acoes-produto SKU-", "acoes-produto indisponivel SKU-")
        result = inspect_product_html(html, BASE_URL, PRODUCT_ID)
        self.assertFalse(result.available)

    def test_ignores_related_product_purchase_link(self):
        html = page(
            '<meta itemprop="availability" content="http://schema.org/InStock">',
            '<div class="acoes-produto" data-produto-id="999"><a class="botao-comprar" '
            'href="/carrinho/produto/999/adicionar">Comprar</a></div>',
        )
        result = inspect_product_html(html, BASE_URL, PRODUCT_ID)
        self.assertFalse(result.available)

    def test_rejects_add_url_from_another_origin(self):
        html = page(
            '<meta itemprop="availability" content="http://schema.org/InStock">'
            f'<a class="botao-comprar" href="https://example.com/carrinho/produto/{PRODUCT_ID}/adicionar">Comprar</a>'
        )
        result = inspect_product_html(html, BASE_URL, PRODUCT_ID)
        self.assertFalse(result.available)

    def test_refuses_quantity_above_one(self):
        html = page(
            '<meta itemprop="availability" content="http://schema.org/InStock">'
            f'<input type="number" name="qtde-carrinho" value="2">'
            f'<a class="botao-comprar" href="/carrinho/produto/{PRODUCT_ID}/adicionar">Comprar</a>'
        )
        result = inspect_product_html(html, BASE_URL, PRODUCT_ID)
        self.assertFalse(result.available)
        self.assertEqual(result.quantity, 2)


if __name__ == "__main__":
    unittest.main()
