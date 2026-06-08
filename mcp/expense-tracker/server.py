#!/usr/bin/env python3
"""Expense Tracker MCP server for Hermes profiles."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP
from fastmcp.utilities.types import Image

from expense_tracker import reports
from expense_tracker import repositories as repo
from expense_tracker.db import init_db

mcp = FastMCP("expense-tracker")


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, ensure_ascii=False, default=str)


def _err(exc: Exception) -> str:
    kind = "validation_error"
    if isinstance(exc, repo.NotFoundError):
        kind = "not_found"
    elif isinstance(exc, repo.ValidationError):
        kind = "validation_error"
    else:
        kind = "error"
    return json.dumps({"ok": False, "error": {"type": kind, "message": str(exc)}}, ensure_ascii=False)


@mcp.tool()
def create_person(display_name: str, slug: str | None = None, aliases: list[str] | None = None) -> str:
    """Create a person who can pay or be allocated expenses."""
    try:
        return _ok(repo.create_person(display_name, slug=slug, aliases=aliases))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def update_person(
    person_ref: str,
    display_name: str | None = None,
    slug: str | None = None,
    aliases: list[str] | None = None,
) -> str:
    """Update an existing person by id, slug, display name, or alias."""
    try:
        return _ok(repo.update_person(person_ref, display_name=display_name, slug=slug, aliases=aliases))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def list_persons() -> str:
    """List all persons."""
    try:
        return _ok(repo.list_persons())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def delete_person(person_ref: str) -> str:
    """Delete a person if not referenced by any expense."""
    try:
        return _ok(repo.delete_person(person_ref))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def create_project(
    name: str,
    slug: str | None = None,
    description: str | None = None,
    members: list[str] | None = None,
    owner: str | None = None,
) -> str:
    """Create a project. Caller becomes owner; optional members are invited."""
    try:
        return _ok(
            repo.create_project(
                name,
                slug=slug,
                description=description,
                members=members,
                owner=owner,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def update_project(
    project_ref: str,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> str:
    """Update an existing project."""
    try:
        return _ok(
            repo.update_project(
                project_ref,
                name=name,
                slug=slug,
                description=description,
                is_active=is_active,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def list_projects(active_only: bool = False) -> str:
    """List projects visible to the current member."""
    try:
        return _ok(repo.list_projects(active_only=active_only))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def add_project_member(project_ref: str, person_ref: str) -> str:
    """Invite a person to a project. Only the project owner can add members."""
    try:
        return _ok(repo.add_project_member(project_ref, person_ref))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def remove_project_member(project_ref: str, person_ref: str) -> str:
    """Remove a person from a project. Only the project owner can remove members."""
    try:
        return _ok(repo.remove_project_member(project_ref, person_ref))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def list_project_members(project_ref: str) -> str:
    """List members and roles for a project. Caller must be a member."""
    try:
        return _ok(repo.list_project_members(project_ref))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def delete_project(project_ref: str, force: bool = False) -> str:
    """Delete a project. Use force=true to unlink expenses instead of blocking."""
    try:
        return _ok(repo.delete_project(project_ref, force=force))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def create_category(name: str, slug: str | None = None, parent_id: int | None = None) -> str:
    """Create an expense category."""
    try:
        return _ok(repo.create_category(name, slug=slug, parent_id=parent_id))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def update_category(
    category_ref: str,
    name: str | None = None,
    slug: str | None = None,
    parent_id: int | None = None,
) -> str:
    """Update an existing category."""
    try:
        return _ok(repo.update_category(category_ref, name=name, slug=slug, parent_id=parent_id))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def list_categories() -> str:
    """List expense categories with parent hierarchy."""
    try:
        return _ok(repo.list_categories())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def delete_category(category_ref: str, reassign_to: str | None = None) -> str:
    """Delete a category. Pass reassign_to when expenses still reference it."""
    try:
        return _ok(repo.delete_category(category_ref, reassign_to=reassign_to))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def add_expense(
    expense_date: str,
    description: str,
    amount: float,
    category: str,
    paid_by: str,
    currency: str = "ARS",
    project: str | None = None,
    notes: str | None = None,
    allocations: list[dict[str, Any]] | None = None,
) -> str:
    """Add an expense. Allocations must sum to 100; defaults to 100% for payer."""
    try:
        return _ok(
            repo.add_expense(
                expense_date=expense_date,
                description=description,
                amount=amount,
                category=category,
                paid_by=paid_by,
                currency=currency,
                project=project,
                notes=notes,
                allocations=allocations,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def update_expense(
    expense_id: int,
    expense_date: str | None = None,
    description: str | None = None,
    amount: float | None = None,
    currency: str | None = None,
    category: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    notes: str | None = None,
    allocations: list[dict[str, Any]] | None = None,
) -> str:
    """Update an expense and optionally replace allocations."""
    try:
        return _ok(
            repo.update_expense(
                expense_id=expense_id,
                expense_date=expense_date,
                description=description,
                amount=amount,
                currency=currency,
                category=category,
                project=project,
                paid_by=paid_by,
                notes=notes,
                allocations=allocations,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def delete_expense(expense_id: int) -> str:
    """Delete an expense."""
    try:
        return _ok(repo.delete_expense(expense_id))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def list_expenses(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    allocated_to: str | None = None,
    currency: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List expenses with optional filters and pagination."""
    try:
        return _ok(
            repo.list_expenses(
                start_date=start_date,
                end_date=end_date,
                category=category,
                project=project,
                paid_by=paid_by,
                allocated_to=allocated_to,
                currency=currency,
                limit=limit,
                offset=offset,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def search_expenses(
    query: str,
    start_date: str | None = None,
    end_date: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    currency: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """Search expenses by text plus optional date, amount, and currency filters."""
    try:
        return _ok(
            repo.search_expenses(
                query,
                start_date=start_date,
                end_date=end_date,
                min_amount=min_amount,
                max_amount=max_amount,
                currency=currency,
                limit=limit,
                offset=offset,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def monthly_summary(
    year: int,
    month: int,
    category: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    allocated_to: str | None = None,
    currency: str | None = None,
) -> str:
    """Monthly spending summary with optional filters."""
    try:
        return _ok(
            repo.monthly_summary(
                year,
                month,
                category=category,
                project=project,
                paid_by=paid_by,
                allocated_to=allocated_to,
                currency=currency,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def yearly_summary(
    year: int,
    category: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    allocated_to: str | None = None,
    currency: str | None = None,
) -> str:
    """Yearly spending summary with optional filters."""
    try:
        return _ok(
            repo.yearly_summary(
                year,
                category=category,
                project=project,
                paid_by=paid_by,
                allocated_to=allocated_to,
                currency=currency,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def project_summary(
    project: str,
    start_date: str | None = None,
    end_date: str | None = None,
    paid_by: str | None = None,
    allocated_to: str | None = None,
    currency: str | None = None,
) -> str:
    """Summary for a project with optional filters."""
    try:
        return _ok(
            repo.project_summary(
                project,
                start_date=start_date,
                end_date=end_date,
                paid_by=paid_by,
                allocated_to=allocated_to,
                currency=currency,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def category_summary(
    category: str,
    start_date: str | None = None,
    end_date: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    allocated_to: str | None = None,
    currency: str | None = None,
) -> str:
    """Summary for a category with breakdowns by month and project."""
    try:
        return _ok(
            repo.category_summary(
                category,
                start_date=start_date,
                end_date=end_date,
                project=project,
                paid_by=paid_by,
                allocated_to=allocated_to,
                currency=currency,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def person_summary(
    person: str,
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    project: str | None = None,
    currency: str | None = None,
) -> str:
    """Person summary: paid vs attributed, with breakdowns by category and project."""
    try:
        return _ok(
            repo.person_summary(
                person,
                start_date=start_date,
                end_date=end_date,
                category=category,
                project=project,
                currency=currency,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def compare_periods(
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
    category: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    allocated_to: str | None = None,
    currency: str | None = None,
) -> str:
    """Compare spending between two date ranges."""
    try:
        return _ok(
            repo.compare_periods(
                period_a_start,
                period_a_end,
                period_b_start,
                period_b_end,
                category=category,
                project=project,
                paid_by=paid_by,
                allocated_to=allocated_to,
                currency=currency,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def compare_months(
    month_a: int,
    month_b: int,
    year_a: int | None = None,
    year_b: int | None = None,
    category: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    allocated_to: str | None = None,
    currency: str | None = None,
) -> str:
    """Compare spending between two months (e.g. June vs May)."""
    try:
        return _ok(
            repo.compare_months(
                month_a,
                month_b,
                year_a=year_a,
                year_b=year_b,
                category=category,
                project=project,
                paid_by=paid_by,
                allocated_to=allocated_to,
                currency=currency,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def top_expenses(
    limit: int = 10,
    start_date: str | None = None,
    end_date: str | None = None,
    year: int | None = None,
    month: int | None = None,
    category: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    allocated_to: str | None = None,
    currency: str | None = None,
    sort_by: str = "amount_desc",
) -> str:
    """Largest or notable expenses for a period."""
    try:
        return _ok(
            repo.top_expenses(
                limit=limit,
                start_date=start_date,
                end_date=end_date,
                year=year,
                month=month,
                category=category,
                project=project,
                paid_by=paid_by,
                allocated_to=allocated_to,
                currency=currency,
                sort_by=sort_by,  # type: ignore[arg-type]
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def export_expenses(
    export_format: str = "csv",
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    allocated_to: str | None = None,
    currency: str | None = None,
    limit: int = 5000,
) -> str:
    """Export filtered expenses as CSV or JSON text."""
    try:
        return _ok(
            repo.export_expenses(
                export_format=export_format,  # type: ignore[arg-type]
                start_date=start_date,
                end_date=end_date,
                category=category,
                project=project,
                paid_by=paid_by,
                allocated_to=allocated_to,
                currency=currency,
                limit=limit,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def export_expenses_file(
    export_format: str = "csv",
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    project: str | None = None,
    paid_by: str | None = None,
    allocated_to: str | None = None,
    currency: str | None = None,
    limit: int = 5000,
) -> str:
    """Export filtered expenses to a file under ~/.hermes/expense-tracker/exports/."""
    try:
        return _ok(
            reports.export_expenses_to_file(
                export_format=export_format,  # type: ignore[arg-type]
                start_date=start_date,
                end_date=end_date,
                category=category,
                project=project,
                paid_by=paid_by,
                allocated_to=allocated_to,
                currency=currency,
                limit=limit,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def generate_report(
    period: str = "month",
    year: int | None = None,
    month: int | None = None,
    project: str | None = None,
    currency: str | None = None,
    include_ascii_charts: bool = True,
) -> str:
    """Unified spending report (markdown) for month, year, or a single project."""
    try:
        return _ok(
            reports.generate_report(
                period=period,  # type: ignore[arg-type]
                year=year,
                month=month,
                project=project,
                currency=currency,
                include_ascii_charts=include_ascii_charts,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def render_chart(
    chart_type: str,
    year: int | None = None,
    month: int | None = None,
    project: str | None = None,
    currency: str | None = None,
) -> Image:
    """Render a spending chart PNG. Types: by_category, by_project, monthly_trend, top_expenses."""
    result = reports.render_chart(
        chart_type=chart_type,  # type: ignore[arg-type]
        year=year,
        month=month,
        project=project,
        currency=currency,
    )
    return Image(path=result["file_path"])


@mcp.tool()
def set_category_budget(
    category: str,
    monthly_amount: float,
    currency: str = "ARS",
    alert_threshold_pct: float = 100.0,
    notes: str | None = None,
) -> str:
    """Set a monthly spending budget for a category."""
    try:
        return _ok(
            repo.set_category_budget(
                category,
                monthly_amount,
                currency=currency,
                alert_threshold_pct=alert_threshold_pct,
                notes=notes,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def update_category_budget(
    category: str,
    monthly_amount: float | None = None,
    currency: str | None = None,
    alert_threshold_pct: float | None = None,
    is_active: bool | None = None,
    notes: str | None = None,
) -> str:
    """Update an existing category budget."""
    try:
        return _ok(
            repo.update_category_budget(
                category,
                monthly_amount=monthly_amount,
                currency=currency,
                alert_threshold_pct=alert_threshold_pct,
                is_active=is_active,
                notes=notes,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def delete_category_budget(category: str) -> str:
    """Remove a category budget."""
    try:
        return _ok(repo.delete_category_budget(category))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def list_category_budgets(active_only: bool = True) -> str:
    """List configured category budgets."""
    try:
        return _ok(repo.list_category_budgets(active_only=active_only))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def budget_status(year: int, month: int, alerts_only: bool = False) -> str:
    """Compare monthly spending against budgets; flags alerts."""
    try:
        return _ok(repo.budget_status(year, month, alerts_only=alerts_only))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
def health_check() -> str:
    """Verify DB connectivity and return counts."""
    try:
        return _ok(repo.health_check())
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


if __name__ == "__main__":
    init_db(seed="categories")
    mcp.run()
