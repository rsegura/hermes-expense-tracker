# Instrucciones para instalar (copiar a otra IA o persona)

Usá este texto cuando le pidas a alguien (o a un agente con terminal) que instale el producto en una máquina con Hermes.

---

## Objetivo

Instalar **Hermes Expense Tracker**: gastos compartidos del hogar. Cada miembro puede tener su bot Telegram; todos comparten una SQLite.

## Requisitos

- Python 3.11+ (`python3`, `python`, o `py` en Windows)
- [Hermes Agent](https://hermes-agent.nousresearch.com) >= 0.14.0 en PATH (`hermes --version`)
- macOS, Linux, WSL2 o **Windows nativo** (PowerShell 5.1+)
- Modelo y Telegram se configuran **después** en cada perfil Hermes — no es parte del instalador

## Pasos (Unix — bash)

```bash
cd ~
git clone https://github.com/Canopix/hermes-expense-tracker.git hermes-expense-tracker
cd hermes-expense-tracker
chmod +x install.sh bootstrap.sh add-member.sh update.sh
./install.sh
```

## Pasos (Windows — PowerShell)

```powershell
cd $HOME
git clone https://github.com/Canopix/hermes-expense-tracker.git hermes-expense-tracker
cd hermes-expense-tracker
.\install.ps1
```

El wizard:

1. Pregunta **idioma del hogar** (`English` / `Español`)
2. Muestra la **ruta de la base compartida** (default `~/.hermes/expense-tracker/expenses.db`) — Enter para default, o escribí otra ruta
3. Verifica Python + Hermes (con indicadores de progreso — usa Rich, como el CLI de Hermes)
4. En la **primera instalación**, prepara servidor + base en esa ruta (sin preguntar “bootstrap”)
5. En **reinstalación**, reutiliza la base existente si ya está
6. Pregunta cuántos miembros, nombre + slug de cada uno
7. Personas sin bot y proyectos iniciales (opcional)

## Después del install (por miembro, en orden)

| Paso | Comando |
|------|---------|
| 1. Modelo | `hermes -p alice setup` |
| 2. MCP test | `hermes -p expense-alice mcp test expense-tracker` |
| 3. Telegram | [@BotFather](https://t.me/BotFather) → `alice gateway setup && alice gateway start` |
| 4. Pairing | Escribir al bot → `hermes -p alice pairing approve telegram <CODIGO>` |
| 5. Chat | `alice chat` |

Borrar un perfil Hermes **no** borra la base de gastos (default `~/.hermes/expense-tracker/expenses.db`, o tu ruta custom en `~/.hermes/expense-tracker/db-path`).

## Onboarding en Hermes (conversacional)

Cuando el MCP ya funciona:

```bash
alice chat
```

Decir: *"Empecemos la configuración"* o *"Primera vez"*.

## Verificación (desarrolladores)

```bash
cd ~/hermes-expense-tracker/mcp/expense-tracker
.venv/bin/python -m unittest discover -s tests -v
```

## No hacer

- No commitear secrets del perfil ni tokens de Telegram
- No poner datos del hogar en el repo (solo en `~/.hermes/expense-tracker/expenses.db`)
