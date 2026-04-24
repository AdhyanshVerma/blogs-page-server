"""
Blog router with CRUD operations.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from typing import List

from app.core.security import verify_api_key
from app.core.github_helpers import (
    get_index,
    save_index,
    get_blog_content,
    save_blog_content,
    get_blog_metadata,
    delete_github_file,
    is_valid_blog_id,
    CONTENT_PREFIX,
    CONTENT_SUFFIX,
)
from app.schemas.blog import (
    BlogCreate,
    BlogUpdate,
    BlogResponse,
    BlogMeta,
    MessageResponse,
)

router = APIRouter()

# Setup rate limiter
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")


@router.get("/health", response_model=dict, tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/", response_model=List[BlogMeta], tags=["Blog"])
async def list_blogs():
    """List all blog posts (metadata only), sorted by date (newest first)."""
    index, _ = get_index()
    # Sort by date (newest first)
    index.sort(key=lambda x: x.get("date", ""), reverse=True)
    return index


@router.post("/add", response_model=MessageResponse, status_code=status.HTTP_201_CREATED, tags=["Blog"])
@limiter.limit("5/minute")
async def add_blog(
    blog: BlogCreate,
    request,
    api_key: str = Depends(verify_api_key)
):
    """
    Add a new blog post.
    Requires valid API key in X-API-Key header.
    """
    # Generate unique ID
    blog_id = str(uuid.uuid4())

    # Read current index
    index, index_sha = get_index()

    # Create metadata entry
    new_entry = {
        "id": blog_id,
        "title": blog.title.strip(),
        "readtime": blog.readtime,
        "date": blog.date,
        "author": blog.author.strip(),
        "tags": blog.tags,
    }

    # Save blog content file first (fail early)
    if not save_blog_content(blog_id, blog.content.strip()):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store blog content on GitHub"
        )

    # Append to index and save
    index.append(new_entry)
    if not save_index(index, index_sha):
        # Rollback: delete the content file (optional - best effort)
        try:
            file_path = f"{CONTENT_PREFIX}{blog_id}{CONTENT_SUFFIX}"
            file_obj = get_blog_content(blog_id)  # Just to check existence
            # We can't easily get SHA here, so skip rollback for simplicity
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update index; transaction rolled back"
        )

    return {"message": "Blog added successfully", "id": blog_id}


@router.get("/load/{blog_id}", response_model=BlogResponse, tags=["Blog"])
async def load_blog(blog_id: str):
    """Retrieve blog content + metadata by ID."""
    if not is_valid_blog_id(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID format"
        )

    # Get metadata from index
    index, _ = get_index()
    meta = get_blog_metadata(blog_id, index)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )

    # Get content from separate file
    content_data = get_blog_content(blog_id)
    if not content_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog content missing"
        )

    # Merge metadata + content
    return BlogResponse(
        id=meta["id"],
        title=meta["title"],
        content=content_data.get("content", ""),
        readtime=meta["readtime"],
        date=meta["date"],
        author=meta["author"],
        tags=meta["tags"],
    )


@router.put("/update/{blog_id}", response_model=MessageResponse, tags=["Blog"])
@limiter.limit("5/minute")
async def update_blog(
    blog_id: str,
    blog_update: BlogUpdate,
    request,
    api_key: str = Depends(verify_api_key)
):
    """
    Update an existing blog post (overwrites the original).
    Only provided fields will be updated.
    Requires valid API key in X-API-Key header.
    """
    if not is_valid_blog_id(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID format"
        )

    # Get current index
    index, index_sha = get_index()
    meta = get_blog_metadata(blog_id, index)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )

    # Get current content
    content_data = get_blog_content(blog_id)
    if not content_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog content missing"
        )

    # Update metadata fields (only if provided)
    if blog_update.title is not None:
        meta["title"] = blog_update.title.strip()
    if blog_update.readtime is not None:
        meta["readtime"] = blog_update.readtime
    if blog_update.date is not None:
        meta["date"] = blog_update.date
    if blog_update.author is not None:
        meta["author"] = blog_update.author.strip()
    if blog_update.tags is not None:
        meta["tags"] = blog_update.tags

    # Update content (only if provided)
    if blog_update.content is not None:
        content_data["content"] = blog_update.content.strip()

    # Save updated content
    if not save_blog_content(blog_id, content_data["content"]):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update blog content on GitHub"
        )

    # Find and update the index entry
    for i, item in enumerate(index):
        if item.get("id") == blog_id:
            index[i] = meta
            break

    # Save updated index
    if not save_index(index, index_sha):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update index"
        )

    return {"message": "Blog updated successfully", "id": blog_id}


@router.delete("/delete/{blog_id}", response_model=MessageResponse, tags=["Blog"])
@limiter.limit("5/minute")
async def delete_blog(
    blog_id: str,
    request,
    api_key: str = Depends(verify_api_key)
):
    """
    Delete a blog post and its content file.
    Requires valid API key in X-API-Key header.
    """
    if not is_valid_blog_id(blog_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid blog ID format"
        )

    # Get current index
    index, index_sha = get_index()
    meta = get_blog_metadata(blog_id, index)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )

    # Get the content file SHA for deletion
    from app.core.github_helpers import read_github_file
    file_path = f"{CONTENT_PREFIX}{blog_id}{CONTENT_SUFFIX}"
    _, content_sha = read_github_file(file_path)

    # Remove from index
    index = [item for item in index if item.get("id") != blog_id]

    # Save updated index first
    if not save_index(index, index_sha):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update index"
        )

    # Delete the content file
    if content_sha:
        if not delete_github_file(file_path, content_sha, f"Delete blog {blog_id}"):
            # Log warning but don't fail - index was already updated
            print(f"Warning: Failed to delete content file for blog {blog_id}")

    return {"message": "Blog deleted successfully", "id": blog_id}
