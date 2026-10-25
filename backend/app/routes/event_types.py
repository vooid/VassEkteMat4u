from flask import Blueprint, abort, current_app, jsonify, request

from ..repositories import event_types

bp = Blueprint("event_types", __name__)


@bp.get("")
def list_event_types():
    return jsonify(event_types.list_all())


@bp.put("/<event_type_id>/minimum")
def update_minimum(event_type_id: str):
    """Admin: change an event type's minimum guests. Existing orders keep the minimum saved on them."""
    body = request.get_json(silent=True) or {}
    value = body.get("min_guests")
    upper = current_app.config["MAX_EVENT_MINIMUM"]
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= upper:
        return jsonify(error=f"min_guests must be a whole number from 1 to {upper}"), 400
    updated = event_types.set_minimum(event_type_id, value)
    if updated is None:
        abort(404)
    return jsonify(updated)
