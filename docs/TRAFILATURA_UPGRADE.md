# Trafilatura Upgrade Documentation

## Overview

This document details the upgrade from newspaper3k to trafilatura for HTML cleaning and text extraction in the News Bias Analyzer project. This change was implemented to improve the accuracy and reliability of the article content extraction process.

## Motivation

Previous implementation used newspaper3k for article parsing and content extraction, which sometimes failed to properly extract content from certain news sites. Based on research and benchmarks, trafilatura consistently outperforms newspaper3k and other HTML cleaning libraries in text extraction accuracy.

## Changes Made

### 1. Dependencies
- Added trafilatura (v2.0.0) to requirements.txt
- Kept newspaper3k for backward compatibility

### 2. Updated Files
- `scrapers/base_scraper.py`: Replaced newspaper's Article class with trafilatura for content extraction
- `scrapers/rss_scraper.py`: Updated the RSS scraper to use trafilatura for article parsing

### 3. Key Improvements
- **Better Content Extraction**: Trafilatura uses more sophisticated methods to identify and extract main content
- **Metadata Extraction**: Improved extraction of metadata (title, publish date, authors, etc.)
- **Fallback Mechanisms**: Added multiple fallback methods if the primary extraction fails:
  - Primary: trafilatura.extract()
  - Fallback 1: trafilatura.baseline()
  - Fallback 2: trafilatura.html2txt() with custom HTML cleaning

### 4. Testing
A test script has been created at `scrapers/test_trafilatura.py` to verify the functionality of the upgrade with various news sources.

## Using Trafilatura in the Project

### Basic Usage

The core functionality is encapsulated in the `parse_article` method of the `NewsScraper` class:

```python
def parse_article(self, url: str) -> Dict[str, Any]:
    """Parse an article using trafilatura."""
    try:
        # Download the page
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise ValueError(f"Failed to download content from {url}")
        
        # Extract main content with metadata
        metadata = trafilatura.metadata.extract_metadata(downloaded)
        content = trafilatura.extract(downloaded, include_comments=False, 
                                    include_tables=True, favor_precision=True)
        html_content = trafilatura.extract(downloaded, include_comments=False, 
                                         include_tables=True, output_format="html")
        
        # ... additional processing and fallbacks ...
        
        return {
            'id': article_id,
            'source': self.source_name,
            'url': url,
            'title': metadata.get('title', ''),
            'text': content,
            'html': html_content,
            # ... additional fields ...
        }
    except Exception as e:
        print(f"Error parsing article {url}: {e}")
        return {}
```

### Configuration Options

Trafilatura offers several configuration options that can be adjusted:

- **include_comments**: Set to `False` to exclude user comments
- **include_tables**: Set to `True` to preserve table content
- **favor_precision**: Set to `True` for more selective extraction
- **favor_recall**: Can be set to `True` for more opportunistic extraction

## Performance Expectations

Based on benchmarks, trafilatura should provide:

1. More accurate extraction of the main article content
2. Better handling of complex page layouts and dynamically loaded content
3. More reliable metadata extraction (publishing dates, authors, etc.)
4. Improved handling of non-English and non-Latin character websites

## Rollback Plan

If issues are encountered with trafilatura, the code can be reverted to use newspaper3k by:

1. Reverting the changes to `base_scraper.py` and `rss_scraper.py`
2. Removing trafilatura from requirements.txt

## Future Considerations

- Consider completely removing newspaper3k dependency in the future once trafilatura has been thoroughly tested
- Explore additional trafilatura options like language detection, signal filtering, and XML output for structured data
- Investigate performance improvements for high-volume scraping jobs

## References

- [Trafilatura Documentation](https://trafilatura.readthedocs.io/)
- [Trafilatura GitHub Repository](https://github.com/adbar/trafilatura)
- [Trafilatura vs. Other Libraries Benchmark](https://trafilatura.readthedocs.io/en/latest/evaluation.html)