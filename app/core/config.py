"""
Core configuration and dependencies for the FastAPI Blog Storage application.
"""

import os
from functools import wraps
from typing import Optional
from github import Github, GithubException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---------- Configuration ----------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # format: "owner/repo"
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-me")

if not GITHUB_TOKEN or not GITHUB_REPO or not API_KEY:
    raise RuntimeError("Missing required env vars: GITHUB_TOKEN, GITHUB_REPO, API_KEY")

# ---------- GitHub setup ----------
g: Optional[Github] = None
repo = None
BRANCH = "main"  # or "master"
INDEX_FILE = "blog_index.json"
CONTENT_PREFIX = "blog_"
CONTENT_SUFFIX = ".json"


def init_github():
    """Initialize GitHub connection lazily."""
    global g, repo
    if g is None:
        g = Github(GITHUB_TOKEN)
        try:
            repo = g.get_repo(GITHUB_REPO)
        except GithubException as e:
            raise RuntimeError(f"Cannot access repo {GITHUB_REPO}: {e.data.get('message', str(e))}")


def get_repo():
    """Get the repo object, ensuring GitHub is initialized first."""
    init_github()
    return repo
