"""Member slug normalization and validation."""

from __future__ import annotations

import re
import sys


def normalize_member_slug(raw: str) -> str:
    slug = raw.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    while slug.startswith("expense-"):
        slug = slug[len("expense-") :]
    return slug


def validate_member_slug(slug: str) -> bool:
    if not slug:
        print("Slug vacío / empty slug", file=sys.stderr)
        return False
    if not re.fullmatch(r"[a-z][a-z0-9-]*", slug):
        print(
            f"Slug inválido '{slug}' (usá letras minúsculas, números y guiones)",
            file=sys.stderr,
        )
        return False
    if slug.startswith("expense-"):
        print("No uses prefijo expense- (ej. alice, no expense-alice)", file=sys.stderr)
        return False
    return True
