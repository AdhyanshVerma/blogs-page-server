"""
Blog storage on GitHub
Routes: /, /health, /add, /load/<id>
"""

import os
import re
import uuid
import json
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, render_template_string
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from github import Github, GithubException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---------- Configuration ----------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")          # format: "owner/repo"
API_KEY = os.getenv("API_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-key-change-me")

if not GITHUB_TOKEN or not GITHUB_REPO or not API_KEY:
    raise RuntimeError("Missing required env vars: GITHUB_TOKEN, GITHUB_REPO, API_KEY")

# ---------- GitHub setup ----------
g = Github(GITHUB_TOKEN)
try:
    repo = g.get_repo(GITHUB_REPO)
except GithubException as e:
    raise RuntimeError(f"Cannot access repo {GITHUB_REPO}: {e.data.get('message', str(e))}")

BRANCH = "main"   # or "master"
INDEX_FILE = "blog_index.json"
CONTENT_PREFIX = "blog_"
CONTENT_SUFFIX = ".json"

# Allowed ID pattern (prevents path traversal)
ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

# ---------- Flask & Rate Limiting ----------
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["20000 per day", "200 per hour"],
    storage_uri="memory://"
)

# ---------- Helpers for GitHub I/O ----------
def read_github_file(path):
    """Return content (decoded) and SHA of a file from the repo."""
    try:
        file_obj = repo.get_contents(path, ref=BRANCH)
        content = file_obj.decoded_content.decode("utf-8")
        return content, file_obj.sha
    except GithubException as e:
        if e.status == 404:
            return None, None
        raise

def write_github_file(path, content, commit_msg, sha=None):
    """Create or update a file on GitHub. Returns True on success."""
    try:
        if sha:
            repo.update_file(path, commit_msg, content, sha, branch=BRANCH)
        else:
            repo.create_file(path, commit_msg, content, branch=BRANCH)
        return True
    except GithubException as e:
        app.logger.error(f"GitHub write error: {e.data.get('message', str(e))}")
        return False

def get_index():
    """Return the current blog index (list of dicts) and the SHA of the index file."""
    content, sha = read_github_file(INDEX_FILE)
    if content is None:
        return [], None
    try:
        return json.loads(content), sha
    except json.JSONDecodeError:
        return [], sha   # corrupted -> reset

def save_index(index_data, old_sha):
    """Save the updated index back to GitHub."""
    new_content = json.dumps(index_data, indent=2, sort_keys=True)
    return write_github_file(INDEX_FILE, new_content, "Update blog index", sha=old_sha)

def get_blog_content(blog_id):
    """Retrieve the content JSON for a given blog ID."""
    file_path = f"{CONTENT_PREFIX}{blog_id}{CONTENT_SUFFIX}"
    content, _ = read_github_file(file_path)
    if content is None:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None

def save_blog_content(blog_id, content_text):
    """Save the blog content as a separate JSON file."""
    file_path = f"{CONTENT_PREFIX}{blog_id}{CONTENT_SUFFIX}"
    data = {"id": blog_id, "content": content_text}
    new_content = json.dumps(data, indent=2)
    return write_github_file(file_path, new_content, f"Add content for blog {blog_id}")

# ---------- Security: API key decorator ----------
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        provided_key = request.headers.get("X-API-Key")
        if not provided_key or provided_key != API_KEY:
            return jsonify({"error": "Unauthorized: valid API key required"}), 401
        return f(*args, **kwargs)
    return decorated

# ---------- Routes ----------
@app.route("/health")
def health():
    """Simple health check."""
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

@app.route("/")
def home():
    """Display all blog posts and a simple form to add new ones."""
    index, _ = get_index()
    # Sort by date (newest first)
    index.sort(key=lambda x: x.get("date", ""), reverse=True)
    return render_template_string(HTML_TEMPLATE, posts=index)

@app.route("/add", methods=["POST"])
@limiter.limit("5 per minute")
@require_api_key
def add_blog():
    """
    Add a new blog post.
    Expects JSON payload with:
        title, content, readtime (int), date (YYYY-MM-DD), author, tags (list of strings)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request must be JSON"}), 400

    # Validate required fields
    required = ["title", "content", "readtime", "date", "author", "tags"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    # Type validation
    try:
        readtime = int(data["readtime"])
        if readtime <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "readtime must be a positive integer"}), 400

    # Date validation (ISO YYYY-MM-DD)
    try:
        datetime.strptime(data["date"], "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "date must be in YYYY-MM-DD format"}), 400

    title = data["title"].strip()
    if not title or len(title) > 200:
        return jsonify({"error": "title must be 1-200 characters"}), 400

    content = data["content"].strip()
    if not content or len(content) > 1_000_000:  # 1 MB limit
        return jsonify({"error": "content size must be 1-1,000,000 characters"}), 400

    author = data["author"].strip()
    if not author or len(author) > 100:
        return jsonify({"error": "author must be 1-100 characters"}), 400

    tags = data["tags"]
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        return jsonify({"error": "tags must be a list of strings"}), 400
    tags = [t.strip() for t in tags if t.strip()]

    # Generate unique ID
    blog_id = str(uuid.uuid4())

    # Read current index
    index, index_sha = get_index()

    # Create metadata entry
    new_entry = {
        "id": blog_id,
        "title": title,
        "readtime": readtime,
        "date": data["date"],
        "author": author,
        "tags": tags,
    }

    # Save blog content file first (fail early)
    if not save_blog_content(blog_id, content):
        return jsonify({"error": "Failed to store blog content on GitHub"}), 500

    # Append to index and save
    index.append(new_entry)
    if not save_index(index, index_sha):
        # Rollback: delete the content file (optional - best effort)
        try:
            file_path = f"{CONTENT_PREFIX}{blog_id}{CONTENT_SUFFIX}"
            file_obj = repo.get_contents(file_path, ref=BRANCH)
            repo.delete_file(file_path, "Rollback due to index failure", file_obj.sha, branch=BRANCH)
        except Exception:
            pass
        return jsonify({"error": "Failed to update index; transaction rolled back"}), 500

    return jsonify({"id": blog_id, "message": "Blog added successfully"}), 201

@app.route("/load/<string:blog_id>")
def load_blog(blog_id):
    """Retrieve blog content + metadata by ID."""
    if not ID_PATTERN.match(blog_id):
        return jsonify({"error": "Invalid blog ID format"}), 400

    # Get metadata from index
    index, _ = get_index()
    meta = next((item for item in index if item["id"] == blog_id), None)
    if not meta:
        return jsonify({"error": "Blog not found"}), 404

    # Get content from separate file
    content_data = get_blog_content(blog_id)
    if not content_data:
        return jsonify({"error": "Blog content missing"}), 404

    # Merge metadata + content
    response = {**meta, "content": content_data.get("content", "")}
    return jsonify(response)

# ---------- HTML Template for "/" ----------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>GitHub Blog Storage</title>
    <style>
        body { font-family: sans-serif; margin: 2em; }
        .post { border-left: 4px solid #0366d6; padding-left: 1em; margin-bottom: 1.5em; }
        .tags { font-size: 0.8em; color: #586069; }
        form { margin-top: 2em; border-top: 1px solid #ccc; padding-top: 1em; }
        input, textarea, button { margin: 0.3em 0; padding: 0.5em; width: 100%; max-width: 500px; }
        button { background: #28a745; color: white; border: none; cursor: pointer; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>Blog Posts</h1>
    {% if posts %}
        {% for post in posts %}
        <div class="post">
            <h3><a href="/load/{{ post.id }}" target="_blank">{{ post.title }}</a></h3>
            <p>by {{ post.author }} · {{ post.date }} · {{ post.readtime }} min read</p>
            <div class="tags">Tags: {{ post.tags | join(', ') }}</div>
        </div>
        {% endfor %}
    {% else %}
        <p>No posts yet.</p>
    {% endif %}

    <h2>Add New Post</h2>
    <form id="addForm">
        <input type="text" id="title" placeholder="Title" required><br>
        <textarea id="content" placeholder="Content (markdown / text)" rows="5" required></textarea><br>
        <input type="number" id="readtime" placeholder="Read time (minutes)" required><br>
        <input type="date" id="date" required><br>
        <input type="text" id="author" placeholder="Author" required><br>
        <input type="text" id="tags" placeholder="Tags (comma separated)"><br>
        <input type="password" id="apiKey" placeholder="API Key" required><br>
        <button type="submit">Publish</button>
    </form>
    <div id="message"></div>

    <script>
        document.getElementById('addForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const tagsField = document.getElementById('tags').value;
            const tags = tagsField ? tagsField.split(',').map(t => t.trim()).filter(t => t) : [];
            const payload = {
                title: document.getElementById('title').value,
                content: document.getElementById('content').value,
                readtime: parseInt(document.getElementById('readtime').value, 10),
                date: document.getElementById('date').value,
                author: document.getElementById('author').value,
                tags: tags
            };
            const apiKey = document.getElementById('apiKey').value;
            const res = await fetch('/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': apiKey
                },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            const msgDiv = document.getElementById('message');
            if (res.ok) {
                msgDiv.innerHTML = `<span style="color:green">Success! ID: ${data.id}</span>`;
                setTimeout(() => location.reload(), 1500);
            } else {
                msgDiv.innerHTML = `<span class="error">Error: ${data.error || 'Unknown'}</span>`;
            }
        });
    </script>
</body>
</html>
"""

# ---------- Run the server ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
