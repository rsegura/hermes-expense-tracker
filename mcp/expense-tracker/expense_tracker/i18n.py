from __future__ import annotations

import os

SUPPORTED_LOCALES = frozenset({"en", "es"})

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "report_month": "Report — {month} {year}",
        "report_year": "Annual report — {year}",
        "report_project": "Report — {name}",
        "member": "Member",
        "project_filter": "Project filter",
        "total_line": "Total: {amount} · {count} expense(s)",
        "total_by_currency": "Total {currency}: {amount} · {count} expense(s)",
        "section_currency": "{currency}",
        "by_category": "By category",
        "by_project": "By project",
        "no_project": "No project",
        "attributed_by_person": "Attributed by person",
        "top_expenses": "Top expenses",
        "budget_alerts": "Budget alerts",
        "chart_by_category_month": "Spending by category — {month} {year}",
        "chart_by_category_year": "Spending by category — {year}",
        "chart_by_project_month": "Spending by project — {month} {year}",
        "chart_by_project_year": "Spending by project — {year}",
        "chart_monthly_trend": "Monthly spending — {year}",
        "chart_top_expenses": "Top expenses — {label}",
        "no_chart_data": "No data to chart for the selected period",
        "month_1": "January",
        "month_2": "February",
        "month_3": "March",
        "month_4": "April",
        "month_5": "May",
        "month_6": "June",
        "month_7": "July",
        "month_8": "August",
        "month_9": "September",
        "month_10": "October",
        "month_11": "November",
        "month_12": "December",
    },
    "es": {
        "report_month": "Reporte — {month} {year}",
        "report_year": "Reporte anual — {year}",
        "report_project": "Reporte — {name}",
        "member": "Miembro",
        "project_filter": "Filtro proyecto",
        "total_line": "Total: {amount} · {count} gasto(s)",
        "total_by_currency": "Total {currency}: {amount} · {count} gasto(s)",
        "section_currency": "{currency}",
        "by_category": "Por categoría",
        "by_project": "Por proyecto",
        "no_project": "Sin proyecto",
        "attributed_by_person": "Atribuido por persona",
        "top_expenses": "Top gastos",
        "budget_alerts": "Alertas de presupuesto",
        "chart_by_category_month": "Gastos por categoría — {month} {year}",
        "chart_by_category_year": "Gastos por categoría — {year}",
        "chart_by_project_month": "Gastos por proyecto — {month} {year}",
        "chart_by_project_year": "Gastos por proyecto — {year}",
        "chart_monthly_trend": "Gasto mensual — {year}",
        "chart_top_expenses": "Top gastos — {label}",
        "no_chart_data": "No hay datos para graficar en el período seleccionado",
        "month_1": "Enero",
        "month_2": "Febrero",
        "month_3": "Marzo",
        "month_4": "Abril",
        "month_5": "Mayo",
        "month_6": "Junio",
        "month_7": "Julio",
        "month_8": "Agosto",
        "month_9": "Septiembre",
        "month_10": "Octubre",
        "month_11": "Noviembre",
        "month_12": "Diciembre",
    },
}


def get_locale() -> str:
    raw = os.getenv("EXPENSE_LOCALE", "en").strip().lower()
    if raw not in SUPPORTED_LOCALES:
        return "en"
    return raw


def t(key: str, **kwargs: str | int) -> str:
    locale = get_locale()
    template = _STRINGS[locale].get(key) or _STRINGS["en"].get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template


def month_name(month: int) -> str:
    return t(f"month_{month}") if 1 <= month <= 12 else str(month)
