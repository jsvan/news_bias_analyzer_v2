#!/usr/bin/env python
"""
A debugging script to test URL filtering in the scraper.
"""
import os
import sys
import logging
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def analyze_url(url):
    """
    Analyze URL and determine if it should be filtered out.
    Return reasons if it should be filtered, or None if it's valid.
    """
    reasons = []
    
    # Check if URL has enough path segments
    if url.count('/') < 3:
        reasons.append(f"Insufficient path segments (found: {url.count('/')})")
    
    # Check if URL ends with slash
    if url.rstrip().endswith('/'):
        reasons.append("Ends with slash (likely category/section page)")
    
    # Skip common non-article patterns
    non_article_patterns = [
        '/tag/', '/tags/', '/category/', '/categories/', 
        '/author/', '/authors/', '/about/', '/contact/',
        '/search/', '/page/', '/subscribe/', '/subscription/',
        '/feed/', '/rss/', '/videos/', '/audio/', '/podcasts/'
    ]
    
    parsed_url = urlparse(url)
    path = parsed_url.path
    
    for pattern in non_article_patterns:
        if pattern in path:
            reasons.append(f"Contains non-article pattern: {pattern}")
    
    # Check domain
    domain = parsed_url.netloc
    if not domain or domain == '':
        reasons.append("Missing domain")
    
    # Path validation
    if not path or path == '/' or path == '':
        reasons.append("Missing or root path only")
    
    return reasons if reasons else None

def test_urls():
    """Test a variety of URLs to see if they're filtered properly."""
    test_cases = [
        # Good URLs
        "https://www.cnn.com/2023/04/18/politics/abortion-supreme-court-mifepristone-restrictions-filing/index.html",
        "https://www.foxnews.com/world/state-department-approves-sale-1-4b-worth-helicopters-f-16-parts-uae-ahead-trumps-visit",
        "https://www.nytimes.com/2025/05/14/us/politics/trump-qatar-air-force-one.html",
        "https://www.npr.org/2025/05/14/nx-s1-5165561/voting-rights-act-north-dakota-section-1983-private-right",
        
        # Bad URLs - should be filtered
        "https://www.cnn.com/",
        "https://www.foxnews.com/category/politics",
        "https://www.nytimes.com/section/politics/",
        "https://www.npr.org/podcasts/",
        "https://www.washingtonpost.com/search/",
        "https://www.bbc.com/author/john-smith",
        "https://www.example.com/feed/rss",
        "http://rss.cnn.com/rss/cnn_topstories.rss",
        "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
    ]
    
    print("\n" + "=" * 80)
    print("TESTING URL FILTERING")
    print("=" * 80)
    
    for i, url in enumerate(test_cases):
        print(f"\nURL {i+1}: {url}")
        reasons = analyze_url(url)
        
        if reasons:
            print(f"✘ FILTERED - Reasons:")
            for j, reason in enumerate(reasons):
                print(f"  {j+1}. {reason}")
        else:
            print(f"✓ VALID - Would be processed")

if __name__ == "__main__":
    test_urls()