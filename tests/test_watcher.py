import unittest

from availability import classify_visible_text


class ClassifyVisibleTextTests(unittest.TestCase):
    def test_unavailable_banner_wins_even_if_other_text_mentions_cart(self):
        result = classify_visible_text(
            "The Legend of Zelda Ocarina of Time. "
            "Ops! Esse produto encontra-se indisponível. "
            "Ir para o carrinho"
        )
        self.assertFalse(result.available)

    def test_visible_buy_action_marks_page_as_available(self):
        result = classify_visible_text(
            "The Legend of Zelda Ocarina of Time. R$ 439,97. Comprar"
        )
        self.assertTrue(result.available)
        self.assertEqual(result.price, "R$ 439,97")

    def test_ambiguous_page_is_not_treated_as_available(self):
        result = classify_visible_text("The Legend of Zelda Ocarina of Time")
        self.assertFalse(result.available)
        self.assertIsNone(result.price)

    def test_empty_cart_link_does_not_count_as_product_availability(self):
        result = classify_visible_text(
            "The Legend of Zelda Ocarina of Time. "
            "Carrinho vazio. Ir para o carrinho."
        )
        self.assertFalse(result.available)

    def test_buy_button_for_related_product_does_not_trigger_alert(self):
        result = classify_visible_text(
            "The Legend of Zelda Ocarina of Time. Indisponível. "
            "Produtos relacionados. Comprar The Legend of Zelda Breath of the Wild."
        )
        self.assertFalse(result.available)

    def test_other_product_page_does_not_trigger_alert(self):
        result = classify_visible_text("Comprar The Legend of Zelda Breath of the Wild")
        self.assertFalse(result.available)

    def test_price_with_thousands_separator_is_extracted(self):
        result = classify_visible_text(
            "The Legend of Zelda Ocarina of Time. Comprar agora por R$ 1.299,90"
        )
        self.assertTrue(result.available)
        self.assertEqual(result.price, "R$ 1.299,90")


if __name__ == "__main__":
    unittest.main()
