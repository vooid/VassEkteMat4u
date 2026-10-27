# Backend (Flask + Neo4j)

Skeleton for the Ekte Mat ordering system API. Conventions from `CLAUDE.md`: Flask for the backend, Neo4j for storage.

## Run it locally

Needs Python 3.11+ and Docker. From the repo root:

```sh
cp backend/.env.example backend/.env              # then set your own NEO4J_PASSWORD
docker compose --env-file backend/.env up -d      # Neo4j at http://localhost:7474
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m scripts.seed                  # constraints, event types, allergens, diets, sample dishes
.venv/bin/python run.py                           # site and API at http://localhost:5001
```

Port 5001 is the default because macOS AirPlay Receiver uses 5000. Change it with `PORT` in `.env`.

Run the tests. The unit tests use a fake driver, so no database is needed:

```sh
.venv/bin/python -m pytest
```

The integration tests run the real Cypher against your local Neo4j. They're skipped unless you opt in, because they
write sample data:

```sh
RUN_NEO4J_TESTS=1 .venv/bin/python -m pytest
```

## Pages

| Path | What it shows | Story |
|---|---|---|
| `/` | Menu: dishes as cards grouped by event type, with price, minimum order, allergens and diets | US-01 |
| `POST /language/<no\|en>` | Switches the interface language (stored in the session) | US-02 |

Each card's minimum order is the larger of the event type's current minimum and the dish's own minimum order quantity.

## API endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | `200` if Neo4j is reachable, `503` if not |
| GET | `/api/event-types` | Event types with their minimum guests |
| PUT | `/api/event-types/<id>/minimum` | Admin: set minimum guests, body `{"min_guests": 1–265}` |

## Layout

```
app/
  __init__.py        create_app(): config, Neo4j driver, blueprints
  config.py          settings from environment / .env
  db.py              driver lifecycle + run(query, **params) helper
  i18n.py            Norwegian/English: UI strings (TEXTS) and tr() for _no/_en data fields
  pages/             Flask blueprints that render HTML pages
  routes/            Flask blueprints for the JSON API (HTTP layer, validation)
  repositories/      Cypher queries, one module per feature or node label
  templates/         Jinja templates (base.html + one per page)
  static/            CSS and images
scripts/seed.py      constraints + sample data (safe to re-run; never overwrites admin changes)
tests/               pytest with a fake Neo4j driver; tests/integration/ runs against real Neo4j (opt-in)
run.py               dev server
```

To add a feature: put its Cypher in `repositories/<name>.py`, its pages in `pages/<name>.py` with templates in `templates/`, any JSON endpoints in `routes/<name>.py`, register the blueprints in `app/__init__.py`, add UI strings for both languages to `i18n.py`, and add tests.

## Graph model

The full data model is in [`docs/diagrams/data_model.md`](../docs/diagrams/data_model.md). Only `:EventType` is
implemented so far; the seed script already creates the uniqueness constraints for `EventType`, `FoodItem`, `Customer`
and `Order`.

## Before production

- **Secrets:** never commit `.env`. Set a long random `SECRET_KEY` (it signs the session cookie). Never publish the Claude API key (`CLAUDE.md`).
- **Hosting:** the case requires data in the EU/EEA and running costs under 3 000 NOK/month (`docs/context/04_vision_scope_constraints/`). Check the region and price of any hosted Neo4j (e.g. Neo4j AuraDB) before choosing, and get a data processing agreement (GDPR note).
