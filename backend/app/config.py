import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
    # Upper bound for an event type's minimum guests (basic_desc.txt model prompt).
    MAX_EVENT_MINIMUM = 265
