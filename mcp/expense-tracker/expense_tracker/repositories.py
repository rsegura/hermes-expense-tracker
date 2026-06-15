from __future__ import annotations

import csv
import io
import json
import os
import re
import calendar
from datetime import date, datetime, timedelta
from typing import Any, Literal

from .db import connect, init_db, row_to_dict, rows_to_dicts


def _slugify(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-") or "item"


def _parse_aliases(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if str(a).strip()]
    text = raw.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(a).strip() for a in parsed if str(a).strip()]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in text.split(",") if part.strip()]


def _aliases_json(aliases: list[str] | str | None) -> str:
    return json.dumps(_parse_aliases(aliases), ensure_ascii=False)


class ValidationError(ValueError):
    pass


class NotFoundError(LookupError):
    pass


def get_caller_slug() -> str | None:
    raw = os.getenv("EXPENSE_MEMBER_SLUG", "").strip()
    return raw or None


def _get_caller_person(conn) -> dict[str, Any] | None:
    slug = get_caller_slug()
    if slug is None:
        return None
    return _get_person_by_ref(conn, slug)


def _get_visible_project_ids(conn, person_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT project_id FROM project_members WHERE person_id = ?",
        (person_id,),
    ).fetchall()
    return [int(row["project_id"]) for row in rows]


def _assert_project_access(conn, project_id: int, person_id: int) -> str:
    row = conn.execute(
        "SELECT role FROM project_members WHERE project_id = ? AND person_id = ?",
        (project_id, person_id),
    ).fetchone()
    if row is None:
        raise ValidationError("No access to this project")
    return str(row["role"])


def _assert_project_owner(conn, project_id: int, person_id: int) -> None:
    role = _assert_project_access(conn, project_id, person_id)
    if role != "owner":
        raise ValidationError("Only the project owner can perform this action")


def _get_accessible_project_by_ref(
    conn,
    ref: str | int | None,
    *,
    require_owner: bool = False,
) -> dict[str, Any] | None:
    project = _get_project_by_ref(conn, ref)
    if project is None:
        return None
    caller = _get_caller_person(conn)
    if caller is None:
        return project
    if require_owner:
        _assert_project_owner(conn, project["id"], caller["id"])
    else:
        _assert_project_access(conn, project["id"], caller["id"])
    return project


def _project_visibility_clause(conn, alias: str = "e") -> tuple[str, list[Any]]:
    caller = _get_caller_person(conn)
    if caller is None:
        return "", []
    visible_ids = _get_visible_project_ids(conn, caller["id"])
    if not visible_ids:
        return f"({alias}.project_id IS NULL)", []
    placeholders = ",".join("?" * len(visible_ids))
    clause = f"({alias}.project_id IS NULL OR {alias}.project_id IN ({placeholders}))"
    return clause, list(visible_ids)


def _list_project_member_rows(conn, project_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT pm.role, p.slug, p.display_name, p.id AS person_id
        FROM project_members pm
        JOIN persons p ON p.id = pm.person_id
        WHERE pm.project_id = ?
        ORDER BY pm.role DESC, p.display_name
        """,
        (project_id,),
    ).fetchall()
    return [
        {
            "person_id": row["person_id"],
            "slug": row["slug"],
            "display_name": row["display_name"],
            "role": row["role"],
        }
        for row in rows
    ]


def _enrich_project(conn, project: dict[str, Any]) -> dict[str, Any]:
    members = _list_project_member_rows(conn, project["id"])
    enriched = dict(project)
    enriched["members"] = members
    enriched["member_count"] = len(members)
    caller = _get_caller_person(conn)
    enriched["role"] = None
    if caller is not None:
        for member in members:
            if member["person_id"] == caller["id"]:
                enriched["role"] = member["role"]
                break
    return enriched


def _insert_project_member(conn, project_id: int, person_id: int, role: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO project_members (project_id, person_id, role)
        VALUES (?, ?, ?)
        """,
        (project_id, person_id, role),
    )


def _assert_expense_visible(conn, expense_id: int) -> dict[str, Any]:
    expense = _expense_with_relations(conn, expense_id)
    if expense.get("project_id"):
        caller = _get_caller_person(conn)
        if caller is not None:
            _assert_project_access(conn, int(expense["project_id"]), caller["id"])
    return expense


def _get_person_by_ref(conn, ref: str | int) -> dict[str, Any]:
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (int(ref),)).fetchone()
    else:
        ref_slug = _slugify(str(ref))
        row = conn.execute(
            "SELECT * FROM persons WHERE slug = ? OR display_name = ? COLLATE NOCASE",
            (ref_slug, str(ref)),
        ).fetchone()
        if row is None:
            rows = conn.execute("SELECT * FROM persons").fetchall()
            for candidate in rows:
                aliases = _parse_aliases(candidate["aliases"])
                if str(ref).lower() in {a.lower() for a in aliases}:
                    row = candidate
                    break
    if row is None:
        raise NotFoundError(f"Person not found: {ref}")
    person = row_to_dict(row)
    person["aliases"] = _parse_aliases(person["aliases"])
    return person


def _get_project_by_ref(conn, ref: str | int | None) -> dict[str, Any] | None:
    if ref is None:
        return None
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (int(ref),)).fetchone()
    else:
        ref_slug = _slugify(str(ref))
        row = conn.execute(
            "SELECT * FROM projects WHERE slug = ? OR name = ? COLLATE NOCASE",
            (ref_slug, str(ref)),
        ).fetchone()
    if row is None:
        raise NotFoundError(f"Project not found: {ref}")
    return row_to_dict(row)


def _get_category_by_ref(conn, ref: str | int) -> dict[str, Any]:
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (int(ref),)).fetchone()
    else:
        ref_slug = _slugify(str(ref))
        row = conn.execute(
            "SELECT * FROM categories WHERE slug = ? OR name = ? COLLATE NOCASE",
            (ref_slug, str(ref)),
        ).fetchone()
    if row is None:
        raise NotFoundError(f"Category not found: {ref}")
    return row_to_dict(row)


def _validate_allocations(allocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not allocations:
        raise ValidationError("At least one allocation is required")
    total = 0.0
    seen: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for item in allocations:
        person_id = int(item["person_id"])
        percentage = float(item["percentage"])
        if person_id in seen:
            raise ValidationError("Duplicate person in allocations")
        if percentage <= 0 or percentage > 100:
            raise ValidationError("Each allocation percentage must be > 0 and <= 100")
        seen.add(person_id)
        total += percentage
        normalized.append({"person_id": person_id, "percentage": percentage})
    if abs(total - 100.0) > 0.01:
        raise ValidationError(f"Allocations must sum to 100, got {total}")
    return normalized


_FREQUENCIES = ("weekly", "monthly", "yearly")


def _today_str() -> str:
    return date.today().isoformat()


def _advance_due_date(
    due: str,
    frequency: str,
    interval: int,
    anchor_day: int | None,
    anchor_month: int | None,
) -> str:
    """Advance an ISO date by interval x frequency, preserving the anchor day."""
    d = date.fromisoformat(due)
    if frequency == "weekly":
        return (d + timedelta(days=7 * interval)).isoformat()
    if frequency == "monthly":
        month_index = (d.month - 1) + interval
        year = d.year + month_index // 12
        month = month_index % 12 + 1
        day = d.day if anchor_day is None else anchor_day
        last = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, last)).isoformat()
    if frequency == "yearly":
        year = d.year + interval
        month = d.month if anchor_month is None else anchor_month
        day = d.day if anchor_day is None else anchor_day
        last = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, last)).isoformat()
    raise ValidationError(f"Unknown frequency: {frequency}")


def create_person(
    display_name: str,
    slug: str | None = None,
    aliases: list[str] | str | None = None,
) -> dict[str, Any]:
    slug_value = _slugify(slug or display_name)
    with connect() as conn:
        existing = conn.execute("SELECT id FROM persons WHERE slug = ?", (slug_value,)).fetchone()
        if existing:
            raise ValidationError(f"Person slug already exists: {slug_value}")
        conn.execute(
            "INSERT INTO persons (slug, display_name, aliases) VALUES (?, ?, ?)",
            (slug_value, display_name.strip(), _aliases_json(aliases)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM persons WHERE slug = ?", (slug_value,)).fetchone()
    person = row_to_dict(row)
    person["aliases"] = _parse_aliases(person["aliases"])
    return person


def update_person(
    person_ref: str | int,
    display_name: str | None = None,
    slug: str | None = None,
    aliases: list[str] | str | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        person = _get_person_by_ref(conn, person_ref)
        new_slug = _slugify(slug) if slug else person["slug"]
        if new_slug != person["slug"]:
            clash = conn.execute("SELECT id FROM persons WHERE slug = ?", (new_slug,)).fetchone()
            if clash:
                raise ValidationError(f"Person slug already exists: {new_slug}")
        conn.execute(
            """
            UPDATE persons
            SET slug = ?, display_name = COALESCE(?, display_name),
                aliases = COALESCE(?, aliases)
            WHERE id = ?
            """,
            (
                new_slug,
                display_name.strip() if display_name else None,
                _aliases_json(aliases) if aliases is not None else None,
                person["id"],
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (person["id"],)).fetchone()
    updated = row_to_dict(row)
    updated["aliases"] = _parse_aliases(updated["aliases"])
    return updated


def list_persons() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM persons ORDER BY display_name").fetchall()
    persons = rows_to_dicts(rows)
    for person in persons:
        person["aliases"] = _parse_aliases(person["aliases"])
    return persons


def create_project(
    name: str,
    slug: str | None = None,
    description: str | None = None,
    members: list[str] | None = None,
    owner: str | None = None,
) -> dict[str, Any]:
    slug_value = _slugify(slug or name)
    with connect() as conn:
        existing = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug_value,)).fetchone()
        if existing:
            raise ValidationError(f"Project slug already exists: {slug_value}")

        caller = _get_caller_person(conn)
        if caller is not None:
            owner_person = caller
        elif owner is not None:
            owner_person = _get_person_by_ref(conn, owner)
        else:
            raise ValidationError(
                "EXPENSE_MEMBER_SLUG is required to create projects (or pass owner for bootstrap)"
            )

        member_people: dict[int, dict[str, Any]] = {owner_person["id"]: owner_person}
        for member_ref in members or []:
            person = _get_person_by_ref(conn, member_ref)
            member_people[person["id"]] = person

        conn.execute(
            """
            INSERT INTO projects (slug, name, description, created_by_person_id)
            VALUES (?, ?, ?, ?)
            """,
            (slug_value, name.strip(), description, owner_person["id"]),
        )
        project_row = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug_value,)).fetchone()
        project_id = int(project_row["id"])

        for person_id, person in member_people.items():
            role = "owner" if person_id == owner_person["id"] else "member"
            _insert_project_member(conn, project_id, person_id, role)

        conn.commit()
        return _enrich_project(conn, row_to_dict(project_row))


def update_project(
    project_ref: str | int,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        project = _get_accessible_project_by_ref(conn, project_ref, require_owner=True)
        new_slug = _slugify(slug) if slug else project["slug"]
        if new_slug != project["slug"]:
            clash = conn.execute("SELECT id FROM projects WHERE slug = ?", (new_slug,)).fetchone()
            if clash:
                raise ValidationError(f"Project slug already exists: {new_slug}")
        conn.execute(
            """
            UPDATE projects
            SET slug = ?, name = COALESCE(?, name), description = COALESCE(?, description),
                is_active = COALESCE(?, is_active)
            WHERE id = ?
            """,
            (
                new_slug,
                name.strip() if name else None,
                description,
                int(is_active) if is_active is not None else None,
                project["id"],
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project["id"],)).fetchone()
    return _enrich_project(conn, row_to_dict(row))


def list_projects(active_only: bool = False) -> list[dict[str, Any]]:
    with connect() as conn:
        caller = _get_caller_person(conn)
        if caller is None:
            query = "SELECT * FROM projects"
            params: list[Any] = []
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY name"
            rows = conn.execute(query, params).fetchall()
        else:
            query = """
                SELECT p.*
                FROM projects p
                JOIN project_members pm ON pm.project_id = p.id AND pm.person_id = ?
            """
            params = [caller["id"]]
            if active_only:
                query += " WHERE p.is_active = 1"
            query += " ORDER BY p.name"
            rows = conn.execute(query, params).fetchall()
        return [_enrich_project(conn, row_to_dict(row)) for row in rows]


def add_project_member(project_ref: str | int, person_ref: str | int) -> dict[str, Any]:
    with connect() as conn:
        project = _get_accessible_project_by_ref(conn, project_ref, require_owner=True)
        person = _get_person_by_ref(conn, person_ref)
        _insert_project_member(conn, project["id"], person["id"], "member")
        conn.commit()
        return {
            "project": _enrich_project(conn, project),
            "added": {
                "slug": person["slug"],
                "display_name": person["display_name"],
                "role": "member",
            },
        }


def remove_project_member(project_ref: str | int, person_ref: str | int) -> dict[str, Any]:
    with connect() as conn:
        project = _get_accessible_project_by_ref(conn, project_ref, require_owner=True)
        person = _get_person_by_ref(conn, person_ref)
        membership = conn.execute(
            "SELECT role FROM project_members WHERE project_id = ? AND person_id = ?",
            (project["id"], person["id"]),
        ).fetchone()
        if membership is None:
            raise NotFoundError(f"Person is not a member of project: {person['slug']}")
        if membership["role"] == "owner":
            owner_count = conn.execute(
                "SELECT COUNT(*) AS c FROM project_members WHERE project_id = ? AND role = 'owner'",
                (project["id"],),
            ).fetchone()["c"]
            if owner_count <= 1:
                raise ValidationError("Cannot remove the only owner from a project")
        conn.execute(
            "DELETE FROM project_members WHERE project_id = ? AND person_id = ?",
            (project["id"], person["id"]),
        )
        conn.commit()
        return {
            "project": _enrich_project(conn, project),
            "removed": {
                "slug": person["slug"],
                "display_name": person["display_name"],
            },
        }


def list_project_members(project_ref: str | int) -> list[dict[str, Any]]:
    with connect() as conn:
        project = _get_accessible_project_by_ref(conn, project_ref)
        return _list_project_member_rows(conn, project["id"])


def sync_project_members_all_persons(project_ref: str | int) -> dict[str, Any]:
    """Add every person in the DB as a member (bootstrap/install). Keeps existing owner."""
    with connect() as conn:
        project = _get_project_by_ref(conn, project_ref)
        owner_id = project.get("created_by_person_id")
        if owner_id is None:
            owner_id = _default_owner_id_for_project(conn)
            if owner_id is not None:
                conn.execute(
                    "UPDATE projects SET created_by_person_id = ? WHERE id = ?",
                    (owner_id, project["id"]),
                )
        persons = conn.execute("SELECT id FROM persons ORDER BY id").fetchall()
        for person in persons:
            role = "owner" if owner_id is not None and person["id"] == owner_id else "member"
            existing = conn.execute(
                "SELECT role FROM project_members WHERE project_id = ? AND person_id = ?",
                (project["id"], person["id"]),
            ).fetchone()
            if existing is None:
                _insert_project_member(conn, project["id"], person["id"], role)
        conn.commit()
        return _enrich_project(conn, project)


def _default_owner_id_for_project(conn) -> int | None:
    row = conn.execute("SELECT id FROM persons ORDER BY created_at, id LIMIT 1").fetchone()
    return int(row["id"]) if row is not None else None


def create_category(name: str, slug: str | None = None, parent_id: int | None = None) -> dict[str, Any]:
    slug_value = _slugify(slug or name)
    with connect() as conn:
        existing = conn.execute("SELECT id FROM categories WHERE slug = ?", (slug_value,)).fetchone()
        if existing:
            raise ValidationError(f"Category slug already exists: {slug_value}")
        if parent_id is not None:
            parent = conn.execute("SELECT id FROM categories WHERE id = ?", (parent_id,)).fetchone()
            if parent is None:
                raise NotFoundError(f"Parent category not found: {parent_id}")
        conn.execute(
            "INSERT INTO categories (slug, name, parent_id) VALUES (?, ?, ?)",
            (slug_value, name.strip(), parent_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM categories WHERE slug = ?", (slug_value,)).fetchone()
    return row_to_dict(row)


def update_category(
    category_ref: str | int,
    name: str | None = None,
    slug: str | None = None,
    parent_id: int | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        category = _get_category_by_ref(conn, category_ref)
        new_slug = _slugify(slug) if slug else category["slug"]
        if new_slug != category["slug"]:
            clash = conn.execute("SELECT id FROM categories WHERE slug = ?", (new_slug,)).fetchone()
            if clash:
                raise ValidationError(f"Category slug already exists: {new_slug}")
        conn.execute(
            """
            UPDATE categories
            SET slug = ?, name = COALESCE(?, name), parent_id = COALESCE(?, parent_id)
            WHERE id = ?
            """,
            (
                new_slug,
                name.strip() if name else None,
                parent_id,
                category["id"],
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category["id"],)).fetchone()
    return row_to_dict(row)


def list_categories() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, p.slug AS parent_slug, p.name AS parent_name
            FROM categories c
            LEFT JOIN categories p ON p.id = c.parent_id
            ORDER BY COALESCE(p.name, c.name), c.name
            """
        ).fetchall()
    return rows_to_dicts(rows)


def delete_project(project_ref: str | int, *, force: bool = False) -> dict[str, Any]:
    with connect() as conn:
        project = _get_accessible_project_by_ref(conn, project_ref, require_owner=True)
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE project_id = ?",
            (project["id"],),
        ).fetchone()["c"]
        if count and not force:
            raise ValidationError(
                f"Project has {count} expense(s). Set force=true to unlink them, "
                "or use update_project(is_active=false) to archive."
            )
        if count and force:
            conn.execute(
                "UPDATE expenses SET project_id = NULL, updated_at = datetime('now') WHERE project_id = ?",
                (project["id"],),
            )
        conn.execute("DELETE FROM projects WHERE id = ?", (project["id"],))
        conn.commit()
    return {"deleted": True, "project": project, "expenses_unlinked": count if force else 0}


def delete_category(
    category_ref: str | int,
    *,
    reassign_to: str | int | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        category = _get_category_by_ref(conn, category_ref)
        children = conn.execute(
            "SELECT COUNT(*) AS c FROM categories WHERE parent_id = ?",
            (category["id"],),
        ).fetchone()["c"]
        if children:
            raise ValidationError(
                f"Category has {children} child categor(ies). Reassign or delete children first."
            )
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE category_id = ?",
            (category["id"],),
        ).fetchone()["c"]
        if count and reassign_to is None:
            raise ValidationError(
                f"Category has {count} expense(s). Pass reassign_to to move them before delete."
            )
        reassigned = 0
        if count and reassign_to is not None:
            target = _get_category_by_ref(conn, reassign_to)
            if target["id"] == category["id"]:
                raise ValidationError("reassign_to must be a different category")
            conn.execute(
                "UPDATE expenses SET category_id = ?, updated_at = datetime('now') WHERE category_id = ?",
                (target["id"], category["id"]),
            )
            reassigned = count
        conn.execute("DELETE FROM categories WHERE id = ?", (category["id"],))
        conn.commit()
    return {"deleted": True, "category": category, "expenses_reassigned": reassigned}


def delete_person(person_ref: str | int) -> dict[str, Any]:
    with connect() as conn:
        person = _get_person_by_ref(conn, person_ref)
        paid_count = conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE paid_by_person_id = ?",
            (person["id"],),
        ).fetchone()["c"]
        alloc_count = conn.execute(
            "SELECT COUNT(*) AS c FROM expense_allocations WHERE person_id = ?",
            (person["id"],),
        ).fetchone()["c"]
        if paid_count or alloc_count:
            raise ValidationError(
                f"Person is referenced in {paid_count} payment(s) and {alloc_count} allocation(s). "
                "Remove or reassign expenses first."
            )
        conn.execute("DELETE FROM persons WHERE id = ?", (person["id"],))
        conn.commit()
    return {"deleted": True, "person": person}


def _expense_filter_parts(
    conn,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    end_exclusive: str | None = None,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    alias: str = "e",
) -> tuple[list[str], list[Any], str]:
    clauses: list[str] = []
    params: list[Any] = []
    joins = ""
    if start_date:
        clauses.append(f"{alias}.expense_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append(f"{alias}.expense_date <= ?")
        params.append(end_date)
    if end_exclusive:
        clauses.append(f"{alias}.expense_date < ?")
        params.append(end_exclusive)
    if category is not None:
        category_row = _get_category_by_ref(conn, category)
        clauses.append(f"{alias}.category_id = ?")
        params.append(category_row["id"])
    if project is not None:
        project_row = _get_accessible_project_by_ref(conn, project)
        clauses.append(f"{alias}.project_id = ?")
        params.append(project_row["id"])
    visibility_clause, visibility_params = _project_visibility_clause(conn, alias=alias)
    if visibility_clause:
        clauses.append(visibility_clause)
        params.extend(visibility_params)
    if paid_by is not None:
        person_row = _get_person_by_ref(conn, paid_by)
        clauses.append(f"{alias}.paid_by_person_id = ?")
        params.append(person_row["id"])
    if allocated_to is not None:
        person_row = _get_person_by_ref(conn, allocated_to)
        joins = (
            f" JOIN expense_allocations {alias}_alloc "
            f"ON {alias}_alloc.expense_id = {alias}.id AND {alias}_alloc.person_id = ?"
        )
        params.insert(0, person_row["id"])
    if currency is not None:
        clauses.append(f"{alias}.currency = ?")
        params.append(currency.upper())
    if min_amount is not None:
        clauses.append(f"{alias}.amount >= ?")
        params.append(float(min_amount))
    if max_amount is not None:
        clauses.append(f"{alias}.amount <= ?")
        params.append(float(max_amount))
    return clauses, params, joins


def _where_clause(clauses: list[str]) -> str:
    return f"WHERE {' AND '.join(clauses)}" if clauses else ""


def _category_parent_select(alias: str = "c") -> str:
    return (
        f"{alias}.name AS category, {alias}.slug AS category_slug, "
        f"{alias}.parent_id AS category_parent_id, "
        f"COALESCE(pc.name, '') AS parent_category"
    )


def _expense_with_relations(conn, expense_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"Expense not found: {expense_id}")
    expense = row_to_dict(row)
    expense["category"] = _get_category_by_ref(conn, expense["category_id"])
    expense["project"] = _get_project_by_ref(conn, expense["project_id"]) if expense["project_id"] else None
    expense["paid_by"] = _get_person_by_ref(conn, expense["paid_by_person_id"])
    alloc_rows = conn.execute(
        """
        SELECT ea.*, p.slug AS person_slug, p.display_name AS person_name
        FROM expense_allocations ea
        JOIN persons p ON p.id = ea.person_id
        WHERE ea.expense_id = ?
        ORDER BY ea.person_id
        """,
        (expense_id,),
    ).fetchall()
    expense["allocations"] = [
        {
            "person_id": r["person_id"],
            "person_slug": r["person_slug"],
            "person_name": r["person_name"],
            "percentage": r["percentage"],
        }
        for r in alloc_rows
    ]
    return expense


def _resolve_allocations(conn, allocations: list[dict[str, Any]] | None, paid_by_person_id: int) -> list[dict[str, Any]]:
    if allocations:
        resolved: list[dict[str, Any]] = []
        for item in allocations:
            if "person_id" in item:
                person_id = int(item["person_id"])
                _get_person_by_ref(conn, person_id)
            else:
                person = _get_person_by_ref(conn, item.get("person") or item.get("person_slug") or item.get("person_name"))
                person_id = person["id"]
            resolved.append({"person_id": person_id, "percentage": float(item["percentage"])})
        return _validate_allocations(resolved)
    return _validate_allocations([{"person_id": paid_by_person_id, "percentage": 100.0}])


def add_expense(
    expense_date: str,
    description: str,
    amount: float,
    category: str | int,
    paid_by: str | int,
    currency: str = "ARS",
    project: str | int | None = None,
    notes: str | None = None,
    allocations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if amount < 0:
        raise ValidationError("Amount must be >= 0")
    datetime.strptime(expense_date, "%Y-%m-%d")
    with connect() as conn:
        category_row = _get_category_by_ref(conn, category)
        paid_by_row = _get_person_by_ref(conn, paid_by)
        project_row = _get_accessible_project_by_ref(conn, project) if project else None
        normalized_allocations = _resolve_allocations(conn, allocations, paid_by_row["id"])
        cur = conn.execute(
            """
            INSERT INTO expenses (
                expense_date, description, amount, currency, category_id,
                project_id, paid_by_person_id, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expense_date,
                description.strip(),
                float(amount),
                currency.upper(),
                category_row["id"],
                project_row["id"] if project_row else None,
                paid_by_row["id"],
                notes,
            ),
        )
        expense_id = cur.lastrowid
        for alloc in normalized_allocations:
            conn.execute(
                "INSERT INTO expense_allocations (expense_id, person_id, percentage) VALUES (?, ?, ?)",
                (expense_id, alloc["person_id"], alloc["percentage"]),
            )
        conn.commit()
        return _expense_with_relations(conn, expense_id)


def update_expense(
    expense_id: int,
    expense_date: str | None = None,
    description: str | None = None,
    amount: float | None = None,
    currency: str | None = None,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    notes: str | None = None,
    allocations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        _assert_expense_visible(conn, expense_id)
        category_id = None
        project_id = None
        paid_by_id = None
        if category is not None:
            category_id = _get_category_by_ref(conn, category)["id"]
        if project is not None:
            project_id = _get_accessible_project_by_ref(conn, project)["id"] if project else None
        if paid_by is not None:
            paid_by_id = _get_person_by_ref(conn, paid_by)["id"]
        if expense_date is not None:
            datetime.strptime(expense_date, "%Y-%m-%d")
        if amount is not None and amount < 0:
            raise ValidationError("Amount must be >= 0")
        conn.execute(
            """
            UPDATE expenses
            SET expense_date = COALESCE(?, expense_date),
                description = COALESCE(?, description),
                amount = COALESCE(?, amount),
                currency = COALESCE(?, currency),
                category_id = COALESCE(?, category_id),
                project_id = COALESCE(?, project_id),
                paid_by_person_id = COALESCE(?, paid_by_person_id),
                notes = COALESCE(?, notes),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                expense_date,
                description.strip() if description else None,
                amount,
                currency.upper() if currency else None,
                category_id,
                project_id,
                paid_by_id,
                notes,
                expense_id,
            ),
        )
        if allocations is not None:
            current = conn.execute(
                "SELECT paid_by_person_id FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()
            paid_by_person_id = paid_by_id or current["paid_by_person_id"]
            normalized_allocations = _resolve_allocations(conn, allocations, paid_by_person_id)
            conn.execute("DELETE FROM expense_allocations WHERE expense_id = ?", (expense_id,))
            for alloc in normalized_allocations:
                conn.execute(
                    "INSERT INTO expense_allocations (expense_id, person_id, percentage) VALUES (?, ?, ?)",
                    (expense_id, alloc["person_id"], alloc["percentage"]),
                )
        conn.commit()
        return _expense_with_relations(conn, expense_id)


def delete_expense(expense_id: int) -> dict[str, Any]:
    with connect() as conn:
        expense = _assert_expense_visible(conn, expense_id)
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
    return {"deleted": True, "expense": expense}


def list_expenses(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if limit < 1 or limit > 500:
        raise ValidationError("limit must be between 1 and 500")
    if offset < 0:
        raise ValidationError("offset must be >= 0")
    with connect() as conn:
        clauses, params, joins = _expense_filter_parts(
            conn,
            start_date=start_date,
            end_date=end_date,
            category=category,
            project=project,
            paid_by=paid_by,
            allocated_to=allocated_to,
            currency=currency,
        )
        where = _where_clause(clauses)
        count_row = conn.execute(
            f"SELECT COUNT(DISTINCT e.id) AS c FROM expenses e{joins} {where}",
            params,
        ).fetchone()
        rows = conn.execute(
            f"""
            SELECT DISTINCT e.id FROM expenses e
            {joins}
            {where}
            ORDER BY e.expense_date DESC, e.id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        items = [_expense_with_relations(conn, row["id"]) for row in rows]
    return {
        "items": items,
        "total_count": count_row["c"],
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < count_row["c"],
    }


def search_expenses(
    query: str,
    start_date: str | None = None,
    end_date: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    currency: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if limit < 1 or limit > 500:
        raise ValidationError("limit must be between 1 and 500")
    if offset < 0:
        raise ValidationError("offset must be >= 0")
    pattern = f"%{query.strip()}%"
    with connect() as conn:
        filter_clauses, filter_params, _ = _expense_filter_parts(
            conn,
            start_date=start_date,
            end_date=end_date,
            min_amount=min_amount,
            max_amount=max_amount,
            currency=currency,
        )
        text_clause = (
            "(e.description LIKE ? OR e.notes LIKE ? OR c.name LIKE ? OR c.slug LIKE ? "
            "OR p.name LIKE ? OR p.slug LIKE ? OR pe.display_name LIKE ? OR pe.slug LIKE ?)"
        )
        clauses = [text_clause, *filter_clauses]
        params: list[Any] = [
            pattern,
            pattern,
            pattern,
            pattern,
            pattern,
            pattern,
            pattern,
            pattern,
            *filter_params,
        ]
        where = _where_clause(clauses)
        joins = (
            " LEFT JOIN categories c ON c.id = e.category_id"
            " LEFT JOIN projects p ON p.id = e.project_id"
            " LEFT JOIN persons pe ON pe.id = e.paid_by_person_id"
        )
        count_row = conn.execute(
            f"SELECT COUNT(DISTINCT e.id) AS c FROM expenses e{joins} {where}",
            params,
        ).fetchone()
        rows = conn.execute(
            f"""
            SELECT DISTINCT e.id FROM expenses e
            {joins}
            {where}
            ORDER BY e.expense_date DESC, e.id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        items = [_expense_with_relations(conn, row["id"]) for row in rows]
    return {
        "items": items,
        "total_count": count_row["c"],
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < count_row["c"],
    }


def monthly_summary(
    year: int,
    month: int,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    start = f"{year:04d}-{month:02d}-01"
    end_exclusive = f"{year + 1:04d}-01-01" if month == 12 else f"{year:04d}-{month + 1:02d}-01"
    with connect() as conn:
        clauses, params, joins = _expense_filter_parts(
            conn,
            start_date=start,
            end_exclusive=end_exclusive,
            category=category,
            project=project,
            paid_by=paid_by,
            allocated_to=allocated_to,
            currency=currency,
        )
        where = _where_clause(clauses)
        total = conn.execute(
            f"""
            SELECT COALESCE(SUM(sub.amount), 0) AS total, COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount FROM expenses e
                {joins}
                {where}
            ) sub
            """,
            params,
        ).fetchone()
        by_category = conn.execute(
            f"""
            SELECT {_category_parent_select("c")},
                   COALESCE(SUM(sub.amount), 0) AS total,
                   COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount, e.category_id FROM expenses e
                {joins}
                {where}
            ) sub
            JOIN categories c ON c.id = sub.category_id
            LEFT JOIN categories pc ON pc.id = c.parent_id
            GROUP BY c.id ORDER BY total DESC
            """,
            params,
        ).fetchall()
        by_project = conn.execute(
            f"""
            SELECT COALESCE(p.name, 'Sin proyecto') AS project,
                   COALESCE(p.slug, '') AS project_slug,
                   COALESCE(SUM(sub.amount), 0) AS total,
                   COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount, e.project_id FROM expenses e
                {joins}
                {where}
            ) sub
            LEFT JOIN projects p ON p.id = sub.project_id
            GROUP BY sub.project_id ORDER BY total DESC
            """,
            params,
        ).fetchall()
        by_person = conn.execute(
            f"""
            SELECT p.display_name AS person, p.slug AS person_slug,
                   COALESCE(SUM(sub.amount * ea.percentage / 100.0), 0) AS attributed_total
            FROM (
                SELECT DISTINCT e.id, e.amount FROM expenses e
                {joins}
                {where}
            ) sub
            JOIN expense_allocations ea ON ea.expense_id = sub.id
            JOIN persons p ON p.id = ea.person_id
            GROUP BY p.id ORDER BY attributed_total DESC
            """,
            params,
        ).fetchall()
        attributed_amount = None
        if allocated_to is not None:
            person_row = _get_person_by_ref(conn, allocated_to)
            attr = conn.execute(
                f"""
                SELECT COALESCE(SUM(sub.amount * ea.percentage / 100.0), 0) AS total
                FROM (
                    SELECT DISTINCT e.id, e.amount FROM expenses e
                    {joins}
                    {where}
                ) sub
                JOIN expense_allocations ea ON ea.expense_id = sub.id AND ea.person_id = ?
                """,
                [*params, person_row["id"]],
            ).fetchone()
            attributed_amount = attr["total"]
    result: dict[str, Any] = {
        "period": {"year": year, "month": month, "start": start, "end_exclusive": end_exclusive},
        "filters": {
            "category": category,
            "project": project,
            "paid_by": paid_by,
            "allocated_to": allocated_to,
            "currency": currency.upper() if currency else None,
        },
        "total_amount": total["total"],
        "expense_count": total["count"],
        "by_category": rows_to_dicts(by_category),
        "by_project": rows_to_dicts(by_project),
        "by_person": rows_to_dicts(by_person),
    }
    if attributed_amount is not None:
        result["attributed_amount"] = attributed_amount
    return result


def yearly_summary(
    year: int,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    start = f"{year:04d}-01-01"
    end_exclusive = f"{year + 1:04d}-01-01"
    with connect() as conn:
        clauses, params, joins = _expense_filter_parts(
            conn,
            start_date=start,
            end_exclusive=end_exclusive,
            category=category,
            project=project,
            paid_by=paid_by,
            allocated_to=allocated_to,
            currency=currency,
        )
        where = _where_clause(clauses)
        total = conn.execute(
            f"""
            SELECT COALESCE(SUM(sub.amount), 0) AS total, COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount FROM expenses e
                {joins}
                {where}
            ) sub
            """,
            params,
        ).fetchone()
        by_month = conn.execute(
            f"""
            SELECT strftime('%m', sub.expense_date) AS month,
                   COALESCE(SUM(sub.amount), 0) AS total,
                   COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount, e.expense_date FROM expenses e
                {joins}
                {where}
            ) sub
            GROUP BY strftime('%Y-%m', sub.expense_date)
            ORDER BY month
            """,
            params,
        ).fetchall()
        by_category = conn.execute(
            f"""
            SELECT {_category_parent_select("c")},
                   COALESCE(SUM(sub.amount), 0) AS total,
                   COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount, e.category_id FROM expenses e
                {joins}
                {where}
            ) sub
            JOIN categories c ON c.id = sub.category_id
            LEFT JOIN categories pc ON pc.id = c.parent_id
            GROUP BY c.id ORDER BY total DESC
            """,
            params,
        ).fetchall()
        by_project = conn.execute(
            f"""
            SELECT COALESCE(p.name, 'Sin proyecto') AS project,
                   COALESCE(p.slug, '') AS project_slug,
                   COALESCE(SUM(sub.amount), 0) AS total,
                   COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount, e.project_id FROM expenses e
                {joins}
                {where}
            ) sub
            LEFT JOIN projects p ON p.id = sub.project_id
            GROUP BY sub.project_id ORDER BY total DESC
            """,
            params,
        ).fetchall()
    return {
        "year": year,
        "filters": {
            "category": category,
            "project": project,
            "paid_by": paid_by,
            "allocated_to": allocated_to,
            "currency": currency.upper() if currency else None,
        },
        "total_amount": total["total"],
        "expense_count": total["count"],
        "by_month": rows_to_dicts(by_month),
        "by_category": rows_to_dicts(by_category),
        "by_project": rows_to_dicts(by_project),
    }


def project_summary(
    project: str | int,
    start_date: str | None = None,
    end_date: str | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        project_row = _get_accessible_project_by_ref(conn, project)
        clauses, params, joins = _expense_filter_parts(
            conn,
            start_date=start_date,
            end_date=end_date,
            paid_by=paid_by,
            allocated_to=allocated_to,
            currency=currency,
        )
        clauses.append("e.project_id = ?")
        params.append(project_row["id"])
        where = _where_clause(clauses)
        total = conn.execute(
            f"""
            SELECT COALESCE(SUM(sub.amount), 0) AS total, COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount FROM expenses e
                {joins}
                {where}
            ) sub
            """,
            params,
        ).fetchone()
        by_category = conn.execute(
            f"""
            SELECT {_category_parent_select("c")},
                   COALESCE(SUM(sub.amount), 0) AS total,
                   COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount, e.category_id FROM expenses e
                {joins}
                {where}
            ) sub
            JOIN categories c ON c.id = sub.category_id
            LEFT JOIN categories pc ON pc.id = c.parent_id
            GROUP BY c.id ORDER BY total DESC
            """,
            params,
        ).fetchall()
    return {
        "project": _enrich_project(conn, project_row),
        "total_amount": total["total"],
        "expense_count": total["count"],
        "by_category": rows_to_dicts(by_category),
    }


def category_summary(
    category: str | int,
    start_date: str | None = None,
    end_date: str | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        category_row = _get_category_by_ref(conn, category)
        parent = None
        if category_row.get("parent_id"):
            parent = row_to_dict(
                conn.execute(
                    "SELECT * FROM categories WHERE id = ?",
                    (category_row["parent_id"],),
                ).fetchone()
            )
        clauses, params, joins = _expense_filter_parts(
            conn,
            start_date=start_date,
            end_date=end_date,
            project=project,
            paid_by=paid_by,
            allocated_to=allocated_to,
            currency=currency,
        )
        clauses.append("e.category_id = ?")
        params.append(category_row["id"])
        where = _where_clause(clauses)
        total = conn.execute(
            f"""
            SELECT COALESCE(SUM(sub.amount), 0) AS total, COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount FROM expenses e
                {joins}
                {where}
            ) sub
            """,
            params,
        ).fetchone()
        by_month = conn.execute(
            f"""
            SELECT strftime('%Y-%m', sub.expense_date) AS period,
                   COALESCE(SUM(sub.amount), 0) AS total,
                   COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount, e.expense_date FROM expenses e
                {joins}
                {where}
            ) sub
            GROUP BY strftime('%Y-%m', sub.expense_date)
            ORDER BY period
            """,
            params,
        ).fetchall()
        by_project = conn.execute(
            f"""
            SELECT COALESCE(p.name, 'Sin proyecto') AS project,
                   COALESCE(p.slug, '') AS project_slug,
                   COALESCE(SUM(sub.amount), 0) AS total,
                   COUNT(*) AS count
            FROM (
                SELECT DISTINCT e.id, e.amount, e.project_id FROM expenses e
                {joins}
                {where}
            ) sub
            LEFT JOIN projects p ON p.id = sub.project_id
            GROUP BY sub.project_id ORDER BY total DESC
            """,
            params,
        ).fetchall()
    enriched = dict(category_row)
    if parent:
        enriched["parent_slug"] = parent["slug"]
        enriched["parent_name"] = parent["name"]
    return {
        "category": enriched,
        "total_amount": total["total"],
        "expense_count": total["count"],
        "by_month": rows_to_dicts(by_month),
        "by_project": rows_to_dicts(by_project),
    }


def person_summary(
    person: str | int,
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | int | None = None,
    project: str | int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        person_row = _get_person_by_ref(conn, person)
        date_clauses, date_params, _ = _expense_filter_parts(
            conn,
            start_date=start_date,
            end_date=end_date,
            category=category,
            project=project,
            currency=currency,
        )
        date_where = _where_clause(date_clauses)
        date_and = f"{date_where} AND" if date_where else "WHERE"
        paid_params = [*date_params, person_row["id"]]
        paid_total = conn.execute(
            f"""
            SELECT COALESCE(SUM(e.amount), 0) AS total, COUNT(*) AS count
            FROM expenses e
            {date_and} e.paid_by_person_id = ?
            """,
            paid_params,
        ).fetchone()
        attributed_params = [*date_params, person_row["id"]]
        attributed_total = conn.execute(
            f"""
            SELECT COALESCE(SUM(e.amount * ea.percentage / 100.0), 0) AS total,
                   COUNT(DISTINCT e.id) AS count
            FROM expenses e
            JOIN expense_allocations ea ON ea.expense_id = e.id
            {date_and} ea.person_id = ?
            """,
            attributed_params,
        ).fetchone()
        by_category = conn.execute(
            f"""
            SELECT {_category_parent_select("c")},
                   COALESCE(SUM(e.amount * ea.percentage / 100.0), 0) AS attributed_total,
                   COUNT(DISTINCT e.id) AS count
            FROM expenses e
            JOIN expense_allocations ea ON ea.expense_id = e.id
            JOIN categories c ON c.id = e.category_id
            LEFT JOIN categories pc ON pc.id = c.parent_id
            {date_and} ea.person_id = ?
            GROUP BY c.id ORDER BY attributed_total DESC
            """,
            attributed_params,
        ).fetchall()
        by_project = conn.execute(
            f"""
            SELECT COALESCE(p.name, 'Sin proyecto') AS project,
                   COALESCE(p.slug, '') AS project_slug,
                   COALESCE(SUM(e.amount * ea.percentage / 100.0), 0) AS attributed_total,
                   COUNT(DISTINCT e.id) AS count
            FROM expenses e
            JOIN expense_allocations ea ON ea.expense_id = e.id
            LEFT JOIN projects p ON p.id = e.project_id
            {date_and} ea.person_id = ?
            GROUP BY e.project_id ORDER BY attributed_total DESC
            """,
            attributed_params,
        ).fetchall()
    return {
        "person": person_row,
        "paid_total": paid_total["total"],
        "paid_count": paid_total["count"],
        "attributed_total": attributed_total["total"],
        "attributed_count": attributed_total["count"],
        "by_category": rows_to_dicts(by_category),
        "by_project": rows_to_dicts(by_project),
    }


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    start = f"{year:04d}-{month:02d}-01"
    end_exclusive = f"{year + 1:04d}-01-01" if month == 12 else f"{year:04d}-{month + 1:02d}-01"
    return start, end_exclusive


def _period_aggregate(
    conn,
    *,
    start_date: str,
    end_exclusive: str | None = None,
    end_date: str | None = None,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    clauses, params, joins = _expense_filter_parts(
        conn,
        start_date=start_date,
        end_exclusive=end_exclusive,
        end_date=end_date,
        category=category,
        project=project,
        paid_by=paid_by,
        allocated_to=allocated_to,
        currency=currency,
    )
    where = _where_clause(clauses)
    total = conn.execute(
        f"""
        SELECT COALESCE(SUM(sub.amount), 0) AS total, COUNT(*) AS count
        FROM (
            SELECT DISTINCT e.id, e.amount FROM expenses e
            {joins}
            {where}
        ) sub
        """,
        params,
    ).fetchone()
    by_category = conn.execute(
        f"""
        SELECT c.slug AS category_slug, c.name AS category,
               COALESCE(SUM(sub.amount), 0) AS total
        FROM (
            SELECT DISTINCT e.id, e.amount, e.category_id FROM expenses e
            {joins}
            {where}
        ) sub
        JOIN categories c ON c.id = sub.category_id
        GROUP BY c.id ORDER BY total DESC
        """,
        params,
    ).fetchall()
    return {
        "total_amount": total["total"],
        "expense_count": total["count"],
        "by_category": rows_to_dicts(by_category),
    }


def compare_periods(
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    datetime.strptime(period_a_start, "%Y-%m-%d")
    datetime.strptime(period_a_end, "%Y-%m-%d")
    datetime.strptime(period_b_start, "%Y-%m-%d")
    datetime.strptime(period_b_end, "%Y-%m-%d")
    filters = {
        "category": category,
        "project": project,
        "paid_by": paid_by,
        "allocated_to": allocated_to,
        "currency": currency.upper() if currency else None,
    }
    with connect() as conn:
        period_a = _period_aggregate(
            conn,
            start_date=period_a_start,
            end_date=period_a_end,
            category=category,
            project=project,
            paid_by=paid_by,
            allocated_to=allocated_to,
            currency=currency,
        )
        period_b = _period_aggregate(
            conn,
            start_date=period_b_start,
            end_date=period_b_end,
            category=category,
            project=project,
            paid_by=paid_by,
            allocated_to=allocated_to,
            currency=currency,
        )
        cat_map_a = {row["category_slug"]: row["total"] for row in period_a["by_category"]}
        cat_map_b = {row["category_slug"]: row["total"] for row in period_b["by_category"]}
        all_slugs = sorted(set(cat_map_a) | set(cat_map_b))
        by_category = []
        for slug in all_slugs:
            a_total = cat_map_a.get(slug, 0.0)
            b_total = cat_map_b.get(slug, 0.0)
            name = next(
                (r["category"] for r in period_a["by_category"] if r["category_slug"] == slug),
                next((r["category"] for r in period_b["by_category"] if r["category_slug"] == slug), slug),
            )
            by_category.append(
                {
                    "category": name,
                    "category_slug": slug,
                    "period_a_total": a_total,
                    "period_b_total": b_total,
                    "delta_amount": b_total - a_total,
                }
            )
    delta = period_b["total_amount"] - period_a["total_amount"]
    delta_pct = None
    if period_a["total_amount"] > 0:
        delta_pct = round((delta / period_a["total_amount"]) * 100, 2)
    return {
        "period_a": {"start": period_a_start, "end": period_a_end, **period_a},
        "period_b": {"start": period_b_start, "end": period_b_end, **period_b},
        "filters": filters,
        "delta_amount": delta,
        "delta_percent": delta_pct,
        "by_category": by_category,
    }


def compare_months(
    month_a: int,
    month_b: int,
    year_a: int | None = None,
    year_b: int | None = None,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    if not 1 <= month_a <= 12 or not 1 <= month_b <= 12:
        raise ValidationError("month_a and month_b must be between 1 and 12")
    now_year = datetime.now().year
    year_a_val = year_a or now_year
    year_b_val = year_b if year_b is not None else year_a_val
    start_a, end_a = _month_bounds(year_a_val, month_a)
    start_b, end_b = _month_bounds(year_b_val, month_b)
    end_a_inclusive = (datetime.strptime(end_a, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
    end_b_inclusive = (datetime.strptime(end_b, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
    result = compare_periods(
        start_a,
        end_a_inclusive,
        start_b,
        end_b_inclusive,
        category=category,
        project=project,
        paid_by=paid_by,
        allocated_to=allocated_to,
        currency=currency,
    )
    result["month_a"] = {"year": year_a_val, "month": month_a}
    result["month_b"] = {"year": year_b_val, "month": month_b}
    return result


def top_expenses(
    limit: int = 10,
    start_date: str | None = None,
    end_date: str | None = None,
    year: int | None = None,
    month: int | None = None,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    allocated_to: str | int | None = None,
    currency: str | None = None,
    sort_by: Literal["amount_desc", "amount_asc", "date_desc", "date_asc"] = "amount_desc",
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise ValidationError("limit must be between 1 and 100")
    if year is not None and month is not None:
        start_date, end_exclusive = _month_bounds(year, month)
        end_date = (datetime.strptime(end_exclusive, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
    order_map = {
        "amount_desc": "e.amount DESC, e.expense_date DESC",
        "amount_asc": "e.amount ASC, e.expense_date ASC",
        "date_desc": "e.expense_date DESC, e.amount DESC",
        "date_asc": "e.expense_date ASC, e.amount ASC",
    }
    if sort_by not in order_map:
        raise ValidationError(f"Invalid sort_by: {sort_by}")
    with connect() as conn:
        clauses, params, joins = _expense_filter_parts(
            conn,
            start_date=start_date,
            end_date=end_date,
            category=category,
            project=project,
            paid_by=paid_by,
            allocated_to=allocated_to,
            currency=currency,
        )
        where = _where_clause(clauses)
        rows = conn.execute(
            f"""
            SELECT DISTINCT e.id FROM expenses e
            {joins}
            {where}
            ORDER BY {order_map[sort_by]}
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        items = [_expense_with_relations(conn, row["id"]) for row in rows]
    return {
        "items": items,
        "limit": limit,
        "sort_by": sort_by,
        "period": {"start_date": start_date, "end_date": end_date, "year": year, "month": month},
    }


def export_expenses(
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
    if export_format not in {"csv", "json"}:
        raise ValidationError("export_format must be 'csv' or 'json'")
    if limit < 1 or limit > 50000:
        raise ValidationError("limit must be between 1 and 50000")
    with connect() as conn:
        clauses, params, joins = _expense_filter_parts(
            conn,
            start_date=start_date,
            end_date=end_date,
            category=category,
            project=project,
            paid_by=paid_by,
            allocated_to=allocated_to,
            currency=currency,
        )
        where = _where_clause(clauses)
        total_count = conn.execute(
            f"SELECT COUNT(DISTINCT e.id) AS c FROM expenses e{joins} {where}",
            params,
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT DISTINCT e.id FROM expenses e
            {joins}
            {where}
            ORDER BY e.expense_date DESC, e.id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        items = [_expense_with_relations(conn, row["id"]) for row in rows]
    if export_format == "json":
        content = json.dumps(items, ensure_ascii=False, indent=2, default=str)
    else:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "id",
                "expense_date",
                "description",
                "amount",
                "currency",
                "category",
                "project",
                "paid_by",
                "allocations",
                "notes",
            ]
        )
        for item in items:
            allocs = "; ".join(
                f"{a['person_slug']}:{a['percentage']}%" for a in item.get("allocations", [])
            )
            writer.writerow(
                [
                    item["id"],
                    item["expense_date"],
                    item["description"],
                    item["amount"],
                    item["currency"],
                    item["category"]["name"] if item.get("category") else "",
                    item["project"]["name"] if item.get("project") else "",
                    item["paid_by"]["display_name"] if item.get("paid_by") else "",
                    allocs,
                    item.get("notes") or "",
                ]
            )
        content = buffer.getvalue()
    return {
        "format": export_format,
        "row_count": len(items),
        "total_count": total_count,
        "truncated": total_count > len(items),
        "content": content,
    }


def set_category_budget(
    category: str | int,
    monthly_amount: float,
    currency: str = "ARS",
    alert_threshold_pct: float = 100.0,
    notes: str | None = None,
) -> dict[str, Any]:
    if monthly_amount < 0:
        raise ValidationError("monthly_amount must be >= 0")
    if alert_threshold_pct <= 0:
        raise ValidationError("alert_threshold_pct must be > 0")
    with connect() as conn:
        category_row = _get_category_by_ref(conn, category)
        existing = conn.execute(
            "SELECT id FROM category_budgets WHERE category_id = ?",
            (category_row["id"],),
        ).fetchone()
        if existing:
            raise ValidationError(
                f"Budget already exists for category {category_row['slug']}. Use update_category_budget."
            )
        conn.execute(
            """
            INSERT INTO category_budgets (
                category_id, monthly_amount, currency, alert_threshold_pct, notes
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                category_row["id"],
                float(monthly_amount),
                currency.upper(),
                float(alert_threshold_pct),
                notes,
            ),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT b.*, c.slug AS category_slug, c.name AS category_name
            FROM category_budgets b
            JOIN categories c ON c.id = b.category_id
            WHERE b.category_id = ?
            """,
            (category_row["id"],),
        ).fetchone()
    return row_to_dict(row)


def update_category_budget(
    category: str | int,
    monthly_amount: float | None = None,
    currency: str | None = None,
    alert_threshold_pct: float | None = None,
    is_active: bool | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        category_row = _get_category_by_ref(conn, category)
        row = conn.execute(
            "SELECT * FROM category_budgets WHERE category_id = ?",
            (category_row["id"],),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"No budget for category: {category}")
        if monthly_amount is not None and monthly_amount < 0:
            raise ValidationError("monthly_amount must be >= 0")
        if alert_threshold_pct is not None and alert_threshold_pct <= 0:
            raise ValidationError("alert_threshold_pct must be > 0")
        conn.execute(
            """
            UPDATE category_budgets
            SET monthly_amount = COALESCE(?, monthly_amount),
                currency = COALESCE(?, currency),
                alert_threshold_pct = COALESCE(?, alert_threshold_pct),
                is_active = COALESCE(?, is_active),
                notes = COALESCE(?, notes),
                updated_at = datetime('now')
            WHERE category_id = ?
            """,
            (
                monthly_amount,
                currency.upper() if currency else None,
                alert_threshold_pct,
                int(is_active) if is_active is not None else None,
                notes,
                category_row["id"],
            ),
        )
        conn.commit()
        updated = conn.execute(
            """
            SELECT b.*, c.slug AS category_slug, c.name AS category_name
            FROM category_budgets b
            JOIN categories c ON c.id = b.category_id
            WHERE b.category_id = ?
            """,
            (category_row["id"],),
        ).fetchone()
    return row_to_dict(updated)


def delete_category_budget(category: str | int) -> dict[str, Any]:
    with connect() as conn:
        category_row = _get_category_by_ref(conn, category)
        row = conn.execute(
            """
            SELECT b.*, c.slug AS category_slug, c.name AS category_name
            FROM category_budgets b
            JOIN categories c ON c.id = b.category_id
            WHERE b.category_id = ?
            """,
            (category_row["id"],),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"No budget for category: {category}")
        conn.execute("DELETE FROM category_budgets WHERE category_id = ?", (category_row["id"],))
        conn.commit()
    return {"deleted": True, "budget": row_to_dict(row)}


def list_category_budgets(active_only: bool = True) -> list[dict[str, Any]]:
    query = """
        SELECT b.*, c.slug AS category_slug, c.name AS category_name
        FROM category_budgets b
        JOIN categories c ON c.id = b.category_id
    """
    if active_only:
        query += " WHERE b.is_active = 1"
    query += " ORDER BY c.name"
    with connect() as conn:
        rows = conn.execute(query).fetchall()
    return rows_to_dicts(rows)


def budget_status(
    year: int,
    month: int,
    alerts_only: bool = False,
) -> dict[str, Any]:
    if not 1 <= month <= 12:
        raise ValidationError("month must be between 1 and 12")
    start, end_exclusive = _month_bounds(year, month)
    with connect() as conn:
        budgets = conn.execute(
            """
            SELECT b.*, c.slug AS category_slug, c.name AS category_name
            FROM category_budgets b
            JOIN categories c ON c.id = b.category_id
            WHERE b.is_active = 1
            ORDER BY c.name
            """
        ).fetchall()
        items: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []
        for budget in budgets:
            spent_row = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count
                FROM expenses
                WHERE category_id = ? AND expense_date >= ? AND expense_date < ?
                  AND currency = ?
                """,
                (budget["category_id"], start, end_exclusive, budget["currency"]),
            ).fetchone()
            spent = spent_row["total"]
            budgeted = budget["monthly_amount"]
            remaining = budgeted - spent
            pct_used = round((spent / budgeted) * 100, 2) if budgeted > 0 else (100.0 if spent > 0 else 0.0)
            alert = pct_used >= budget["alert_threshold_pct"]
            entry = {
                "category": budget["category_name"],
                "category_slug": budget["category_slug"],
                "currency": budget["currency"],
                "budgeted": budgeted,
                "spent": spent,
                "remaining": remaining,
                "percent_used": pct_used,
                "alert_threshold_pct": budget["alert_threshold_pct"],
                "alert_triggered": alert,
                "expense_count": spent_row["count"],
            }
            if alert:
                alerts.append(entry)
            if not alerts_only or alert:
                items.append(entry)
    return {
        "period": {"year": year, "month": month, "start": start, "end_exclusive": end_exclusive},
        "items": items,
        "alerts": alerts,
        "alert_count": len(alerts),
    }


def _recurring_with_relations(conn, recurring_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM recurring_expenses WHERE id = ?", (recurring_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"Recurring expense not found: {recurring_id}")
    rec = row_to_dict(row)
    rec["category"] = _get_category_by_ref(conn, rec["category_id"])
    rec["project"] = _get_project_by_ref(conn, rec["project_id"]) if rec["project_id"] else None
    rec["paid_by"] = _get_person_by_ref(conn, rec["paid_by_person_id"])
    alloc_rows = conn.execute(
        """
        SELECT ra.person_id, ra.percentage, p.slug AS person_slug, p.display_name AS person_name
        FROM recurring_allocations ra
        JOIN persons p ON p.id = ra.person_id
        WHERE ra.recurring_id = ?
        ORDER BY ra.person_id
        """,
        (recurring_id,),
    ).fetchall()
    rec["allocations"] = [
        {
            "person_id": r["person_id"],
            "person_slug": r["person_slug"],
            "person_name": r["person_name"],
            "percentage": r["percentage"],
        }
        for r in alloc_rows
    ]
    return rec


def create_recurring_expense(
    description: str,
    category: str | int,
    paid_by: str | int,
    frequency: str,
    start_date: str,
    suggested_amount: float | None = None,
    currency: str = "ARS",
    interval: int = 1,
    anchor_day: int | None = None,
    anchor_month: int | None = None,
    project: str | int | None = None,
    notes: str | None = None,
    allocations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if frequency not in _FREQUENCIES:
        raise ValidationError(f"frequency must be one of {_FREQUENCIES}")
    if interval < 1:
        raise ValidationError("interval must be >= 1")
    if suggested_amount is not None and suggested_amount < 0:
        raise ValidationError("suggested_amount must be >= 0")
    datetime.strptime(start_date, "%Y-%m-%d")
    start = date.fromisoformat(start_date)
    resolved_anchor_day = anchor_day if anchor_day is not None else start.day
    resolved_anchor_month = anchor_month if anchor_month is not None else start.month
    with connect() as conn:
        category_row = _get_category_by_ref(conn, category)
        paid_by_row = _get_person_by_ref(conn, paid_by)
        project_row = _get_accessible_project_by_ref(conn, project) if project else None
        caller = _get_caller_person(conn)
        normalized_allocations = _resolve_allocations(conn, allocations, paid_by_row["id"])
        cur = conn.execute(
            """
            INSERT INTO recurring_expenses (
                description, suggested_amount, currency, category_id, project_id,
                paid_by_person_id, notes, frequency, interval, anchor_day, anchor_month,
                start_date, next_due_date, created_by_person_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                description.strip(),
                float(suggested_amount) if suggested_amount is not None else None,
                currency.upper(),
                category_row["id"],
                project_row["id"] if project_row else None,
                paid_by_row["id"],
                notes,
                frequency,
                int(interval),
                resolved_anchor_day,
                resolved_anchor_month,
                start_date,
                start_date,
                caller["id"] if caller else None,
            ),
        )
        recurring_id = cur.lastrowid
        for alloc in normalized_allocations:
            conn.execute(
                "INSERT INTO recurring_allocations (recurring_id, person_id, percentage) VALUES (?, ?, ?)",
                (recurring_id, alloc["person_id"], alloc["percentage"]),
            )
        conn.commit()
        return _recurring_with_relations(conn, recurring_id)


def list_recurring_expenses(active_only: bool = False) -> list[dict[str, Any]]:
    with connect() as conn:
        clause = "WHERE is_active = 1" if active_only else ""
        rows = conn.execute(
            f"SELECT id FROM recurring_expenses {clause} ORDER BY next_due_date, id"
        ).fetchall()
        return [_recurring_with_relations(conn, r["id"]) for r in rows]


def update_recurring_expense(
    recurring_id: int,
    description: str | None = None,
    suggested_amount: float | None = None,
    currency: str | None = None,
    category: str | int | None = None,
    project: str | int | None = None,
    paid_by: str | int | None = None,
    notes: str | None = None,
    frequency: str | None = None,
    interval: int | None = None,
    anchor_day: int | None = None,
    anchor_month: int | None = None,
    start_date: str | None = None,
    is_active: bool | None = None,
    allocations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if frequency is not None and frequency not in _FREQUENCIES:
        raise ValidationError(f"frequency must be one of {_FREQUENCIES}")
    if interval is not None and interval < 1:
        raise ValidationError("interval must be >= 1")
    if suggested_amount is not None and suggested_amount < 0:
        raise ValidationError("suggested_amount must be >= 0")
    if start_date is not None:
        datetime.strptime(start_date, "%Y-%m-%d")
    with connect() as conn:
        current = conn.execute(
            "SELECT * FROM recurring_expenses WHERE id = ?", (recurring_id,)
        ).fetchone()
        if current is None:
            raise NotFoundError(f"Recurring expense not found: {recurring_id}")
        category_id = _get_category_by_ref(conn, category)["id"] if category is not None else None
        project_id = (_get_accessible_project_by_ref(conn, project)["id"] if project else None) if project is not None else current["project_id"]
        paid_by_id = _get_person_by_ref(conn, paid_by)["id"] if paid_by is not None else None

        conn.execute(
            """
            UPDATE recurring_expenses
            SET description = COALESCE(?, description),
                suggested_amount = CASE WHEN ? = 1 THEN ? ELSE suggested_amount END,
                currency = COALESCE(?, currency),
                category_id = COALESCE(?, category_id),
                project_id = ?,
                paid_by_person_id = COALESCE(?, paid_by_person_id),
                notes = COALESCE(?, notes),
                frequency = COALESCE(?, frequency),
                interval = COALESCE(?, interval),
                anchor_day = COALESCE(?, anchor_day),
                anchor_month = COALESCE(?, anchor_month),
                start_date = COALESCE(?, start_date),
                is_active = COALESCE(?, is_active),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                description.strip() if description else None,
                1 if suggested_amount is not None else 0,
                float(suggested_amount) if suggested_amount is not None else None,
                currency.upper() if currency else None,
                category_id,
                project_id,
                paid_by_id,
                notes,
                frequency,
                int(interval) if interval is not None else None,
                anchor_day,
                anchor_month,
                start_date,
                (1 if is_active else 0) if is_active is not None else None,
                recurring_id,
            ),
        )

        # If cadence/anchor/start changed, recompute next_due_date from start_date.
        if frequency is not None or interval is not None or start_date is not None or anchor_day is not None or anchor_month is not None:
            row = conn.execute("SELECT start_date FROM recurring_expenses WHERE id = ?", (recurring_id,)).fetchone()
            conn.execute(
                "UPDATE recurring_expenses SET next_due_date = ? WHERE id = ?",
                (row["start_date"], recurring_id),
            )

        if allocations is not None:
            row = conn.execute("SELECT paid_by_person_id FROM recurring_expenses WHERE id = ?", (recurring_id,)).fetchone()
            normalized = _resolve_allocations(conn, allocations, row["paid_by_person_id"])
            conn.execute("DELETE FROM recurring_allocations WHERE recurring_id = ?", (recurring_id,))
            for alloc in normalized:
                conn.execute(
                    "INSERT INTO recurring_allocations (recurring_id, person_id, percentage) VALUES (?, ?, ?)",
                    (recurring_id, alloc["person_id"], alloc["percentage"]),
                )
        conn.commit()
        return _recurring_with_relations(conn, recurring_id)


def delete_recurring_expense(recurring_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT id FROM recurring_expenses WHERE id = ?", (recurring_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Recurring expense not found: {recurring_id}")
        referenced = conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE recurring_id = ?", (recurring_id,)
        ).fetchone()["c"]
        if referenced:
            conn.execute(
                "UPDATE recurring_expenses SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
                (recurring_id,),
            )
            conn.commit()
            return {"hard_deleted": False, "deactivated": True, "id": recurring_id}
        conn.execute("DELETE FROM recurring_allocations WHERE recurring_id = ?", (recurring_id,))
        conn.execute("DELETE FROM recurring_expenses WHERE id = ?", (recurring_id,))
        conn.commit()
        return {"hard_deleted": True, "deactivated": False, "id": recurring_id}


def health_check() -> dict[str, Any]:
    db_path = init_db(seed=False)
    with connect() as conn:
        persons = conn.execute("SELECT COUNT(*) AS c FROM persons").fetchone()["c"]
        projects = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
        categories = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
        expenses = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
        budgets = conn.execute("SELECT COUNT(*) AS c FROM category_budgets").fetchone()["c"]
    return {
        "status": "ok",
        "db_path": str(db_path),
        "counts": {
            "persons": persons,
            "projects": projects,
            "categories": categories,
            "expenses": expenses,
            "budgets": budgets,
        },
    }
