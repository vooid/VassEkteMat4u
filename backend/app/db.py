"""Neo4j driver lifecycle: one driver per app, one session per query."""
import atexit

from flask import Flask, current_app
from neo4j import Driver, GraphDatabase


def init_app(app: Flask) -> None:
    if "NEO4J_DRIVER" not in app.config:  # tests inject a fake driver
        driver = GraphDatabase.driver(
            app.config["NEO4J_URI"],
            auth=(app.config["NEO4J_USER"], app.config["NEO4J_PASSWORD"]),
        )
        app.config["NEO4J_DRIVER"] = driver
        atexit.register(driver.close)


def get_driver() -> Driver:
    return current_app.config["NEO4J_DRIVER"]


def run(query: str, **params) -> list[dict]:
    """Run a Cypher query and return the records as dicts."""
    records, _, _ = get_driver().execute_query(
        query, params, database_=current_app.config["NEO4J_DATABASE"]
    )
    return [r.data() for r in records]
