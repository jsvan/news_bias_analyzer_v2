# Content Extraction API

## Overview

The News Bias Analyzer now includes a dedicated content extraction API endpoint that uses the Trafilatura library for superior web content extraction. This endpoint provides a way to cleanly extract the main content from web pages, removing navigation elements, ads, sidebars, and other irrelevant content.

## Benefits

- **Cleaner Content Extraction**: Trafilatura consistently outperforms other content extraction libraries in benchmark tests.
- **Better Metadata**: Extracts a rich set of metadata including title, author, publication date, etc.
- **Table Preservation**: Preserves table structures in the extracted content when available.
- **Fallback Mechanisms**: Includes multiple fallback strategies if the primary extraction fails.

## API Endpoint

### Extract Content

```
POST /extract
```

Extracts the main content from a URL using Trafilatura.

#### Request

```json
{
  "url": "https://example.com/article"
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| url | string | The URL of the webpage to extract content from |

#### Response

```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "source": "Example News",
  "authors": ["Author Name"],
  "publish_date": "2023-07-21T15:30:00Z",
  "language": "en",
  "text": "The extracted article text...",
  "html": "<div>The extracted article with HTML formatting...</div>",
  "extraction_method": "trafilatura"
}
```

| Field | Type | Description |
|-------|------|-------------|
| url | string | The original URL |
| title | string | The extracted article title |
| source | string | The extracted source name |
| authors | array | List of extracted author names |
| publish_date | string | The extracted publication date |
| language | string | The detected language code |
| text | string | The extracted plain text content |
| html | string | The extracted content with basic HTML formatting preserved |
| extraction_method | string | The method used for extraction (always "trafilatura") |

## Usage Examples

### cURL

```bash
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

### Python

```python
import requests

response = requests.post(
    "http://localhost:8000/extract",
    json={"url": "https://example.com/article"}
)

if response.status_code == 200:
    data = response.json()
    print(f"Title: {data['title']}")
    print(f"Content length: {len(data['text'])} characters")
    print(f"Text preview: {data['text'][:200]}...")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### JavaScript (Browser)

```javascript
fetch('http://localhost:8000/extract', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    url: 'https://example.com/article'
  })
})
.then(response => response.json())
.then(data => {
  console.log('Title:', data.title);
  console.log('Content length:', data.text.length);
  console.log('Text preview:', data.text.substring(0, 200) + '...');
})
.catch(error => {
  console.error('Error:', error);
});
```

## Browser Extension Integration

The browser extension has been updated to use this endpoint for content extraction. The extension now follows this strategy:

1. First attempt to use the `/extract` endpoint to get the cleanest possible content.
2. If the extraction API fails or is unavailable, fall back to the extension's built-in content extraction.

This approach ensures the best possible content quality while maintaining robustness if the API is not available.

## Error Handling

The API returns appropriate HTTP status codes:

- **400 Bad Request**: If the URL could not be downloaded or is invalid
- **500 Internal Server Error**: If content extraction failed for any other reason

Error responses include a detail message explaining what went wrong.

## Performance Considerations

- The extraction process requires downloading the target URL's content, which may take time for large pages.
- Consider implementing caching for frequently accessed URLs to improve performance.
- If the API is under heavy load, the browser extension will automatically fall back to its built-in extraction.