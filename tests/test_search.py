import unittest

from mfc_app.services.search import extract_service_terms, normalize_chat_query


class SearchTests(unittest.TestCase):
    def test_normalizes_zagran_pasport(self):
        self.assertIn("загранпаспорт", normalize_chat_query("Как сделать загран паспорт?"))

    def test_adds_official_term(self):
        terms = extract_service_terms("Сколько стоит загранпаспорт?")
        self.assertIn("за пределами территории российской федерации", terms)

    def test_normalizes_driver_license(self):
        terms = extract_service_terms("Как поменять права?")
        self.assertIn("водительское удостоверение", terms)


if __name__ == "__main__":
    unittest.main()
