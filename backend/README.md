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
| `/cart` | Cart: guests, portions per dish, line totals and total, and whether the minimums are met | US-05, US-06 |
| `POST /cart/add`, `/cart/update`, `/cart/remove/<dish>`, `/cart/clear` | Change the cart (stored in the session) | US-05 |
| `/register` | Create a customer account (name, e-mail, phone, password ≥ 8 characters); logs in and keeps the cart | US-04 |
| `/login` | Log in with e-mail and password; a failed login gives one generic message | US-04 |
| `POST /logout` | Log out; the cart is cleared, the language is kept | US-04 |
| `/order` | Checkout (logged in): event date, delivery address and notes, allergies and diets per guest group, payment option. Creates the order as *Submitted* | US-06, US-07 |
| `/orders` | The customer's orders, current and past, with status and payment status | US-08 |
| `/orders/<id>` | One order: dishes at the prices when ordered, guest groups, status history. Other customers' orders give 404 | US-08 |
| `/dev/outbox` | Development only (`DEV_OUTBOX`, on when `FLASK_DEBUG=1`): the e-mails the system would have sent | US-07 |

Each card's minimum order is the larger of the event type's current minimum and the dish's own minimum order quantity. The cart enforces the same rule per dish, and the number of guests must reach the event type's minimum
(`app/cart.py`). A cart is for one event type, because an order is.

An order is created in one Cypher query (`repositories/orders.py`) that checks the minimums again against the
database and copies the event type's minimum and the dish prices onto the order, so later changes don't affect it. The
event date must be more than 5 days ahead (`app/orders.py`, assumption in US-07). Allergies are stored per guest group
as counts, never with names (GDPR). E-mail isn't sent yet: `app/mail.py` stores it in the development outbox.

Passwords are hashed with Werkzeug (scrypt). There is no e-mail password reset in this version (decision 2026-10-27).
A logged-in customer's language choice is saved on the account and restored at the next login. Redirects after login
only go to paths on this site (`app/urls.py`).

All HTML forms are protected against cross-site request forgery: include
`<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` in every `POST` form.

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
  cart.py            cart in the session + minimum-order rules (pure functions)
  auth.py            Flask-Login setup, customer user, registration checks, password hashing
  urls.py            safe_next(): redirect only to local paths
  orders.py          checkout validation, 5-day rule, current/past statuses (pure functions)
  mail.py            outgoing e-mail -> development outbox (no mail service yet)
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

The full data model is in [`docs/diagrams/data_model.md`](../docs/diagrams/data_model.md). `:EventType`, `:FoodItem`
(with allergens, diets, images), `:Customer` and `:Order` (with guest groups and status history) are implemented so
far; the seed script already creates the uniqueness constraints for `EventType`, `FoodItem`, `Customer`
and `Order`.

## Before production

- **Secrets:** never commit `.env`. Set a long random `SECRET_KEY` (it signs the session cookie). Serve over HTTPS and set `SESSION_COOKIE_SECURE=1`. Never publish the Claude API key (`CLAUDE.md`).
- **Hosting:** the case requires data in the EU/EEA and running costs under 3 000 NOK/month (`docs/context/04_vision_scope_constraints/`). Check the region and price of any hosted Neo4j (e.g. Neo4j AuraDB) before choosing, and get a data processing agreement (GDPR note).
