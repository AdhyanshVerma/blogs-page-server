"""
Helper functions for GitHub I/O operations.
"""

import json
import re
from typing import Optional, Tuple, List, Dict, Any
from app.core.config import repo, BRANCH, INDEX_FILE, CONTENT_PREFIX, CONTENT_SUFFIX


# Allowed ID pattern (prevents path traversal)
ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def is_valid_blog_id(blog_id: str) -> bool:
    """Check if blog ID matches the allowed pattern."""
    return bool(ID_PATTERN.match(blog_id))


def read_github_file(path: str) -> Tuple[Optional[str], Optional[str]]:
    """Return content (decoded) and SHA of a file from the repo."""
    try:
        file_obj = repo.get_contents(path, ref=BRANCH)
        content = file_obj.decoded_content.decode("utf-8")
        return content, file_obj.sha
    except Exception as e:
        if hasattr(e, 'status') and e.status == 404:
            return None, None
        raise


def write_github_file(path: str, content: str, commit_msg: str, sha: Optional[str] = None) -> bool:
    """Create or update a file on GitHub. Returns True on success."""
    try:
        if sha:
            repo.update_file(path, commit_msg, content, sha, branch=BRANCH)
        else:
            repo.create_file(path, commit_msg, content, branch=BRANCH)
        return True
    except Exception as e:
        error_msg = getattr(e, 'data', {}).get('message', str(e)) if hasattr(e, 'data') else str(e)
        print(f"GitHub write error: {error_msg}")
        return False


def delete_github_file(path: str, sha: str, commit_msg: str) -> bool:
    """Delete a file from GitHub. Returns True on success."""
    try:
        repo.delete_file(path, commit_msg, sha, branch=BRANCH)
        return True
    except Exception as e:
        error_msg = getattr(e, 'data', {}).get('message', str(e)) if hasattr(e, 'data') else str(e)
        print(f"GitHub delete error: {error_msg}")
        return False


def get_index() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Return the current blog index (list of dicts) and the SHA of the index file."""
    content, sha = read_github_file(INDEX_FILE)
    if content is None:
        return [], None
    try:
        return json.loads(content), sha
    except json.JSONDecodeError:
        return [], sha  # corrupted -> reset


def save_index(index_data: List[Dict[str, Any]], old_sha: Optional[str]) -> bool:
    """Save the updated index back to GitHub."""
    new_content = json.dumps(index_data, indent=2, sort_keys=True)
    return write_github_file(INDEX_FILE, new_content, "Update blog index", sha=old_sha)


def get_blog_content(blog_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the content JSON for a given blog ID."""
    file_path = f"{CONTENT_PREFIX}{blog_id}{CONTENT_SUFFIX}"
    content, _ = read_github_file(file_path)
    if content is None:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def save_blog_content(blog_id: str, content_text: str, sha: Optional[str] = None) -> bool:
    """Save the blog content as a separate JSON file."""
    file_path = f"{CONTENT_PREFIX}{blog_id}{CONTENT_SUFFIX}"
    data = {"id": blog_id, "content": content_text}
    new_content = json.dumps(data, indent=2)
    return write_github_file(file_path, new_content, f"Add content for blog {blog_id}", sha=sha)


def get_blog_metadata(blog_id: str, index: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Get blog metadata from index by ID."""
    for item in index:
        if item.get("id") == blog_id:
            return item
    return None
