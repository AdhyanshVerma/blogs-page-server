"""
Main entry point for the FastAPI Blog Storage application.
Routes: /, /health, /add, /load/<id>, /update/<id>, /delete/<id>
"""

import uvicorn

from app.main import app

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
