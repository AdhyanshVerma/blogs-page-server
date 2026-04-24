"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime


class BlogCreate(BaseModel):
    """Schema for creating a new blog post."""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=1_000_000)
    readtime: int = Field(..., gt=0)
    date: str = Field(...)  # YYYY-MM-DD format
    author: str = Field(..., min_length=1, max_length=100)
    tags: List[str] = Field(default_factory=list)

    @field_validator('date')
    @classmethod
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError('date must be in YYYY-MM-DD format')
        return v

    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, v):
        if not isinstance(v, list):
            raise ValueError('tags must be a list of strings')
        return [t.strip() for t in v if isinstance(t, str) and t.strip()]


class BlogUpdate(BaseModel):
    """Schema for updating an existing blog post (overwrites original)."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1, max_length=1_000_000)
    readtime: Optional[int] = Field(None, gt=0)
    date: Optional[str] = Field(None)  # YYYY-MM-DD format
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    tags: Optional[List[str]] = None

    @field_validator('date')
    @classmethod
    def validate_date(cls, v):
        if v is not None:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError('date must be in YYYY-MM-DD format')
        return v

    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, v):
        if v is not None:
            if not isinstance(v, list):
                raise ValueError('tags must be a list of strings')
            return [t.strip() for t in v if isinstance(t, str) and t.strip()]
        return v


class BlogResponse(BaseModel):
    """Schema for blog response."""
    id: str
    title: str
    content: str
    readtime: int
    date: str
    author: str
    tags: List[str]


class BlogMeta(BaseModel):
    """Schema for blog metadata (without content)."""
    id: str
    title: str
    readtime: int
    date: str
    author: str
    tags: List[str]


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    timestamp: str


class MessageResponse(BaseModel):
    """Schema for simple message responses."""
    message: str
    id: Optional[str] = None


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
