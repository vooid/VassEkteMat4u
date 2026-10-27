"""Admin pages: orders (US-21 – US-25), answering questions (US-26) and event-type minimums (US-20).
Staff with role "admin" only."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .. import mail, orders
from ..auth import staff_required
from ..i18n import format_date, t, t_in
from ..repositories import event_types, questions
from ..repositories import kitchen as kitchen_repo
from ..repositories import orders as orders_repo

bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_only = staff_required("admin")

# What needs the admin's attention: to approve, to release, to deliver.
DEFAULT_STATUS_FILTER = ("submitted", "approved", "in_preparation")


@bp.get("")
@admin_only
def index():
    return redirect(url_for("admin.order_list"))


@bp.get("/orders")
@admin_only
def order_list():
    statuses = [s for s in request.args.getlist("status") if s in orders.ALL_STATUSES] or list(DEFAULT_STATUS_FILTER)
    date_from = orders.parse_date(request.args.get("from", ""))
    date_to = orders.parse_date(request.args.get("to", ""))
    rows = orders_repo.admin_list(statuses, date_from and date_from.isoformat(), date_to and date_to.isoformat(),
                                  orders.BOOKED_STATUSES)
    return render_template("admin_orders.html", rows=rows, statuses=statuses, date_from=date_from,
                           date_to=date_to, all_statuses=orders.ALL_STATUSES)


def _load(order_id: str) -> tuple[dict, dict]:
    order, customer = orders_repo.admin_get(order_id)
    if order is None:
        abort(404)
    return order, customer


@bp.get("/orders/<order_id>")
@admin_only
def order_detail(order_id: str):
    order, customer = _load(order_id)
    booked, wedding = orders_repo.booked_on(order["event_date"], order_id, orders.BOOKED_STATUSES, orders.WEDDING)
    return render_template("admin_order.html", order=order, customer=customer,
                           actions=orders.admin_actions(order),
                           payment_actions=orders.payment_actions(order),
                           capacity=orders.capacity(booked, wedding, order),
                           locked=orders.is_locked(order["event_date"]), lock_days=orders.LOCK_DAYS,
                           questions=questions.for_order(order_id), max_question=orders.MAX_QUESTION_LENGTH,
                           allergies_seen=kitchen_repo.allergies_seen(order_id), staff_view=True)


@bp.post("/orders/<order_id>/status")
@admin_only
def change_status(order_id: str):
    order, customer = _load(order_id)
    to_status = request.form.get("to", "")
    reason = request.form.get("reason", "").strip()
    error = orders.status_change_error(order, to_status, reason)
    if error:
        flash(t(error, max=orders.MAX_TEXT_LENGTH), "error")
    elif not orders_repo.change_status(order_id, order["status"], to_status, current_user.email, reason):
        flash(t("changed_meanwhile"), "error")
    else:
        if to_status in ("approved", "rejected"):
            _notify_customer(order, customer, to_status, reason)
        flash(t("status_changed", status=t("status_" + to_status)), "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


def _notify_customer(order: dict, customer: dict, to_status: str, reason: str) -> None:
    """E-mail the customer in their own language (US-22)."""
    lang = customer.get("language")
    event = order["event_type"].get(f"name_{lang}") or order["event_type"]["name_no"]
    body = t_in(lang, f"mail_{to_status}_body", name=customer["name"], id=order["id"], event=event,
                date=format_date(order["event_date"], lang), reason=reason,
                url=url_for("orders.detail", order_id=order["id"], _external=True))
    mail.send(customer["email"], t_in(lang, f"mail_{to_status}_subject", id=order["id"]), body)


@bp.post("/orders/<order_id>/payment")
@admin_only
def change_payment(order_id: str):
    order, _ = _load(order_id)
    to_status = request.form.get("to", "")
    if to_status not in orders.payment_actions(order):
        flash(t("change_not_allowed"), "error")
    elif not orders_repo.change_payment(order_id, order["payment_status"], to_status, current_user.email):
        flash(t("changed_meanwhile"), "error")
    else:
        flash(t("payment_changed", status=t("payment_" + to_status)), "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@bp.get("/questions")
@admin_only
def question_list():
    return render_template("admin_questions.html", rows=questions.unanswered())


@bp.post("/orders/<order_id>/questions/<question_id>/answer")
@admin_only
def answer(order_id: str, question_id: str):
    text = request.form.get("text", "").strip()
    error = orders.question_error(text)
    if error:
        flash(t(error, max=orders.MAX_QUESTION_LENGTH), "error")
    else:
        result = questions.answer(order_id, question_id, current_user.email, text)
        if result is None:
            flash(t("already_answered"), "error")
        else:
            _send_answer(result["order"], result["customer"], result["question"], text)
            flash(t("answer_sent"), "success")
    return redirect(url_for("admin.order_detail", order_id=order_id, _anchor="questions"))


def _send_answer(order: dict, customer: dict, question: str, text: str) -> None:
    """US-26: the answer goes to the customer by e-mail, in their language."""
    lang = customer.get("language")
    event = order["event_type"].get(f"name_{lang}") or order["event_type"]["name_no"]
    body = t_in(lang, "mail_answer_body", name=customer["name"], id=order["id"], event=event,
                date=format_date(order["event_date"], lang), question=question, answer=text,
                url=url_for("orders.detail", order_id=order["id"], _external=True))
    mail.send(customer["email"], t_in(lang, "mail_answer_subject", id=order["id"]), body)


@bp.get("/event-types")
@admin_only
def event_type_list():
    return render_template("admin_event_types.html", event_types=event_types.list_all(),
                           max_minimum=current_app.config["MAX_EVENT_MINIMUM"])


@bp.post("/event-types/<event_type_id>/minimum")
@admin_only
def set_minimum(event_type_id: str):
    upper = current_app.config["MAX_EVENT_MINIMUM"]
    try:
        value = int(request.form.get("min_guests", "").strip())
    except ValueError:
        value = 0
    if not 1 <= value <= upper:
        flash(t("minimum_out_of_range", max=upper), "error")
    elif event_types.set_minimum(event_type_id, value) is None:
        abort(404)
    else:
        flash(t("minimum_saved"), "success")
    return redirect(url_for("admin.event_type_list"))
