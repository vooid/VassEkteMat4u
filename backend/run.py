"""Dev server: python run.py (from the backend folder).

Default port is 5001 because macOS AirPlay Receiver occupies 5000.
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "5001")), debug=os.getenv("FLASK_DEBUG") == "1")
