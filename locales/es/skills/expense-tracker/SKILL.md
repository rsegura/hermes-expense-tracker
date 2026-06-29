# Expense Tracker

Skill operativa para el MCP `expense-tracker`. Usá estas tools para todo dato financiero.

## Tools disponibles (prefijo Hermes: `mcp_expense_tracker_`)

### Personas
- `create_person(display_name, slug?, aliases?)`
- `update_person(person_ref, ...)`
- `list_persons()`
- `delete_person(person_ref)` — solo si no tiene gastos

### Proyectos (membresía por persona)
- `create_project(name, slug?, description?, members?)` — caller = owner; `members` = slugs invitados
- `update_project`, `list_projects(active_only?)` — lista solo proyectos visibles para el caller
- `add_project_member(project, person)` / `remove_project_member` — solo owner
- `list_project_members(project)` — requiere ser miembro
- `delete_project(project_ref, force?)` — solo owner; `force=true` desvincula gastos

Proyecto personal = sin `members`. Compartido = owner + `members`. Gastos sin proyecto siguen visibles para todos.

### Categorías
- `create_category`, `update_category`, `list_categories` (incluye `parent_slug`)
- `delete_category(category_ref, reassign_to?)` — mover gastos antes de borrar

### Gastos
- `add_expense(expense_date, description, amount, category, paid_by, currency?, project?, notes?, allocations?)`
- `update_expense`, `delete_expense`
- `list_expenses(start_date?, end_date?, category?, project?, paid_by?, allocated_to?, currency?, limit?, offset?)` → paginado (`items`, `total_count`, `has_more`)
- `search_expenses(query, start_date?, end_date?, min_amount?, max_amount?, currency?, limit?, offset?)`

### Comparación y exportación
- `compare_months(month_a, month_b, year_a?, year_b?, filtros…)` — ej. junio vs mayo
- `compare_periods(period_a_start, period_a_end, period_b_start, period_b_end, filtros…)`
- `top_expenses(limit?, year?, month?, sort_by?, filtros…)` — `sort_by`: `amount_desc`, `amount_asc`, `date_desc`, `date_asc`
- `export_expenses(export_format, filtros…)` — `csv` o `json`; devuelve `content` como texto
- `export_expenses_file(export_format, filtros…)` — guarda en `~/.hermes/expense-tracker/exports/`, devuelve `file_path`

### Reportes unificados y gráficos
- `generate_report(period?, year?, month?, project?, currency?, include_ascii_charts?)`
  - `period`: `month` (default), `year`, `project` (requiere `project`)
  - Devuelve `markdown` listo para Telegram + `summary`, `top_expenses`, alertas de presupuesto
  - Sin `currency` y con gastos en varias monedas: totales y categorías **separados por moneda** en un solo reporte (no suma mezclada)
  - Para una sola moneda: pasá `currency="USD"` (o la que corresponda)
- `render_chart(chart_type, year?, month?, project?)` → **imagen PNG**
  - `by_category` — torta del mes (o año si sin `month`)
  - `by_project` — barras horizontales por proyecto
  - `monthly_trend` — evolución mes a mes del año
  - `top_expenses` — top gastos del período
  - Guarda en `~/.hermes/expense-tracker/charts/`; **enviar la imagen** al usuario

### Presupuestos por categoría
- `set_category_budget(category, monthly_amount, currency?, alert_threshold_pct?, notes?)`
- `update_category_budget`, `delete_category_budget`, `list_category_budgets(active_only?)`
- `budget_status(year, month, alerts_only?)` — `spent` vs `budgeted`, `alert_triggered`

### Reportes (solo lectura)

Todos aceptan filtros opcionales salvo donde se indica el parámetro obligatorio.

- `monthly_summary(year, month, category?, project?, paid_by?, allocated_to?, currency?)`
  - Devuelve: total, `by_category`, `by_project`, `by_person` (atribuido)
- `yearly_summary(year, category?, project?, paid_by?, allocated_to?, currency?)`
  - Devuelve: total, `by_month`, `by_category`, `by_project`
- `project_summary(project, start_date?, end_date?, paid_by?, allocated_to?, currency?)`
- `category_summary(category, start_date?, end_date?, project?, paid_by?, allocated_to?, currency?)`
  - Devuelve: total, `by_month`, `by_project`
- `person_summary(person, start_date?, end_date?, category?, project?, currency?)`
  - Devuelve: `paid_total`, `attributed_total`, `by_category`, `by_project`

### Utilidad
- `health_check()`

## Allocations

- Cada gasto necesita allocations que sumen **100%**.
- Si el usuario no especifica reparto → 100% al `paid_by`.
- Ejemplo reparto 50/50:

```json
"allocations": [
  {"person": "alice", "percentage": 50},
  {"person": "bob", "percentage": 50}
]
```

## paid_by vs attributed

| Concepto | Significado |
|----------|-------------|
| `paid_by` | Quién sacó la plata (dato factual) |
| `allocated_to` / `attributed` | Cuánto le corresponde según % en allocations |

`person_summary` reporta ambos por separado. **No** hay deudas ni settlements.

## Ejemplos de consultas

- "¿Cuánto gastamos en junio?" → `generate_report(period="month", year=2026, month=6)` (si hay varias monedas, el reporte las separa)
- "¿Cuánto gastamos en USD este mes?" → `generate_report(period="month", year=2026, month=6, currency="USD")`
- "Resumen del casamiento" → `generate_report(period="project", project="casamiento")`
- "Gráfico de gastos por categoría" → `render_chart("by_category", year=2026, month=6)` + enviar imagen
- "Exportá junio en CSV" → `export_expenses_file("csv", start_date="2026-06-01", end_date="2026-06-30")`
- "¿Cuánto en hogar en junio?" → `monthly_summary(2026, 6, project="hogar")`
- "Creá proyecto Casamiento con Bob" → `create_project("Casamiento", members=["bob"])`
- "¿Qué proyectos tengo?" → `list_projects(active_only=true)`
- "Sumá a Bob al casamiento" → `add_project_member("casamiento", "bob")`
- "Gastos de alice en junio" → `list_expenses(allocated_to="alice", start_date="2026-06-01", end_date="2026-06-30")`
- "¿Cuánto pagué yo este año?" → `person_summary("<slug-del-usuario>", start_date="2026-01-01", end_date="2026-12-31")`
- "Buscar supermercado entre $5000 y $20000" → `search_expenses("supermercado", min_amount=5000, max_amount=20000)`
- "¿Junio vs mayo?" → `compare_months(6, 5, year_a=2026, year_b=2026)`
- "Top 5 gastos del mes" → `top_expenses(year=2026, month=6, limit=5)`
- "Exportá junio en CSV" → `export_expenses("csv", start_date="2026-06-01", end_date="2026-06-30")`
- "¿Superé el presupuesto de comida?" → `budget_status(2026, 6, alerts_only=true)`
- Listas largas → usar `offset` con `has_more`

## Formato de respuesta

- Listas o tablas compactas para reportes.
- Montos con separador de miles y moneda (ej. `$ 15.500 {{DEFAULT_CURRENCY}}`).
- Si falta un dato obligatorio, preguntá una sola cosa concreta.
- No narres tools ni pasos intermedios.

### Ejemplos (registrar gasto)

| Mal | Bien |
|-----|------|
| "No tengo Panadería, te la creo..." antes de registrar | Ir directo a tools; al terminar, confirmación estructurada |
| Una sola línea sin detalle | `Listo ✅` + bullets 📅💰🏷️👤📊 (ver SOUL) |
| Párrafo narrando cada tool | Solo el bloque de confirmación al final |

Ejemplo bueno:

```
Listo ✅

- 📅 Fecha: 06/06/2026
- 💰 Monto: $150.000 {{DEFAULT_CURRENCY}}
- 🏷️ Categoría: Hotel (Viajes)
- 👤 Pagador: Alice
- 📊 Reparto: 100% Alice

¿Algo más?
```

## Gastos recurrentes

Plantillas para gastos que se repiten (alquiler, suscripciones, facturas). Son **del hogar** — todos las ven y cualquiera puede materializar lo que vence. Nada se crea automáticamente; las ocurrencias se generan bajo demanda.

- `mcp_expense_tracker_create_recurring_expense` — define una plantilla: `description`, `category`, `paid_by`, `frequency` (`weekly`|`monthly`|`yearly`), `start_date` (AAAA-MM-DD). Opcional: `suggested_amount` (omítelo/null para facturas **variables** como la luz), `interval` (cada N), `anchor_day`, `anchor_month`, `project`, `notes`, `allocations`.
- `mcp_expense_tracker_list_recurring_expenses` — muestra todas las plantillas y su próxima fecha de vencimiento.
- `mcp_expense_tracker_list_due_recurring` — muestra las plantillas vencidas (`next_due_date <= hoy`).
- `mcp_expense_tracker_generate_recurring_expense` — crea un gasto real a partir de una plantilla. En plantillas **fijas** se usa el importe sugerido; en **variables** DEBES pasar `amount`. Avanza el calendario un periodo.
- `mcp_expense_tracker_update_recurring_expense` / `mcp_expense_tracker_delete_recurring_expense`.

**Cuando un miembro pregunte "¿qué toca pagar este mes?" o inicie una sesión:** llama a `list_due_recurring`. Para cada plantilla vencida: si es fija, confirma y genera; si es variable, pregunta el importe y luego genera. Si hay varios periodos atrasados, materialízalos de uno en uno (cada generación avanza un periodo).

## Recibos (fotos)

Cuando un miembro envíe una **foto de un recibo**, léela directamente (tu modelo es multimodal) y extrae:
- **importe** (total), **fecha**, **comercio** → úsalo como `description`, e infiere la **categoría** de las categorías existentes del hogar (`list_categories`).
- Pon `paid_by` por defecto en quien envió la foto.

Muestra una confirmación breve — Importe / Fecha / Comercio / Categoría — y solo tras la confirmación llama a `mcp_expense_tracker_add_expense`. Si un campo no se lee, pregunta **solo** por ese campo. La imagen no se guarda; solo se registra el gasto resultante.
