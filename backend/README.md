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

Create a staff account for the admin pages (the password is asked for twice, so it stays out of the shell history):

```sh
.venv/bin/flask --app app create-staff ingrid@ektemat.no --name "Ingrid Solheim" --role admin
```

Run the daily job once a day (reminders 7 days before the event, lock 5 days before, summary e-mail to the admins).
Running it twice on the same day is harmless. Use `--date YYYY-MM-DD` to try it as if it were another day:

```sh
.venv/bin/flask --app app run-daily-jobs
```

On a server, schedule it with cron, e.g. every morning at 06:00 Norwegian time (set `SITE_URL` in `.env` so the links
in the e-mails point to the real site):

```
0 6 * * *  cd /path/to/backend && .venv/bin/flask --app app run-daily-jobs >> daily-jobs.log 2>&1
```

The 5-day rule itself is checked by date on every request, so a day the job doesn't run never opens a locked order.

Roles are `admin`, `kitchen` and `driver`; each lands on its own screen after logging in. Staff log in at
`/staff/login` with e-mail and password; there is no self-registration for staff. Kitchen and driver staff can also log
in at `/staff/pin` by picking their name and typing a 4–8 digit PIN, set by someone with server access (asked for
twice, like the password):

```sh
.venv/bin/flask --app app create-staff mateo@ektemat.no --name "Mateo" --role kitchen
.venv/bin/flask --app app set-pin mateo@ektemat.no
```

Five wrong PINs in a row block that person's PIN login for 15 minutes (the password still works). Admins can't use a
PIN.

PIN login only works on devices an admin has approved: log in as an admin on the kitchen tablet or the driver's phone,
open **Devices** (`/admin/devices`), give the device a name and approve it, then log out. The device keeps a random
token in a cookie for a year (only its hash is stored); removing the device in the list stops its PIN login at once.
An IP allow-list wouldn't work, because drivers are on mobile data.

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
| `/order` | Checkout (logged in): event date and time (06:00–23:00), delivery address and notes, allergies and diets per guest group, payment option. Creates the order as *Submitted* | US-06, US-07 |
| `/orders` | The customer's orders, current and past, with status and payment status | US-08 |
| `/orders/<id>` | One order: dishes at the prices when ordered, guest groups, status history. Other customers' orders give 404 | US-08 |
| `/orders/<id>/change` | Change guests, time, dishes, guest groups and delivery notes until more than 5 days before the event. The minimum saved on the order applies; dishes already ordered keep their price. Changing an approved order e-mails the admins | US-09 |
| `POST /orders/<id>/cancel` | Cancel (with a confirmation tick) until more than 5 days before the event; the customer and the admins are e-mailed | US-10 |
| `POST /orders/<id>/questions` | Ask a question from the order page (any status); the answer shows on the order page. The admins are e-mailed | US-12 |
| `/staff/login` | Login for Ekte Mat staff (separate from customer login); admin → orders, kitchen → kitchen screen, driver → driver screen | – |
| `/staff/pin` | PIN login for kitchen and driver staff: pick your name, type your PIN. Only on approved devices (403 elsewhere) | US-27 |
| `/admin/devices` | Admin: approve the device you're using for PIN login, see when each device was last used, remove devices | US-27 |
| `/kitchen?day=YYYY-MM-DD` | Kitchen screen (kitchen and admin), today by default: orders in preparation, portions per dish, guest groups with allergies in red, an "Allergies seen" button that stores who and when. Refreshes every minute | US-27, US-28 |
| `/driver?day=YYYY-MM-DD` | Driver screen (driver and admin): the day's orders in preparation with address, map link, customer's phone and delivery notes; "Mark as delivered" | US-30 |
| `/admin/questions` | Admin: unanswered questions, newest first, linking to the order | US-26 |
| `/admin/orders` | Admin: all orders, filtered by status (default: submitted, approved, in preparation) and event-date range, with guests already booked that day | US-21, US-23 |
| `/admin/orders/<id>` | Admin: the whole order and the customer; approve, reject with reason, release to kitchen (5 days or less before the event), mark delivered, set payment status; capacity warning above 400 guests a day, 250 with a wedding; whether the kitchen has seen the allergies; questions with an answer form (the answer is e-mailed to the customer in their language) | US-22 – US-26, US-28 |
| `/admin/event-types` | Admin: change each event type's minimum guests (1–265) | US-20 |
| `/dev/outbox` | Development only (`DEV_OUTBOX`, on when `FLASK_DEBUG=1`): the e-mails the system would have sent | US-07 |

Each card's minimum order is the larger of the event type's current minimum and the dish's own minimum order quantity. The cart enforces the same rule per dish, and the number of guests must reach the event type's minimum
(`app/cart.py`). A cart is for one event type, because an order is.

Admin status changes follow the allowed-transitions table in
[`state_order.md`](../docs/diagrams/state_order.md) (`app/orders.py`: `ADMIN_TRANSITIONS`, `admin_actions()`). Each
change is saved as a `:StatusChange` with who did it and the reason, and only applies if the order still has the status
the admin saw, so two admins can't overwrite each other. Approving and rejecting e-mail the customer in their own
language.

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
| PUT | `/api/event-types/<id>/minimum` | Admin only (staff session; `401`/`403` otherwise): set minimum guests, body `{"min_guests": 1–265}`. Send the CSRF token in an `X-CSRFToken` header |

## Layout

```
app/
  __init__.py        create_app(): config, Neo4j driver, blueprints
  config.py          settings from environment / .env
  db.py              driver lifecycle + run(query, **params) helper
  cart.py            cart in the session + minimum-order rules (pure functions)
  auth.py            Flask-Login: customer and staff users, login checks, customer_required / staff_required
  urls.py            safe_next(): redirect only to local paths
  cli.py             flask create-staff, flask set-pin, flask run-daily-jobs
  jobs.py            the daily job: 7-day reminders, 5-day lock
  orders.py          checkout validation, 5-day rule, admin transitions, capacity (pure functions)
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
(with allergens, diets, images), `:Customer`, `:Staff`, `:Order` (with guest groups and status history) and
`:Question`/`:Answer` are implemented so far; the seed script creates the constraints and indexes marked `exists` there.

## Before production

- **Secrets:** never commit `.env`. Set a long random `SECRET_KEY` (it signs the session cookie). Serve over HTTPS and set `SESSION_COOKIE_SECURE=1`. Never publish the Claude API key (`CLAUDE.md`).
- **PIN login:** approve only Ekte Mat's own tablet and the drivers' work phones under Devices, remove a device that is lost or replaced, and change a PIN (`flask set-pin`) when someone leaves. Serve over HTTPS so the device cookie can't be read on the way.
- **Hosting:** the case requires data in the EU/EEA and running costs under 3 000 NOK/month (`docs/context/04_vision_scope_constraints/`). Check the region and price of any hosted Neo4j (e.g. Neo4j AuraDB) before choosing, and get a data processing agreement (GDPR note).
