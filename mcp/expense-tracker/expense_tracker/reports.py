from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from . import i18n
from . import repositories as repo
from .db import get_db_path

ChartType = Literal["by_category", "by_project", "monthly_trend", "top_expenses"]
ReportPeriod = Literal["month", "year", "project"]


def _exports_dir() -> Path:
    base = get_db_path().parent
    path = base / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _charts_dir() -> Path:
    base = get_db_path().parent
    path = base / "charts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _format_money(amount: float, currency: str = "ARS") -> str:
    rounded = int(round(amount))
    if i18n.get_locale() == "en":
        text = f"{rounded:,}"
    else:
        text = f"{rounded:,}".replace(",", ".")
    if currency == "ARS":
        return f"${text}"
    return f"{text} {currency}"


def _ascii_bar(label: str, value: float, max_value: float, width: int = 20) -> str:
    if max_value <= 0:
        fill = 0
    else:
        fill = max(1, int(round((value / max_value) * width))) if value > 0 else 0
    bar = "█" * fill + "░" * (width - fill)
    return f"{label[:18]:<18} {bar} {_format_money(value)}"


def _default_year_month() -> tuple[int, int]:
    today = date.today()
    return today.year, today.month


def generate_report(
    *,
    period: ReportPeriod = "month",
    year: int | None = None,
    month: int | None = None,
    project: str | int | None = None,
    currency: str | None = None,
    include_ascii_charts: bool = True,
) -> dict[str, Any]:
    default_year, default_month = _default_year_month()
    year = year or default_year
    month = month or default_month

    if period == "project":
        if project is None:
            raise repo.ValidationError("project is required when period='project'")
        summary = repo.project_summary(project, currency=currency)
        top = repo.top_expenses(limit=5, project=project, currency=currency)
        budgets = None
        period_info = {"type": "project", "project": summary["project"]}
        title = i18n.t("report_project", name=summary["project"]["name"])
        total = summary["total_amount"]
        count = summary["expense_count"]
        by_category = summary["by_category"]
        by_project = []
    elif period == "year":
        summary = repo.yearly_summary(year, project=project, currency=currency)
        top = repo.top_expenses(limit=5, year=year, project=project, currency=currency)
        budgets = None
        period_info = {"year": year}
        title = i18n.t("report_year", year=year)
        total = summary["total_amount"]
        count = summary["expense_count"]
        by_category = summary["by_category"]
        by_project = summary["by_project"]
    else:
        summary = repo.monthly_summary(year, month, project=project, currency=currency)
        top = repo.top_expenses(limit=5, year=year, month=month, project=project, currency=currency)
        budgets = repo.budget_status(year, month, alerts_only=True)
        period_info = summary["period"]
        title = i18n.t("report_month", month=i18n.month_name(month), year=year)
        total = summary["total_amount"]
        count = summary["expense_count"]
        by_category = summary["by_category"]
        by_project = summary["by_project"]

    caller = repo.get_caller_slug()
    lines = [title, ""]

    if caller:
        lines.append(f"{i18n.t('member')}: {caller}")
    if project and period != "project":
        lines.append(f"{i18n.t('project_filter')}: {project}")
    lines.append(i18n.t("total_line", amount=_format_money(total), count=count))
    lines.append("")

    if by_category:
        lines.append(i18n.t("by_category"))
        max_cat = max((row["total"] for row in by_category), default=0)
        for row in by_category[:10]:
            label = row.get("parent_category") or row.get("category") or row.get("category_slug", "")
            if include_ascii_charts:
                lines.append(_ascii_bar(str(label), float(row["total"]), float(max_cat)))
            else:
                lines.append(f"- {label}: {_format_money(row['total'])} ({row['count']})")
        lines.append("")

    if by_project:
        lines.append(i18n.t("by_project"))
        max_proj = max((row["total"] for row in by_project), default=0)
        for row in by_project[:10]:
            name = row.get("project") or i18n.t("no_project")
            if include_ascii_charts:
                lines.append(_ascii_bar(str(name), float(row["total"]), float(max_proj)))
            else:
                lines.append(f"- {name}: {_format_money(row['total'])} ({row['count']})")
        lines.append("")

    if period == "month" and summary.get("by_person"):
        lines.append(i18n.t("attributed_by_person"))
        for row in summary["by_person"][:10]:
            lines.append(f"- {row['person']}: {_format_money(row['attributed_total'])}")
        lines.append("")

    if top.get("items"):
        lines.append(i18n.t("top_expenses"))
        for item in top["items"]:
            proj = ""
            if item.get("project"):
                proj = f" · {item['project']['name']}"
            lines.append(
                f"- {item['expense_date']} · {item['description'][:40]} · "
                f"{_format_money(item['amount'])}{proj}"
            )
        lines.append("")

    if budgets and budgets.get("alerts"):
        lines.append(i18n.t("budget_alerts"))
        for item in budgets["alerts"]:
            lines.append(
                f"- {item['category_name']}: {_format_money(item['spent'])} / "
                f"{_format_money(item['budgeted'])} ({item['percent_used']:.0f}%)"
            )
        lines.append("")

    markdown = "\n".join(lines).strip()
    return {
        "period": period_info,
        "title": title,
        "total_amount": total,
        "expense_count": count,
        "markdown": markdown,
        "summary": summary,
        "top_expenses": top,
        "budget_alerts": budgets.get("alerts") if budgets else [],
        "locale": i18n.get_locale(),
    }


def export_expenses_to_file(
    export_format: Literal["csv", "json"] = "csv",
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
    limit: int = 5000,
) -> dict[str, Any]:
    exported = repo.export_expenses(
        export_format=export_format,
        start_date=start_date,
        end_date=end_date,
        category=category,
        project=project,
        paid_by=paid_by,
        allocated_to=allocated_to,
        currency=currency,
        limit=limit,
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug_bits = [export_format, stamp]
    if project:
        slug_bits.insert(0, _slugify(str(project)))
    filename = f"expenses_{'_'.join(slug_bits)}.{export_format}"
    path = _exports_dir() / filename
    path.write_text(exported["content"], encoding="utf-8")
    return {
        **exported,
        "file_path": str(path),
        "filename": filename,
    }


def _slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-") or "report"


def _chart_rows_for_type(
    chart_type: ChartType,
    *,
    year: int,
    month: int | None,
    project: str | int | None,
    currency: str | None,
) -> tuple[str, list[tuple[str, float]]]:
    if chart_type == "by_category":
        if month is not None:
            summary = repo.monthly_summary(year, month, project=project, currency=currency)
            title = i18n.t(
                "chart_by_category_month",
                month=i18n.month_name(month),
                year=year,
            )
            rows = [
                (str(r.get("parent_category") or r.get("category") or r["category_slug"]), float(r["total"]))
                for r in summary["by_category"]
            ]
        else:
            summary = repo.yearly_summary(year, project=project, currency=currency)
            title = i18n.t("chart_by_category_year", year=year)
            rows = [
                (str(r.get("parent_category") or r.get("category") or r["category_slug"]), float(r["total"]))
                for r in summary["by_category"]
            ]
        return title, rows

    if chart_type == "by_project":
        if month is not None:
            summary = repo.monthly_summary(year, month, project=project, currency=currency)
            title = i18n.t(
                "chart_by_project_month",
                month=i18n.month_name(month),
                year=year,
            )
            rows = [(str(r["project"]), float(r["total"])) for r in summary["by_project"]]
        else:
            summary = repo.yearly_summary(year, project=project, currency=currency)
            title = i18n.t("chart_by_project_year", year=year)
            rows = [(str(r["project"]), float(r["total"])) for r in summary["by_project"]]
        return title, rows

    if chart_type == "monthly_trend":
        summary = repo.yearly_summary(year, project=project, currency=currency)
        title = i18n.t("chart_monthly_trend", year=year)
        by_month: dict[int, float] = {}
        for row in summary["by_month"]:
            month_key = row.get("month") or row.get("period", "")
            if isinstance(month_key, str) and "-" in month_key:
                month_num = int(month_key.split("-")[1])
            else:
                month_num = int(str(month_key).lstrip("0") or "0")
            by_month[month_num] = float(row["total"])
        rows = [(i18n.month_name(m)[:3], by_month.get(m, 0.0)) for m in range(1, 13)]
        return title, rows

    if chart_type == "top_expenses":
        top = repo.top_expenses(
            limit=8,
            year=year if month is None else None,
            month=month,
            project=project,
            currency=currency,
            sort_by="amount_desc",
        )
        label = f"{i18n.month_name(month)} {year}" if month else str(year)
        title = i18n.t("chart_top_expenses", label=label)
        rows = [
            (f"{item['description'][:22]}…" if len(item["description"]) > 23 else item["description"], float(item["amount"]))
            for item in top["items"]
        ]
        return title, rows

    raise repo.ValidationError(f"Unknown chart_type: {chart_type}")


def render_chart(
    chart_type: ChartType,
    *,
    year: int | None = None,
    month: int | None = None,
    project: str | int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise repo.ValidationError(
            "matplotlib is required for charts. Run: pip install matplotlib"
        ) from exc

    default_year, default_month = _default_year_month()
    year = year or default_year
    chart_month: int | None = month
    if chart_type == "monthly_trend":
        chart_month = None
    elif chart_type == "top_expenses" and chart_month is None:
        chart_month = default_month

    title, rows = _chart_rows_for_type(
        chart_type,
        year=year,
        month=chart_month,
        project=project,
        currency=currency,
    )
    rows = [(label, value) for label, value in rows if value > 0]
    if not rows:
        raise repo.ValidationError(i18n.t("no_chart_data"))

    labels, values = zip(*rows)
    fig, ax = plt.subplots(figsize=(10, 6), dpi=120)
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fafafa")

    if chart_type == "by_category":
        ax.pie(values, labels=labels, autopct=lambda pct: f"{pct:.0f}%", startangle=90)
        ax.axis("equal")
    elif chart_type == "monthly_trend":
        ax.plot(labels, values, marker="o", color="#2563eb", linewidth=2)
        ax.fill_between(range(len(values)), values, alpha=0.15, color="#2563eb")
        ax.set_ylabel("ARS")
        plt.xticks(rotation=45, ha="right")
    else:
        y_pos = range(len(labels))
        ax.barh(list(y_pos), values, color="#2563eb")
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlabel("ARS")

    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    plt.tight_layout()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chart_{chart_type}_{year}{f'_{month:02d}' if month else ''}_{stamp}.png"
    path = _charts_dir() / filename
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return {
        "chart_type": chart_type,
        "title": title,
        "file_path": str(path),
        "filename": filename,
        "row_count": len(rows),
        "locale": i18n.get_locale(),
    }
