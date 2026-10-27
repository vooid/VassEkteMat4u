"""The kitchen screen (US-27, US-28), the prep list (US-29) and the driver screen (US-30). Made for a tablet and a
phone: big text, few taps, one query per page. Admins can open them all."""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .. import orders
from ..auth import staff_required
from ..i18n import t, tr
from ..repositories import kitchen as kitchen_repo
from ..repositories import orders as orders_repo

kitchen_bp = Blueprint("kitchen", __name__, url_prefix="/kitchen")
driver_bp = Blueprint("driver", __name__, url_prefix="/driver")

PREP_DAYS = 3  # Mateo: "total kilos of each ingredient for the next three days"
# Approved orders are what the kitchen will cook; orders waiting for approval are only counted in a note.
PREP_STATUSES = ("approved", "in_preparation")


def _day():
    """?day=YYYY-MM-DD, today by default."""
    return orders.parse_date(request.args.get("day", "")) or orders.today()


def _day_links(day) -> dict:
    return {"day": day, "previous": day - timedelta(days=1), "next": day + timedelta(days=1),
            "is_today": day == orders.today()}


@kitchen_bp.get("", endpoint="index")
@staff_required("kitchen", "admin")
def kitchen_screen():
    day = _day()
    return render_template("kitchen.html", rows=kitchen_repo.kitchen_day(day), updated_at=datetime.now(timezone.utc),
                           **_day_links(day))


@kitchen_bp.get("/prep")
@staff_required("kitchen", "admin")
def prep():
    days = [orders.today() + timedelta(days=n) for n in range(PREP_DAYS)]
    prep_list = kitchen_repo.prep_list(days, PREP_STATUSES)
    prep_list["ingredients"].sort(key=lambda i: tr(i, "name").lower())
    return render_template("prep_list.html", days=days, prep_days=PREP_DAYS, updated_at=datetime.now(timezone.utc),
                           **prep_list)


@kitchen_bp.get("/sw.js")
def service_worker():
    """The kitchen tablet's service worker (US-29: today's orders still visible when the internet is down). Served
    from here, not /static, so it may control /kitchen. No login: the script holds no data."""
    response = current_app.send_static_file("kitchen-sw.js")
    response.headers["Service-Worker-Allowed"] = url_for("kitchen.index")
    response.headers["Cache-Control"] = "no-cache"
    return response


@kitchen_bp.post("/orders/<order_id>/allergies-seen")
@staff_required("kitchen", "admin")
def allergies_seen(order_id: str):
    if not kitchen_repo.confirm_allergies(order_id, current_user.email):
        abort(404)
    flash(t("allergies_confirmed", id=order_id), "success")
    return redirect(url_for("kitchen.index", day=request.form.get("day") or None, _anchor=f"order-{order_id}"))


@driver_bp.get("", endpoint="index")
@staff_required("driver", "admin")
def driver_screen():
    day = _day()
    return render_template("driver.html", rows=kitchen_repo.driver_day(day), **_day_links(day))


@driver_bp.post("/orders/<order_id>/delivered")
@staff_required("driver", "admin")
def delivered(order_id: str):
    # Only from "in preparation", like the admin's button; a second tap finds the status moved on.
    if orders_repo.change_status(order_id, "in_preparation", "delivered", current_user.email, None):
        flash(t("order_delivered", id=order_id), "success")
    else:
        flash(t("changed_meanwhile"), "error")
    return redirect(url_for("driver.index", day=request.form.get("day") or None))
