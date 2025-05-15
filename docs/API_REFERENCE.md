# News Bias Analyzer - API Reference

This document describes the API endpoints available in the News Bias Analyzer system, including request and response formats, authentication, and example usage.

## Base URL

All API endpoints are relative to the base URL:

```
http://localhost:8000
```

For production deployments, replace with your domain.

## Authentication

Most endpoints require authentication using a JWT bearer token:

```
Authorization: Bearer <your_token>
```

To obtain a token, use the `/auth/token` endpoint.

## Endpoints

### Authentication

#### `POST /auth/token`

Obtain an authentication token.

**Request:**
```json
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

### Entities

#### `GET /entities`

Get a list of entities.

**Query Parameters:**
- `entity_type` (optional): Filter by entity type
- `limit` (optional): Maximum number of entities to return (default: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "name": "United States",
      "type": "country",
      "mention_count": 1247
    },
    {
      "id": 2,
      "name": "Joe Biden",
      "type": "person",
      "mention_count": 835
    }
  ],
  "total": 1500,
  "limit": 100,
  "offset": 0
}
```

#### `GET /entity/{entity_id}`

Get details for a specific entity.

**Path Parameters:**
- `entity_id`: ID of the entity

**Response:**
```json
{
  "id": 1,
  "name": "United States",
  "type": "country",
  "mention_count": 1247,
  "first_seen": "2023-01-15T12:30:45Z",
  "last_seen": "2023-06-22T08:15:30Z",
  "avg_power_score": 3.7,
  "avg_moral_score": 0.2,
  "sources": [
    {
      "name": "CNN",
      "mention_count": 142
    },
    {
      "name": "Fox News",
      "mention_count": 156
    }
  ]
}
```

#### `GET /entity/{entity_id}/sentiment`

Get sentiment data for a specific entity.

**Path Parameters:**
- `entity_id`: ID of the entity

**Query Parameters:**
- `start_date` (optional): Start date for sentiment data (ISO format)
- `end_date` (optional): End date for sentiment data (ISO format)
- `source_id` (optional): Filter by source ID
- `country` (optional): Filter by country

**Response:**
```json
{
  "entity": {
    "id": 1,
    "name": "United States",
    "type": "country"
  },
  "sentiment_data": [
    {
      "date": "2023-06-01",
      "power_score": 3.5,
      "moral_score": 0.8,
      "mention_count": 25,
      "sources": ["CNN", "BBC", "Al Jazeera"]
    },
    {
      "date": "2023-06-02",
      "power_score": 3.7,
      "moral_score": 0.3,
      "mention_count": 18,
      "sources": ["Fox News", "Guardian", "Reuters"]
    }
  ],
  "averages": {
    "power_score": 3.6,
    "moral_score": 0.6
  },
  "distributions": {
    "power": {
      "mean": 3.6,
      "std": 0.8,
      "min": 1.2,
      "max": 4.8
    },
    "moral": {
      "mean": 0.6,
      "std": 1.2,
      "min": -2.5,
      "max": 3.2
    }
  }
}
```

### Analysis

#### `POST /analyze/article`

Analyze an article for entities and sentiment.

**Request:**
```json
{
  "title": "Article Title",
  "text": "Full article text content...",
  "source": "Publication Name",
  "url": "https://example.com/article",
  "publish_date": "2023-06-22T10:30:00Z"
}
```

**Response:**
```json
{
  "article_id": "f8c7b9a2e1d0",
  "entities": [
    {
      "entity": "United States",
      "entity_type": "country",
      "power_score": 4.2,
      "moral_score": 1.5,
      "mentions": [
        {
          "text": "The United States announced new sanctions",
          "context": "policy announcement"
        }
      ],
      "national_significance": 0.024,
      "global_significance": 0.032
    }
  ],
  "composite_score": {
    "percentile": 72.5,
    "p_value": 0.275
  },
  "processing_time": 2.4
}
```

#### `GET /stats/entity/{entity_id}/distribution`

Get the sentiment distribution data for an entity.

**Path Parameters:**
- `entity_id`: ID of the entity

**Query Parameters:**
- `country` (optional): Country for national distribution
- `source_id` (optional): Source for source-specific distribution
- `days` (optional): Number of days of data to include (default: 90)

**Response:**
```json
{
  "entity": {
    "id": 1,
    "name": "United States",
    "type": "country"
  },
  "distributions": {
    "global": {
      "power": {
        "mean": 3.7,
        "std": 0.9,
        "count": 1247,
        "pdf": {
          "x": [-2, -1.9, ..., 1.9, 2],
          "y": [0.001, 0.0012, ..., 0.0015, 0.001]
        }
      },
      "moral": {
        "mean": 0.2,
        "std": 1.5,
        "count": 1247,
        "pdf": {
          "x": [-2, -1.9, ..., 1.9, 2],
          "y": [0.003, 0.0035, ..., 0.004, 0.0038]
        }
      }
    },
    "national": {
      "country": "United States",
      "power": {
        "mean": 3.9,
        "std": 0.7,
        "count": 532,
        "pdf": {
          "x": [-2, -1.9, ..., 1.9, 2],
          "y": [0.001, 0.0012, ..., 0.0015, 0.001]
        }
      },
      "moral": {
        "mean": 1.2,
        "std": 1.3,
        "count": 532,
        "pdf": {
          "x": [-2, -1.9, ..., 1.9, 2],
          "y": [0.002, 0.0025, ..., 0.003, 0.0028]
        }
      }
    }
  }
}
```

#### `GET /trends`

Get sentiment trends over time.

**Query Parameters:**
- `entity_ids`: Comma-separated list of entity IDs
- `entity_types` (optional): Comma-separated list of entity types
- `days` (optional): Number of days to include (default: 30)
- `source_id` (optional): Filter by source ID
- `country` (optional): Filter by country

**Response:**
```json
{
  "trends": [
    {
      "id": 1,
      "name": "United States",
      "type": "country",
      "data": [
        {
          "date": "2023-06-01",
          "power_score": 1.5,
          "moral_score": 0.8,
          "mention_count": 25
        },
        {
          "date": "2023-06-02",
          "power_score": 1.7,
          "moral_score": 0.3,
          "mention_count": 18
        }
      ]
    },
    {
      "id": 2,
      "name": "China",
      "type": "country",
      "data": [
        {
          "date": "2023-06-01",
          "power_score": 1.2,
          "moral_score": -0.5,
          "mention_count": 18
        },
        {
          "date": "2023-06-02",
          "power_score": 1.4,
          "moral_score": -0.7,
          "mention_count": 15
        }
      ]
    }
  ]
}
```

### Sources

#### `GET /sources`

Get a list of news sources.

**Query Parameters:**
- `country` (optional): Filter by country
- `political_leaning` (optional): Filter by political leaning
- `limit` (optional): Maximum number of sources to return (default: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "name": "CNN",
      "base_url": "https://www.cnn.com",
      "country": "United States",
      "language": "English",
      "political_leaning": "center-left",
      "article_count": 5243
    },
    {
      "id": 2,
      "name": "Fox News",
      "base_url": "https://www.foxnews.com",
      "country": "United States",
      "language": "English",
      "political_leaning": "right",
      "article_count": 4876
    }
  ],
  "total": 45,
  "limit": 100,
  "offset": 0
}
```

#### `GET /source/{source_id}/bias`

Get bias profile for a news source.

**Path Parameters:**
- `source_id`: ID of the source

**Query Parameters:**
- `days` (optional): Number of days to include (default: 90)

**Response:**
```json
{
  "source": {
    "id": 1,
    "name": "CNN",
    "country": "United States",
    "political_leaning": "center-left"
  },
  "bias_profile": {
    "partisan_bias": {
      "detected": true,
      "direction": "left-leaning",
      "confidence": 0.85,
      "evidence": [
        "Democratic politicians receive power_score avg +0.7 higher than Republican politicians",
        "Republican politicians receive moral_score avg -1.2 lower than Democratic politicians"
      ]
    },
    "national_bias": {
      "detected": true,
      "favored": ["United States", "United Kingdom", "European Union"],
      "disfavored": ["Russia", "China", "Iran"],
      "confidence": 0.78,
      "evidence": [
        "US allies receive moral_score avg +1.8 higher than non-allies",
        "Significant difference in power portrayal between Western and non-Western countries"
      ]
    }
  },
  "entity_sentiment": {
    "countries": [
      {
        "entity": "United States",
        "power_score": 3.8,
        "moral_score": 1.7,
        "global_percentile": 87
      },
      {
        "entity": "Russia",
        "power_score": 3.2,
        "moral_score": -2.1,
        "global_percentile": 12
      }
    ],
    "people": [
      {
        "entity": "Joe Biden",
        "power_score": 2.8,
        "moral_score": 1.5,
        "global_percentile": 75
      },
      {
        "entity": "Vladimir Putin",
        "power_score": 3.6,
        "moral_score": -3.2,
        "global_percentile": 5
      }
    ]
  }
}
```

### Browser Extension API

#### `POST /extension/analyze`

Analyze an article for the browser extension.

**Request:**
```json
{
  "url": "https://example.com/article",
  "title": "Article Title",
  "text": "Full article text content...",
  "source": "Publication Name"
}
```

**Response:**
```json
{
  "entities": [
    {
      "name": "United States",
      "type": "country",
      "power_score": 4.2,
      "moral_score": 1.5,
      "national_significance": 0.024,
      "global_significance": 0.032,
      "mentions": [
        {
          "text": "The United States announced new sanctions",
          "context": "policy announcement"
        }
      ]
    }
  ],
  "composite_score": {
    "percentile": 72.5,
    "p_value": 0.275
  },
  "source_info": {
    "name": "CNN",
    "country": "United States",
    "political_leaning": "center-left"
  }
}
```

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request

```json
{
  "detail": "Invalid request. Please check your parameters."
}
```

### 401 Unauthorized

```json
{
  "detail": "Invalid authentication credentials"
}
```

### 403 Forbidden

```json
{
  "detail": "You do not have permission to perform this action"
}
```

### 404 Not Found

```json
{
  "detail": "The requested resource was not found"
}
```

### 429 Too Many Requests

```json
{
  "detail": "Rate limit exceeded. Please try again later.",
  "retry_after": 60
}
```

### 500 Internal Server Error

```json
{
  "detail": "An internal server error occurred"
}
```

## Rate Limiting

API requests are rate-limited to prevent abuse:

- Authenticated users: 100 requests per minute
- Anonymous users: 10 requests per minute

Rate limit information is included in response headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1624352400
```

## Pagination

Endpoints that return lists support pagination using `limit` and `offset` parameters:

```
GET /entities?limit=10&offset=20
```

Pagination information is included in the response:

```json
{
  "items": [...],
  "total": 1500,
  "limit": 10,
  "offset": 20
}
```

## Filtering

Many endpoints support filtering using query parameters. Multiple filters can be combined:

```
GET /entities?entity_type=country&limit=5
```

## Versioning

The API version is specified in the URL:

```
/api/v1/entities
```

The current version is v1.