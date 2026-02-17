"""
Vercel serverless adapter for the Phantasm FastAPI backend.
"""
import sys
from pathlib import Path

# Add the backend app directory to the Python path
backend_dir = Path(__file__).resolve().parent.parent / "phantasm" / "backend"
sys.path.insert(0, str(backend_dir))

from app.main import app  # noqa: E402
