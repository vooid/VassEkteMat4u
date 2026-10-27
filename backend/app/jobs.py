"""Daily job: reminders 7 days before the event (US-11) and the 5-day lock (basic_desc.txt, US-25).

Run once a day, e.g. from cron: `flask --app app run-daily-jobs` (see README). Running it twice on the same day does
no harm: each order is reminded and locked once. The 5-day rule itself is checked by date everywhere
(`orders.is_locked`), so a day the job doesn't run never lets a customer change a locked order; the job records
`locked_at` and tells the admin.
"""
from datetime import date, timedelta

from flask import current_app, url_for

from . import mail, orders
from .i18n import format_date, format_event, t_in
from .repositories import orders as orders_repo

ADMIN_LANGUAGE = "no"


def run_daily(on: date | None = None) -> dict:
    on = on or orders.today()
    lock_until = orders.lock_until(on)
    # No web request here, so links in e-mails are built from SITE_URL.
    with current_app.test_request_context(base_url=current_app.config["SITE_URL"]):
        reminded = orders_repo.take_reminders(on + timedelta(days=orders.REMINDER_DAYS), lock_until)
        for row in reminded:
            _send_reminder(row)
        locked = orders_repo.lock_due(orders.CUSTOMER_CHANGEABLE, lock_until)
        if locked:
            _send_lock_summary(locked, on)
    return {"reminded": [r["order"]["id"] for r in reminded], "locked": [o["id"] for o in locked]}


def _send_reminder(row: dict) -> None:
    order, customer = row["order"], row["customer"]
    lang = customer.get("language")
    event = row["event_type"].get(f"name_{lang}") or row["event_type"]["name_no"]
    body = t_in(lang, "mail_reminder_body", name=customer["name"], id=order["id"], event=event,
                date=format_event(order["event_date"], order.get("event_time"), lang), guests=order["guests"],
                last_day=format_date(orders.last_change_date(order["event_date"]), lang),
                url=url_for("orders.detail", order_id=order["id"], _external=True))
    mail.send(customer["email"], t_in(lang, "mail_reminder_subject", id=order["id"]), body)


def _send_lock_summary(locked: list[dict], on: date) -> None:
    lines = [t_in(ADMIN_LANGUAGE, "mail_locked_line", id=o["id"], date=format_date(o["event_date"], ADMIN_LANGUAGE),
                  event=o["event_type"]["name_no"], guests=o["guests"],
                  status=t_in(ADMIN_LANGUAGE, "status_" + o["status"])) for o in locked]
    waiting = [o["id"] for o in locked if o["status"] == "submitted"]
    body = t_in(ADMIN_LANGUAGE, "mail_locked_body", n=len(locked), lines="\n".join(lines),
                url=url_for("admin.order_list", _external=True))
    if waiting:
        # Open question 2 in state_order.md: what happens to orders nobody approved before the lock.
        body += "\n\n" + t_in(ADMIN_LANGUAGE, "mail_locked_waiting", ids=", ".join(waiting))
    mail.send_to_admins(t_in(ADMIN_LANGUAGE, "mail_locked_subject", n=len(locked),
                             date=format_date(on, ADMIN_LANGUAGE)), body)
