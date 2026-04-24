# FastAPI Blog Storage API

A modular FastAPI-based blog storage system using GitHub as the backend.

## Features

- **CRUD Operations**: Create, Read, Update, and Delete blog posts
- **Modular Architecture**: Clean separation of concerns with routers, schemas, core, and models
- **GitHub Backend**: Stores blog content and index in a GitHub repository
- **API Key Authentication**: Protected routes require a valid API key
- **Rate Limiting**: Prevents abuse with configurable rate limits
- **CORS Support**: Ready for frontend integration

## Project Structure

```
/workspace
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create this)
└── app/
    ├── __init__.py
    ├── main.py            # FastAPI app factory
    ├── core/
    │   ├── __init__.py
    │   ├── config.py      # Configuration and GitHub setup
    │   ├── security.py    # API key authentication
    │   └── github_helpers.py  # GitHub I/O operations
    ├── models/
    │   └── __init__.py    # Database models (future expansion)
    ├── routers/
    │   ├── __init__.py
    │   └── blog.py        # Blog CRUD routes
    └── schemas/
        ├── __init__.py
        └── blog.py        # Pydantic models
```

## API Routes

| Method | Endpoint           | Description                          | Auth Required |
|--------|-------------------|--------------------------------------|---------------|
| GET    | `/`               | List all blog posts (metadata)       | No            |
| GET    | `/health`         | Health check endpoint                | No            |
| POST   | `/add`            | Create a new blog post               | Yes           |
| GET    | `/load/{blog_id}` | Get blog post by ID                  | No            |
| PUT    | `/update/{blog_id}`| Update/overwrite existing blog post | Yes           |
| DELETE | `/delete/{blog_id}`| Delete a blog post                  | Yes           |

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Create `.env` file** with your credentials:
   ```env
   GITHUB_TOKEN=your_github_personal_access_token
   GITHUB_REPO=owner/repo_name
   API_KEY=your_secret_api_key
   ```

3. **Run the server**:
   ```bash
   python main.py
   ```

   The API will be available at `http://localhost:8000`

4. **Access interactive docs**:
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

## Usage Examples

### Create a Blog Post

```bash
curl -X POST "http://localhost:8000/add" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{
    "title": "My First Blog",
    "content": "Hello, world!",
    "readtime": 5,
    "date": "2024-01-15",
    "author": "John Doe",
    "tags": ["intro", "hello"]
  }'
```

### Get All Blogs

```bash
curl "http://localhost:8000/"
```

### Get a Specific Blog

```bash
curl "http://localhost:8000/load/{blog_id}"
```

### Update a Blog Post

```bash
curl -X PUT "http://localhost:8000/update/{blog_id}" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{
    "title": "Updated Title",
    "content": "Updated content here"
  }'
```

### Delete a Blog Post

```bash
curl -X DELETE "http://localhost:8000/delete/{blog_id}" \
  -H "X-API-Key: your_api_key_here"
```

## Environment Variables

| Variable     | Required | Description                                      |
|-------------|----------|--------------------------------------------------|
| GITHUB_TOKEN | Yes      | GitHub Personal Access Token with repo access  |
| GITHUB_REPO  | Yes      | Repository in format `owner/repo_name`         |
| API_KEY      | Yes      | Secret key for authenticating write operations |
| SECRET_KEY   | No       | Application secret key (default: dev-key-change-me) |

## Notes

- Blog content is stored as individual JSON files (`blog_{id}.json`)
- Blog metadata is stored in `blog_index.json`
- All write operations (add, update, delete) require API key authentication
- Rate limiting is set to 5 requests per minute for write operations
