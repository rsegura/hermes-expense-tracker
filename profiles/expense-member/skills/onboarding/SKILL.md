# Onboarding — Expense Tracker

Skill para la **primera configuración** del hogar. Activá este flujo cuando el usuario quiera empezar, configurar, instalar, o diga "primera vez".

## Límites importantes

**No tenés terminal.** No podés correr `install.sh`, `add-member.sh` ni `hermes profile install`.

| Qué | Quién lo hace |
|-----|----------------|
| MCP, DB, perfiles Hermes, bots Telegram | Terminal: `./install.sh` o `./add-member.sh` |
| Personas solo en gastos (sin bot) | Vos: `create_person` |
| Proyectos, presupuestos, primer gasto | Vos: MCP tools |

Si `health_check` muestra `persons: 0`, explicá que primero debe correr `./install.sh` en la máquina. Ofrecé crear personas **sin bot** con `create_person` si ya tienen el MCP pero faltan personas en DB.

## Flujo guiado (una pregunta por turno)

1. **`health_check`** — confirmar MCP y DB.
2. **`list_persons`** — si vacío, indicar `./install.sh`; si hay personas, saludar por nombre.
3. **`list_projects`** — si vacío o pocos, preguntar: *"¿Qué proyectos querés trackear? (ej. casamiento, auto)"* → `create_project` por cada uno. Personal = sin `members`; compartido = `members=["slug-del-otro"]` (slugs de `list_persons`).
4. **Presupuestos (opcional)** — *"¿Querés presupuesto mensual por categoría?"* → `set_category_budget` con montos que indiquen.
5. **Primer gasto** — *"Registramos un gasto de prueba?"* → `add_expense` y confirmar resumen.
6. **Cierre** — recordar comandos útiles:
   - Reportes: `monthly_summary`, `compare_months`, `top_expenses`
   - Telegram: pairing con `hermes -p <slug> pairing approve telegram CODE`
   - Otro miembro con bot: `./add-member.sh <slug> <nombre>` en terminal

## Tono

- Español (Argentina), breve, una pregunta a la vez.
- No abrumar con todas las tools; mostrar lo esencial según lo que pida.
- Si ya está configurado, no repetir onboarding — pasar a modo gastos normal.

## Señales de que ya terminó el onboarding

- Hay personas en DB y al menos un gasto o proyecto custom.
- El usuario pide algo concreto ("¿cuánto gastamos?") → salir del flujo onboarding.
