from __future__ import annotations

import os
import unittest

from expense_tracker import i18n


class I18nTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("EXPENSE_LOCALE", None)

    def test_get_locale_default_en(self) -> None:
        os.environ.pop("EXPENSE_LOCALE", None)
        self.assertEqual(i18n.get_locale(), "en")

    def test_get_locale_es(self) -> None:
        os.environ["EXPENSE_LOCALE"] = "es"
        self.assertEqual(i18n.get_locale(), "es")

    def test_get_locale_invalid_falls_back_en(self) -> None:
        os.environ["EXPENSE_LOCALE"] = "fr"
        self.assertEqual(i18n.get_locale(), "en")

    def test_month_name_en(self) -> None:
        os.environ["EXPENSE_LOCALE"] = "en"
        self.assertEqual(i18n.month_name(6), "June")

    def test_month_name_es(self) -> None:
        os.environ["EXPENSE_LOCALE"] = "es"
        self.assertEqual(i18n.month_name(6), "Junio")

    def test_t_by_category_en(self) -> None:
        os.environ["EXPENSE_LOCALE"] = "en"
        self.assertEqual(i18n.t("by_category"), "By category")

    def test_frequency_label_monthly_en(self) -> None:
        self.assertEqual(i18n.frequency_label("monthly", "en"), "monthly")

    def test_frequency_label_monthly_es(self) -> None:
        self.assertEqual(i18n.frequency_label("monthly", "es"), "mensual")

    def test_frequency_label_weekly_es(self) -> None:
        self.assertEqual(i18n.frequency_label("weekly", "es"), "semanal")

    def test_frequency_label_yearly_es(self) -> None:
        self.assertEqual(i18n.frequency_label("yearly", "es"), "anual")

    def test_frequency_label_unknown_frequency_returns_key(self) -> None:
        self.assertEqual(i18n.frequency_label("biweekly", "en"), "biweekly")

    def test_frequency_label_invalid_locale_falls_back_en(self) -> None:
        self.assertEqual(i18n.frequency_label("monthly", "fr"), "monthly")


if __name__ == "__main__":
    unittest.main()
