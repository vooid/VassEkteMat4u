import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Signs the session cookie (language, later login). Set a long random value in .env outside development.
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-not-secret")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set SESSION_COOKIE_SECURE=1 in .env when the site runs on HTTPS (production).
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE") == "1"
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
    # Upper bound for an event type's minimum guests (basic_desc.txt model prompt).
    MAX_EVENT_MINIMUM = 265
