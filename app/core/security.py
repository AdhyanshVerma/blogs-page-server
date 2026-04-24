"""
Security dependencies for API key validation.
"""

from fastapi import HTTPException, Security, Header
from typing import Optional
from app.core.config import API_KEY


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """Verify the API key from the X-API-Key header."""
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: valid API key required"
        )
    return x_api_key
