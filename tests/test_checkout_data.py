import os
import unittest
from unittest.mock import patch

from checkout_data import CheckoutData, load_checkout_data


class CheckoutDataTests(unittest.TestCase):
    def test_empty_configuration_does_not_require_personal_data(self):
        with patch.dict(os.environ, {}, clear=True), patch("checkout_data._read_env_file", return_value={}):
            self.assertEqual(load_checkout_data(), CheckoutData())

    def test_explicit_environment_values_are_loaded(self):
        with patch.dict(
            os.environ,
            {"CHECKOUT_NAME": "Pessoa Exemplo", "CHECKOUT_CPF": "00000000000"},
            clear=True,
        ), patch("checkout_data._read_env_file", return_value={}):
            data = load_checkout_data()
        self.assertEqual(data.name, "Pessoa Exemplo")
        self.assertEqual(data.cpf, "00000000000")
        self.assertEqual(data.email, "")


if __name__ == "__main__":
    unittest.main()
