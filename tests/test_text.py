import unittest

from mfc_app.utils.text import clean_html


class CleanHtmlTests(unittest.TestCase):
    def test_keeps_readable_lines(self):
        value = "<p>Первая строка</p><p>Вторая<br>строка</p>"
        self.assertEqual(clean_html(value), "Первая строка\nВторая\nстрока")


if __name__ == "__main__":
    unittest.main()
