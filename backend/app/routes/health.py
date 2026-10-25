from flask import Blueprint, jsonify
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from ..db import get_driver

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    try:
        get_driver().verify_connectivity()
    except (ServiceUnavailable, Neo4jError, OSError) as exc:
        return jsonify(status="error", neo4j="unreachable", detail=str(exc)), 503
    return jsonify(status="ok", neo4j="connected")
