"""
WSGI entry point for Azure App Service deployment
Imports the Flask app from app.py and exposes it for Gunicorn
"""
from app import app

if __name__ == "__main__":
    app.run()
