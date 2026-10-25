# Backend (Flask + Neo4j)

Skeleton for the Ekte Mat ordering system API. Conventions from `CLAUDE.md`: Flask for the backend, Neo4j for storage.

## Run it locally

Needs Python 3.11+ and Docker. From the repo root:

```sh
cp backend/.env.example backend/.env              # then set your own NEO4J_PASSWORD
docker compose --env-file backend/.env up -d      # Neo4j at http://localhost:7474
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m scripts.seed                  # constraints + example event types
.venv/bin/python run.py                           # API at http://localhost:5001
```

Port 5001 is the default because macOS AirPlay Receiver uses 5000. Change it with `PORT` in `.env`.

Run the tests (they use a fake driver, so no database is needed):

```sh
.venv/bin/python -m pytest
```

## Endpoints

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
  routes/            Flask blueprints (HTTP layer, validation)
  repositories/      Cypher queries, one module per node label
scripts/seed.py      constraints + example data (safe to re-run)
tests/               pytest with a fake Neo4j driver
run.py               dev server
```

To add a resource: put its Cypher in `repositories/<name>.py`, its endpoints in `routes/<name>.py`, register the blueprint in `app/__init__.py`, and add tests.

## Graph model (first draft)

Only `:EventType` is implemented. The rest is the planned model, with constraints already created by the seed script:

```
(:Customer {email})-[:PLACED]->(:Order {id, status, payment_status, payment_option,
                                        event_date, guests, min_guests_at_order, ...})
(:Order)-[:FOR_EVENT]->(:EventType {id, name_no, name_en, min_guests})
(:Order)-[:CONTAINS {quantity}]->(:FoodItem {id, name, price_nok, min_order_qty, ...})
(:FoodItem)-[:SUITS]->(:EventType)
```

`min_guests_at_order` stores the minimum in force when the order was placed, so later changes to an event type's minimum don't invalidate existing orders (`docs/requirements/basic_desc.txt`).

## Before production

- **Secrets:** never commit `.env`. Never publish the Claude API key (`CLAUDE.md`).
- **Hosting:** the case requires data in the EU/EEA and running costs under 3 000 NOK/month (`docs/context/04_vision_scope_constraints/`). Check the region and price of any hosted Neo4j (e.g. Neo4j AuraDB) before choosing, and get a data processing agreement (GDPR note).
