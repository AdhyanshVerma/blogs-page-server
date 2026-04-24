#!/bin/bash

# Base URL for the blog API
BASE_URL="https://blogs-page-server.onrender.com"

echo "=========================================="
echo "Testing Blog API at $BASE_URL"
echo "=========================================="
echo ""

# Test 1: List all blogs (Root endpoint)
echo "1. Testing GET / (List all blogs)"
echo "-------------------------------------------"
curl -s -X GET "$BASE_URL/" | head -c 500
echo ""
echo ""

# Test 2: Verbose output to see headers
echo "2. Testing GET / with verbose output"
echo "-------------------------------------------"
curl -s -v -X GET "$BASE_URL/" 2>&1 | head -c 800
echo ""
echo ""

# Test 3: Try to get a specific blog (replace 'sample-slug' if you know one)
echo "3. Testing GET /blog/{slug} (using 'welcome' as example slug)"
echo "-------------------------------------------"
curl -s -X GET "$BASE_URL/blog/welcome" | head -c 500
echo ""
echo ""

# Test 4: Create a new blog post
echo "4. Testing POST /blog (Create new post)"
echo "-------------------------------------------"
curl -s -X POST "$BASE_URL/blog" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Post from Script",
    "slug": "test-post-from-script",
    "content": "This is a test blog post created via script.sh",
    "tags": ["test", "script", "automated"]
  }' | head -c 500
echo ""
echo ""

# Test 5: Update the created blog post
echo "5. Testing PUT /blog/{slug} (Update post)"
echo "-------------------------------------------"
curl -s -X PUT "$BASE_URL/blog/test-post-from-script" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Updated Test Post",
    "content": "This content has been updated via script.sh",
    "tags": ["test", "updated", "script"]
  }' | head -c 500
echo ""
echo ""

# Test 6: Delete the created blog post
echo "6. Testing DELETE /blog/{slug} (Delete post)"
echo "-------------------------------------------"
curl -s -X DELETE "$BASE_URL/blog/test-post-from-script" | head -c 500
echo ""
echo ""

# Test 7: Verify deletion by trying to list blogs again
echo "7. Verifying deletion - GET / (List all blogs)"
echo "-------------------------------------------"
curl -s -X GET "$BASE_URL/" | head -c 500
echo ""
echo ""

echo "=========================================="
echo "All tests completed!"
echo "=========================================="
