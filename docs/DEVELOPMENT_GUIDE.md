# News Bias Analyzer - Development Guide

This guide is for developers who want to contribute to or extend the News Bias Analyzer project.

## Development Environment Setup

### 1. Install Development Tools

In addition to the standard requirements, developers should install:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# For linting and code quality
pip install flake8 black mypy isort

# For testing
pip install pytest pytest-cov
```

### 2. Configure Pre-commit Hooks

We use pre-commit hooks to ensure code quality:

```bash
pip install pre-commit
pre-commit install
```

### 3. Set Up a Development Database

For development, use Docker for the database:

```bash
# Start the database container
./run.sh docker up

# Initialize the database schema
./run.sh docker init

# The database is accessible at:
# postgresql://postgres:postgres@localhost:5432/news_bias
```

## Project Structure

The News Bias Analyzer follows a modular structure:

```
news_bias_analyzer/
├── scrapers/                 # News scraping modules
│   ├── base_scraper.py       # Base scraper class
│   ├── rss_scraper.py        # RSS feed scraper
│   ├── scheduler.py          # Scheduling system
│   └── news_sources.py       # Source configurations
│
├── processors/               # Text processing and OpenAI integration
│   ├── openai_integration.py # OpenAI API client
│   ├── article_processor.py  # Article processing pipeline
│   ├── prompts.py            # LLM prompts
│   └── config.py             # Configuration management
│
├── database/                 # Database layer
│   ├── models.py             # SQLAlchemy models
│   ├── db.py                 # Database manager
│   ├── migrations/           # Alembic migrations
│   └── seed.py               # Test data generation
│
├── analysis/                 # Statistical analysis
│   ├── statistical_models.py # Distribution and testing models
│   └── trend_analysis.py     # Trend detection
│
├── api/                      # API service
│   ├── main.py               # FastAPI application
│   ├── routes/               # API endpoints
│   ├── models.py             # Pydantic models
│   └── auth.py               # Authentication
│
├── frontend/                 # Frontend components
│   └── browser_extension/    # Chrome extension
│
├── tests/                    # Test suite
│
└── docs/                     # Documentation
```

## Coding Standards

### Python

- Follow PEP 8 style guide
- Use type hints (PEP 484)
- Keep functions small and focused
- Write comprehensive docstrings (Google style)

Example:

```python
def process_entity(entity: Dict[str, Any], score_threshold: float = 0.5) -> Optional[Dict[str, Any]]:
    """
    Process an entity and filter based on score threshold.
    
    Args:
        entity: Dictionary containing entity data
        score_threshold: Minimum score to include entity (default: 0.5)
        
    Returns:
        Processed entity or None if below threshold
    """
    # Implementation
```

### JavaScript (Browser Extension)

- Use ES6+ features
- Follow Airbnb JavaScript Style Guide
- Use TypeScript where possible

## Working with the Database

### Creating New Models

1. Add model class to `database/models.py`:

```python
class NewModel(Base):
    __tablename__ = 'new_models'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
```

2. Create a migration:

```bash
cd database/migrations
alembic revision --autogenerate -m "Add new model"
```

3. Apply the migration:

```bash
alembic upgrade head
```

### Database Query Best Practices

- Use SQLAlchemy ORM for most operations
- Optimize queries that will be frequently run
- Add indexes for fields used in filtering and sorting
- Use joined loading to avoid N+1 query problems
- Consider using async queries for API endpoints

Example:

```python
# Efficient query with joins and filtering
def get_entity_mentions(entity_id: int, source_id: Optional[int] = None):
    query = (
        session.query(EntityMention)
        .options(joinedload(EntityMention.article))
        .filter(EntityMention.entity_id == entity_id)
    )
    
    if source_id:
        query = query.join(NewsArticle).filter(NewsArticle.source_id == source_id)
    
    return query.order_by(EntityMention.created_at.desc()).limit(100).all()
```

## Working with OpenAI

### Prompt Development

When developing new prompts:

1. Start with a base template from `processors/prompts.py`
2. Test with a variety of articles to ensure consistent extraction
3. Analyze token usage to optimize length
4. Validate structured output format
5. Add the new prompt to `processors/prompts.py`

### Cost Management

- Monitor token usage with `get_usage_stats()`
- Set up alerts for unusually high usage
- Use tiered model selection based on task complexity
- Cache results when appropriate

## Adding a New Scraper

To add support for a new news source:

1. Add source configuration to `scrapers/news_sources.py`:

```python
{
    "name": "New News Site",
    "base_url": "https://newnewssite.com",
    "country": "Country",
    "language": "Language",
    "political_leaning": "center",
    "rss_feeds": [
        "https://newnewssite.com/rss/main.xml"
    ]
}
```

2. If the site requires custom handling, create a specialized scraper by extending `BaseScraper`.

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=news_bias_analyzer

# Run specific test module
pytest tests/test_processors/
```

### Writing Tests

- Write unit tests for all new functions
- Use mocks for external dependencies (especially OpenAI API)
- Test error cases and edge conditions
- For API endpoints, use FastAPI test client

Example test:

```python
def test_entity_extraction():
    # Setup test data
    test_article = {"title": "Test", "text": "Sample content mentioning the United States."}
    
    # Mock OpenAI response
    mock_response = {
        "entities": [
            {
                "entity": "United States",
                "entity_type": "country",
                "power_score": 3.0,
                "moral_score": 0.5,
                "mentions": [{"text": "United States", "context": "mentioned"}]
            }
        ]
    }
    
    with patch('processors.openai_integration.OpenAIProcessor.analyze_text', return_value=mock_response):
        processor = ArticleProcessor(use_database=False)
        result = processor.process_article(test_article)
        
        # Assertions
        assert len(result["entities"]) == 1
        assert result["entities"][0]["entity"] == "United States"
        assert result["entities"][0]["power_score"] == 3.0
```

## Continuous Integration

We use GitHub Actions for CI/CD. Workflows include:

- Linting and code quality checks
- Running tests with coverage reporting
- Building and testing Docker images

## Working with the Browser Extension

### Local Development

1. Load the extension in Chrome from `frontend/browser_extension`
2. Enable Chrome extension debugging
3. Make changes to the source files
4. Reload the extension to test changes

### Extension Structure

- `manifest.json`: Extension configuration
- `popup.html`, `popup.js`: Extension popup UI
- `content.js`: Content script that runs on pages
- `background.js`: Background service worker

## Deployment

### Local Development Deployment

For local development, you can run all services directly:

```bash
# Run API server
uvicorn api.main:app --reload

# Run scheduler (in separate terminal)
python -m scrapers.scheduler
```

### Production Deployment

For production, we use Docker:

```bash
# Build and start all services
docker-compose build
docker-compose up -d

# Check logs
docker-compose logs -f api
```

## Common Development Tasks

### Adding a New Dependency

1. Add to `requirements.txt` or `requirements-dev.txt`
2. Update Dockerfiles if needed
3. Document the dependency in relevant READMEs

### Database Migrations

```bash
# Create migration
cd database/migrations
alembic revision --autogenerate -m "Description"

# Apply migration through Docker helper
./run.sh docker init

# Or apply manually
cd database/migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Adding a New API Endpoint

1. Create a new route function in `api/routes/`
2. Add necessary Pydantic models in `api/models.py`
3. Register the route in `api/main.py`
4. Add tests for the new endpoint
5. Update API documentation

## Troubleshooting

### Common Development Issues

1. **Database migration conflicts**:
   - Check the migration sequence
   - Resolve merge conflicts in migration files
   - Consider recreating conflicting migrations

2. **OpenAI API errors**:
   - Check API key and model availability
   - Look for changes in the OpenAI API response format
   - Check for rate limiting or quota issues

3. **Browser extension not loading**:
   - Check Chrome extension errors in chrome://extensions
   - Verify manifest.json is valid
   - Check for JavaScript console errors

## Contributing Guidelines

1. **Creating a new feature**:
   - Create a feature branch: `git checkout -b feature/your-feature-name`
   - Implement and test your changes
   - Submit a pull request with a clear description

2. **Fixing a bug**:
   - Create a bug fix branch: `git checkout -b fix/bug-description`
   - Write a test case that demonstrates the bug
   - Fix the bug and ensure the test passes
   - Submit a pull request referencing the issue

3. **Code review**:
   - All code changes require review
   - Address review comments promptly
   - Ensure CI checks pass before merging

4. **Documentation**:
   - Update relevant documentation for all changes
   - Add comments for complex logic
   - Include examples for new features