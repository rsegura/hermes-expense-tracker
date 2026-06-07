# Instrucciones para instalar (copiar a otra IA o persona)

Usá este texto cuando le pidas a alguien (o a un agente con terminal) que instale el producto en una máquina con Hermes.

---

## Objetivo

Instalar **Hermes Expense Tracker**: gastos compartidos del hogar. Cada miembro puede tener su bot Telegram; todos comparten una SQLite.

## Requisitos

- macOS o Linux con `python3` 3.11+
- [Hermes Agent](https://hermes-agent.nousresearch.com) >= 0.14.0 en PATH (`hermes --version`)
- Modelo y Telegram se configuran **después** en cada perfil Hermes (`config.yaml` / `hermes setup` / `gateway setup`) — no es parte de `install.sh`

`install.sh` verifica automáticamente python3, que `hermes` exista, responda, cumpla versión mínima y que `hermes profile list` funcione.

## Pasos (en terminal)

```bash
cd ~
git clone https://github.com/Canopix/hermes-expense-tracker.git hermes-expense-tracker
cd hermes-expense-tracker
chmod +x install.sh bootstrap.sh add-member.sh
./install.sh
```

El script `install.sh` pregunta interactivamente:

1. **Idioma del hogar** — `English` o `Español` (SOUL, skills y reportes)
2. Si correr bootstrap (MCP + DB) — decir que sí
3. **Cuántos miembros** tendrán bot propio
4. Por cada uno: **nombre** y **slug** (ej. `maria` / `María`)
5. Si hay personas **sin bot** (solo en gastos)
6. Si crear proyectos default (hogar, vacaciones, salud)

## Después del install (por cada miembro)

En la ruta que imprime `add-member.sh` (típico `~/.hermes/profiles/expense-<slug>/`):

1. Modelo: `hermes setup` o editar `config.yaml` del perfil
2. `<slug> gateway setup && <slug> gateway start`
3. `hermes -p <slug> pairing approve telegram <CODIGO>`
4. `hermes -p <slug> mcp test expense-tracker` → debe mostrar 38 tools

## Onboarding en Hermes (conversacional)

Cuando el MCP ya funciona:

```bash
<slug-principal> chat
```

Decir: *"Empecemos la configuración"* o *"Primera vez"*.

El agente (skill `onboarding`) guía: proyectos extra, presupuestos, primer gasto. **No** crea perfiles Hermes — eso solo vía `install.sh` / `add-member.sh`.

## Verificación

```bash
cd ~/hermes-expense-tracker/mcp/expense-tracker
.venv/bin/python -m unittest discover -s tests -v
```

## No hacer

- No commitear `config.yaml` con secrets ni tokens del perfil runtime
- No poner datos de personas reales en el repo (solo en `~/expenses/data/expenses.db`)
- No calcular deudas entre personas (fuera de scope)
