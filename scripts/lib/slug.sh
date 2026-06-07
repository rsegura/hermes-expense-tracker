#!/usr/bin/env bash
# Shared slug normalization for add-member / install wizard.

normalize_member_slug() {
  local raw="$1"
  local slug
  slug="$(echo "${raw}" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')"
  slug="${slug#expense-}"
  slug="${slug#expense-}"
  echo "${slug}"
}

validate_member_slug() {
  local slug="$1"
  if [[ -z "${slug}" ]]; then
    echo "Slug vacío" >&2
    return 1
  fi
  if [[ ! "${slug}" =~ ^[a-z][a-z0-9-]*$ ]]; then
    echo "Slug inválido '${slug}' (usá letras minúsculas, números y guiones)" >&2
    return 1
  fi
  if [[ "${slug}" == expense-* ]]; then
    echo "No uses slug con prefijo expense-; poné solo el nombre (ej. johanna)" >&2
    return 1
  fi
  return 0
}
