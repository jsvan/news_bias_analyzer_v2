# News Bias Analyzer - API Usage Examples

This document provides practical examples of how to interact with the News Bias Analyzer API using various programming languages and tools.

## Prerequisites

Before using these examples, you need:

1. A running instance of the News Bias Analyzer API
2. Valid API credentials (if using authenticated endpoints)
3. Basic familiarity with the language/tool you're using

## API Base URL

The examples use a placeholder base URL. Replace it with your actual API endpoint:

```
https://api.newsbiasanalyzer.com
```

For local development, use:

```
http://localhost:8000
```

## Authentication

Most endpoints require authentication using JWT Bearer tokens. To obtain a token:

### 1. Get an Authentication Token

**Request:**

```http
POST /auth/token
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 2. Use the Token in Subsequent Requests

Include the token in the Authorization header:

```http
GET /entities
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Examples by Programming Language

### cURL

#### Authenticate and Get Token

```bash
curl -X POST https://api.newsbiasanalyzer.com/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"your_username","password":"your_password"}'
```

#### Get Entities

```bash
curl -X GET https://api.newsbiasanalyzer.com/entities \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### Analyze an Article

```bash
curl -X POST https://api.newsbiasanalyzer.com/analyze/article \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "url": "https://example.com/article",
    "title": "Example Article Title",
    "text": "Article content with mentions of entities like United States and China.",
    "source": "Example News",
    "publish_date": "2023-06-22T10:30:00Z"
  }'
```

### Python

#### Setup

```python
import requests
import json

BASE_URL = "https://api.newsbiasanalyzer.com"
```

#### Authenticate and Get Token

```python
def get_auth_token(username, password):
    auth_url = f"{BASE_URL}/auth/token"
    payload = {
        "username": username,
        "password": password
    }
    
    response = requests.post(auth_url, json=payload)
    response.raise_for_status()
    
    return response.json()["access_token"]

# Usage
token = get_auth_token("your_username", "your_password")
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}
```

#### Get Entities

```python
def get_entities(entity_type=None, limit=100, offset=0):
    entities_url = f"{BASE_URL}/entities"
    params = {}
    
    if entity_type:
        params["entity_type"] = entity_type
    if limit:
        params["limit"] = limit
    if offset:
        params["offset"] = offset
    
    response = requests.get(entities_url, headers=headers, params=params)
    response.raise_for_status()
    
    return response.json()

# Usage
entities = get_entities(entity_type="country", limit=10)
print(f"Found {len(entities['items'])} entities")
for entity in entities["items"]:
    print(f"{entity['name']} ({entity['type']}): {entity['mention_count']} mentions")
```

#### Analyze an Article

```python
def analyze_article(url, title, text, source, publish_date=None):
    analyze_url = f"{BASE_URL}/analyze/article"
    payload = {
        "url": url,
        "title": title,
        "text": text,
        "source": source
    }
    
    if publish_date:
        payload["publish_date"] = publish_date
    
    response = requests.post(analyze_url, headers=headers, json=payload)
    response.raise_for_status()
    
    return response.json()

# Usage
article_text = "Article content with mentions of entities like United States and China."
analysis = analyze_article(
    url="https://example.com/article",
    title="Example Article Title",
    text=article_text,
    source="Example News",
    publish_date="2023-06-22T10:30:00Z"
)

print(f"Analyzed article with {len(analysis['entities'])} entities")
for entity in analysis["entities"]:
    print(f"{entity['name']} ({entity['entity_type']})")
    print(f"  Power Score: {entity['power_score']}")
    print(f"  Moral Score: {entity['moral_score']}")
```

### JavaScript

#### Setup

```javascript
// Using fetch API
const BASE_URL = "https://api.newsbiasanalyzer.com";
let token = null;
```

#### Authenticate and Get Token

```javascript
async function getAuthToken(username, password) {
  const authUrl = `${BASE_URL}/auth/token`;
  const payload = {
    username,
    password
  };
  
  const response = await fetch(authUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    throw new Error(`Authentication failed: ${response.statusText}`);
  }
  
  const data = await response.json();
  return data.access_token;
}

// Usage
async function initializeApi() {
  token = await getAuthToken("your_username", "your_password");
  console.log("Authentication successful");
}
```

#### Get Entities

```javascript
async function getEntities(entityType = null, limit = 100, offset = 0) {
  const entitiesUrl = new URL(`${BASE_URL}/entities`);
  
  if (entityType) entitiesUrl.searchParams.append("entity_type", entityType);
  if (limit) entitiesUrl.searchParams.append("limit", limit.toString());
  if (offset) entitiesUrl.searchParams.append("offset", offset.toString());
  
  const response = await fetch(entitiesUrl, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get entities: ${response.statusText}`);
  }
  
  return await response.json();
}

// Usage
async function displayEntities() {
  try {
    const entities = await getEntities("country", 10);
    console.log(`Found ${entities.items.length} entities`);
    
    entities.items.forEach(entity => {
      console.log(`${entity.name} (${entity.type}): ${entity.mention_count} mentions`);
    });
  } catch (error) {
    console.error("Error fetching entities:", error);
  }
}
```

#### Analyze an Article

```javascript
async function analyzeArticle(url, title, text, source, publishDate = null) {
  const analyzeUrl = `${BASE_URL}/analyze/article`;
  const payload = {
    url,
    title,
    text,
    source
  };
  
  if (publishDate) {
    payload.publish_date = publishDate;
  }
  
  const response = await fetch(analyzeUrl, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    throw new Error(`Failed to analyze article: ${response.statusText}`);
  }
  
  return await response.json();
}

// Usage
async function runAnalysis() {
  try {
    const articleText = "Article content with mentions of entities like United States and China.";
    const analysis = await analyzeArticle(
      "https://example.com/article",
      "Example Article Title",
      articleText,
      "Example News",
      "2023-06-22T10:30:00Z"
    );
    
    console.log(`Analyzed article with ${analysis.entities.length} entities`);
    
    analysis.entities.forEach(entity => {
      console.log(`${entity.name} (${entity.entity_type})`);
      console.log(`  Power Score: ${entity.power_score}`);
      console.log(`  Moral Score: ${entity.moral_score}`);
    });
  } catch (error) {
    console.error("Error analyzing article:", error);
  }
}
```

### R

#### Setup

```r
library(httr)
library(jsonlite)

BASE_URL <- "https://api.newsbiasanalyzer.com"
token <- NULL
```

#### Authenticate and Get Token

```r
get_auth_token <- function(username, password) {
  auth_url <- paste0(BASE_URL, "/auth/token")
  payload <- list(
    username = username,
    password = password
  )
  
  response <- POST(
    url = auth_url,
    body = toJSON(payload, auto_unbox = TRUE),
    content_type("application/json")
  )
  
  if (http_error(response)) {
    stop("Authentication failed: ", http_status(response)$message)
  }
  
  content <- content(response, as = "parsed")
  return(content$access_token)
}

# Usage
token <- get_auth_token("your_username", "your_password")
headers <- c(
  "Authorization" = paste("Bearer", token),
  "Content-Type" = "application/json"
)
```

#### Get Entities

```r
get_entities <- function(entity_type = NULL, limit = 100, offset = 0) {
  entities_url <- paste0(BASE_URL, "/entities")
  params <- list()
  
  if (!is.null(entity_type)) params$entity_type <- entity_type
  if (!is.null(limit)) params$limit <- limit
  if (!is.null(offset)) params$offset <- offset
  
  response <- GET(
    url = entities_url,
    add_headers(.headers = headers),
    query = params
  )
  
  if (http_error(response)) {
    stop("Failed to get entities: ", http_status(response)$message)
  }
  
  return(content(response, as = "parsed"))
}

# Usage
entities <- get_entities(entity_type = "country", limit = 10)
cat("Found", length(entities$items), "entities\n")

for (entity in entities$items) {
  cat(entity$name, "(", entity$type, "):", entity$mention_count, "mentions\n")
}
```

#### Analyze an Article

```r
analyze_article <- function(url, title, text, source, publish_date = NULL) {
  analyze_url <- paste0(BASE_URL, "/analyze/article")
  payload <- list(
    url = url,
    title = title,
    text = text,
    source = source
  )
  
  if (!is.null(publish_date)) {
    payload$publish_date <- publish_date
  }
  
  response <- POST(
    url = analyze_url,
    add_headers(.headers = headers),
    body = toJSON(payload, auto_unbox = TRUE),
    content_type("application/json")
  )
  
  if (http_error(response)) {
    stop("Failed to analyze article: ", http_status(response)$message)
  }
  
  return(content(response, as = "parsed"))
}

# Usage
article_text <- "Article content with mentions of entities like United States and China."
analysis <- analyze_article(
  url = "https://example.com/article",
  title = "Example Article Title",
  text = article_text,
  source = "Example News",
  publish_date = "2023-06-22T10:30:00Z"
)

cat("Analyzed article with", length(analysis$entities), "entities\n")

for (entity in analysis$entities) {
  cat(entity$name, "(", entity$entity_type, ")\n")
  cat("  Power Score:", entity$power_score, "\n")
  cat("  Moral Score:", entity$moral_score, "\n")
}
```

## Advanced Usage Examples

### Batch Processing Multiple Articles

#### Python

```python
def batch_analyze_articles(articles):
    """
    Batch analyze multiple articles
    
    Args:
        articles: List of article dictionaries, each containing
                 url, title, text, source, and optionally publish_date
                 
    Returns:
        List of analysis results in the same order
    """
    results = []
    
    for article in articles:
        try:
            analysis = analyze_article(
                url=article["url"],
                title=article["title"],
                text=article["text"],
                source=article["source"],
                publish_date=article.get("publish_date")
            )
            results.append(analysis)
        except Exception as e:
            print(f"Error analyzing article {article['url']}: {e}")
            results.append(None)
    
    return results

# Usage
articles = [
    {
        "url": "https://example.com/article1",
        "title": "First Example Article",
        "text": "Content about United States and China relations.",
        "source": "Example News"
    },
    {
        "url": "https://example.com/article2",
        "title": "Second Example Article",
        "text": "Content about European Union policies.",
        "source": "Example News",
        "publish_date": "2023-06-23T10:30:00Z"
    }
]

batch_results = batch_analyze_articles(articles)
```

### Tracking Entity Sentiment Over Time

#### Python

```python
def track_entity_sentiment(entity_id, days=30, source_id=None):
    """
    Track sentiment changes for an entity over time
    
    Args:
        entity_id: ID of the entity to track
        days: Number of days to look back
        source_id: Optional source to filter by
        
    Returns:
        Time series data for the entity's sentiment
    """
    sentiment_url = f"{BASE_URL}/entity/{entity_id}/sentiment"
    params = {"days": days}
    
    if source_id:
        params["source_id"] = source_id
    
    response = requests.get(sentiment_url, headers=headers, params=params)
    response.raise_for_status()
    
    return response.json()

# Usage
entity_id = 1  # United States
sentiment_data = track_entity_sentiment(entity_id, days=90)

# Process and visualize with matplotlib (example)
import matplotlib.pyplot as plt
from datetime import datetime

dates = []
power_scores = []
moral_scores = []

for item in sentiment_data["sentiment_data"]:
    dates.append(datetime.fromisoformat(item["date"]))
    power_scores.append(item["power_score"])
    moral_scores.append(item["moral_score"])

plt.figure(figsize=(12, 6))
plt.plot(dates, power_scores, label="Power Score", color="blue")
plt.plot(dates, moral_scores, label="Moral Score", color="red")
plt.title(f"Sentiment Trends for {sentiment_data['entity']['name']}")
plt.xlabel("Date")
plt.ylabel("Score")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
```

### Comparing Sources

#### Python

```python
def compare_sources(entity_id, source_ids, days=30):
    """
    Compare how different sources portray the same entity
    
    Args:
        entity_id: ID of the entity to analyze
        source_ids: List of source IDs to compare
        days: Number of days to look back
        
    Returns:
        Dictionary with source comparison data
    """
    comparison_data = {}
    
    for source_id in source_ids:
        sentiment_url = f"{BASE_URL}/entity/{entity_id}/sentiment"
        params = {
            "days": days,
            "source_id": source_id
        }
        
        response = requests.get(sentiment_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Get source name
        source_url = f"{BASE_URL}/source/{source_id}"
        source_response = requests.get(source_url, headers=headers)
        source_response.raise_for_status()
        source_data = source_response.json()
        source_name = source_data["name"]
        
        # Store averages
        comparison_data[source_name] = {
            "power_score": data["averages"]["power_score"],
            "moral_score": data["averages"]["moral_score"],
            "mention_count": sum(item["mention_count"] for item in data["sentiment_data"])
        }
    
    return comparison_data

# Usage
entity_id = 1  # United States
source_ids = [1, 2, 3]  # Example source IDs (CNN, Fox News, BBC)
comparison = compare_sources(entity_id, source_ids, days=90)

# Print results
for source, data in comparison.items():
    print(f"{source}:")
    print(f"  Power Score: {data['power_score']:.2f}")
    print(f"  Moral Score: {data['moral_score']:.2f}")
    print(f"  Mention Count: {data['mention_count']}")
```

## Error Handling

Always implement proper error handling when working with the API:

### Python Example

```python
def safe_api_call(func, *args, **kwargs):
    """Wrapper for safe API calls with error handling"""
    try:
        return func(*args, **kwargs)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("Authentication error. Token may have expired.")
            # Re-authenticate
            token = get_auth_token("your_username", "your_password")
            headers["Authorization"] = f"Bearer {token}"
            return func(*args, **kwargs)  # Retry
        elif e.response.status_code == 429:
            retry_after = int(e.response.headers.get("Retry-After", 60))
            print(f"Rate limit exceeded. Retrying after {retry_after} seconds")
            time.sleep(retry_after)
            return func(*args, **kwargs)  # Retry
        else:
            print(f"API error: {e.response.status_code} - {e.response.text}")
            return None
    except requests.exceptions.ConnectionError:
        print("Connection error. Check your internet connection and API endpoint.")
        return None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None
```

## Rate Limiting Considerations

The API implements rate limiting to prevent abuse. Here's how to handle it:

1. Check the rate limit headers in responses:
   - `X-RateLimit-Limit`: Total requests allowed within the window
   - `X-RateLimit-Remaining`: Requests remaining in current window
   - `X-RateLimit-Reset`: Time when the rate limit resets (Unix timestamp)

2. Implement exponential backoff:

```python
def api_call_with_backoff(func, *args, max_retries=5, **kwargs):
    """Make API call with exponential backoff for rate limiting"""
    retries = 0
    while retries < max_retries:
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                wait_time = retry_after * (2 ** retries)
                print(f"Rate limited. Waiting {wait_time} seconds before retry.")
                time.sleep(wait_time)
                retries += 1
            else:
                raise
        except Exception as e:
            raise
    
    raise Exception(f"Failed after {max_retries} retries due to rate limiting")
```

## Advanced Authentication

For production applications, consider using API keys rather than username/password authentication:

```python
def get_api_key_token(api_key):
    """Authenticate using API key"""
    auth_url = f"{BASE_URL}/auth/api-key"
    headers = {"X-API-Key": api_key}
    
    response = requests.post(auth_url, headers=headers)
    response.raise_for_status()
    
    return response.json()["access_token"]

# Usage
api_key = "your-api-key-from-dashboard"
token = get_api_key_token(api_key)
```

## Conclusion

These examples should help you get started with the News Bias Analyzer API. For more detailed information on available endpoints and parameters, refer to the [API Reference](API_REFERENCE.md).