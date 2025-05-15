#!/usr/bin/env python3
"""
Compare the performance and reliability of wget vs. requests for article extraction.
This script tests both methods against a selection of major news sites and reports
which method works better for each site.

Usage:
    ./run.sh custom temp_scripts/compare_extraction.py
"""

import os
import sys
import time
import json
import asyncio
import tempfile
import subprocess
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
import aiohttp
import trafilatura
from bs4 import BeautifulSoup

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Test articles from major news sources - using current articles
TEST_ARTICLES = [
    # CNN
    "https://www.cnn.com/2025/05/14/politics/hunter-biden-trial-opening-arguments/index.html",
    "https://www.cnn.com/2025/05/14/business/coinbase-earnings-crypto/index.html",
    
    # BBC
    "https://www.bbc.com/news/world-middle-east-66059374",
    "https://www.bbc.com/news/business-66058764",
    
    # New York Times
    "https://www.nytimes.com/2025/05/14/us/politics/trump-xi-phone-call.html",
    "https://www.nytimes.com/2025/05/14/business/dealbook/james-murdoch-tiktok.html",
    
    # Fox News
    "https://www.foxnews.com/politics/biden-white-house-refuses-say-thinks-hunter-trial-politically-motivated",
    "https://www.foxnews.com/sports/tom-brady-roast-drew-lot-blood-tony-dungy-says",
    
    # Guardian
    "https://www.theguardian.com/world/2025/may/14/ukraine-war-update-what-we-know-on-day-811-of-russias-invasion",
    "https://www.theguardian.com/world/2025/may/14/israel-gaza-war-what-we-know-day-221",
    
    # Washington Post
    "https://www.washingtonpost.com/business/2025/05/14/walmart-earnings-inflation/",
    "https://www.washingtonpost.com/technology/2025/05/14/apple-ios-18-ai-wwdc/",
    
    # Al Jazeera
    "https://www.aljazeera.com/news/2025/5/14/un-chief-calls-for-end-to-gaza-war-as-israel-hamas-talks-continue",
    "https://www.aljazeera.com/economy/2025/5/14/us-cpi-data-shows-inflation-rose-in-april",
    
    # Reuters
    "https://www.reuters.com/world/middle-east/gaza-ceasefire-talks-resume-egypt-sources-say-2025-05-14/",
    "https://www.reuters.com/business/retail-consumer/walmart-beats-quarterly-results-estimates-2025-05-14/",
    
    # NPR
    "https://www.npr.org/2025/05/14/1235901257/hunter-biden-trial-tax-charges",
    "https://www.npr.org/2025/05/14/1235894872/inflation-cpi-consumer-prices-april"
]

# User agent to use for requests
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"

async def extract_with_wget(url):
    """Extract article content using wget and trafilatura."""
    start_time = time.time()
    result = {
        "url": url,
        "method": "wget",
        "success": False,
        "text_length": 0,
        "html_length": 0,
        "time_taken": 0,
        "error": None
    }
    
    try:
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.html')
        os.close(temp_fd)
        
        try:
            # Use wget to download the article
            wget_cmd = [
                'wget',
                '--timeout=30',
                '--tries=2',
                '--quiet',
                '--user-agent=' + USER_AGENT,
                '-O', temp_path,
                url
            ]
            
            # Run wget
            process = await asyncio.create_subprocess_exec(
                *wget_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
            
            if process.returncode != 0:
                result["error"] = f"wget failed: {stderr.decode()}"
                return result
            
            # Read the HTML file
            with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
            
            # Extract content with trafilatura
            extracted_text = trafilatura.extract(html_content, include_comments=False, favor_precision=True)
            extracted_html = trafilatura.extract(html_content, output_format='html', favor_precision=True)
            
            if not extracted_text:
                result["error"] = "No content extracted"
                return result
            
            # Success!
            result["success"] = True
            result["text_length"] = len(extracted_text)
            result["html_length"] = len(extracted_html)
            result["text"] = extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        result["error"] = str(e)
    
    # Record time taken
    result["time_taken"] = time.time() - start_time
    return result

async def extract_with_requests(url):
    """Extract article content using requests and trafilatura."""
    start_time = time.time()
    result = {
        "url": url,
        "method": "requests",
        "success": False,
        "text_length": 0,
        "html_length": 0,
        "time_taken": 0,
        "error": None
    }
    
    try:
        # Make request with timeout
        headers = {
            'User-Agent': USER_AGENT
        }
        
        # Run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            response_future = loop.run_in_executor(
                executor,
                lambda: requests.get(url, headers=headers, timeout=30)
            )
            response = await response_future
        
        if response.status_code != 200:
            result["error"] = f"HTTP error: {response.status_code}"
            return result
            
        html_content = response.text
        
        # Extract content with trafilatura
        extracted_text = trafilatura.extract(html_content, include_comments=False, favor_precision=True)
        extracted_html = trafilatura.extract(html_content, output_format='html', favor_precision=True)
        
        if not extracted_text:
            result["error"] = "No content extracted"
            return result
            
        # Success!
        result["success"] = True
        result["text_length"] = len(extracted_text)
        result["html_length"] = len(extracted_html)
        result["text"] = extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
        
    except Exception as e:
        result["error"] = str(e)
    
    # Record time taken
    result["time_taken"] = time.time() - start_time
    return result

async def extract_with_aiohttp(url):
    """Extract article content using aiohttp and trafilatura."""
    start_time = time.time()
    result = {
        "url": url,
        "method": "aiohttp",
        "success": False,
        "text_length": 0,
        "html_length": 0,
        "time_taken": 0,
        "error": None
    }
    
    try:
        # Make request with timeout
        headers = {
            'User-Agent': USER_AGENT
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    result["error"] = f"HTTP error: {response.status}"
                    return result
                
                html_content = await response.text()
        
        # Extract content with trafilatura
        extracted_text = trafilatura.extract(html_content, include_comments=False, favor_precision=True)
        extracted_html = trafilatura.extract(html_content, output_format='html', favor_precision=True)
        
        if not extracted_text:
            result["error"] = "No content extracted"
            return result
            
        # Success!
        result["success"] = True
        result["text_length"] = len(extracted_text)
        result["html_length"] = len(extracted_html)
        result["text"] = extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
        
    except Exception as e:
        result["error"] = str(e)
    
    # Record time taken
    result["time_taken"] = time.time() - start_time
    return result

async def test_url(url):
    """Test all extraction methods on a single URL."""
    print(f"\n\nTesting URL: {url}")
    
    # Get domain for reporting
    domain = urlparse(url).netloc
    
    # Run all extraction methods
    wget_result = await extract_with_wget(url)
    requests_result = await extract_with_requests(url)
    aiohttp_result = await extract_with_aiohttp(url)
    
    # Determine which method worked best
    methods = [wget_result, requests_result, aiohttp_result]
    working_methods = [m for m in methods if m["success"]]
    
    if not working_methods:
        print(f"❌ ALL METHODS FAILED for {domain}")
        print(f"  wget error: {wget_result['error']}")
        print(f"  requests error: {requests_result['error']}")
        print(f"  aiohttp error: {aiohttp_result['error']}")
        return {
            "url": url,
            "domain": domain,
            "best_method": None,
            "fastest_method": None,
            "success": False,
            "results": {
                "wget": wget_result,
                "requests": requests_result,
                "aiohttp": aiohttp_result
            }
        }
    
    # Sort working methods by text length (more is better)
    working_methods.sort(key=lambda x: x["text_length"], reverse=True)
    best_method = working_methods[0]["method"]
    
    # Find the fastest method among those that worked
    fastest = min(working_methods, key=lambda x: x["time_taken"])
    
    print(f"✅ Results for {domain}:")
    print(f"  wget: {'✅ Success' if wget_result['success'] else '❌ Failed'} - {wget_result['text_length']} chars in {wget_result['time_taken']:.2f}s")
    print(f"  requests: {'✅ Success' if requests_result['success'] else '❌ Failed'} - {requests_result['text_length']} chars in {requests_result['time_taken']:.2f}s")
    print(f"  aiohttp: {'✅ Success' if aiohttp_result['success'] else '❌ Failed'} - {aiohttp_result['text_length']} chars in {aiohttp_result['time_taken']:.2f}s")
    print(f"  Best method: {best_method} (most content)")
    print(f"  Fastest method: {fastest['method']} ({fastest['time_taken']:.2f}s)")
    
    return {
        "url": url,
        "domain": domain,
        "best_method": best_method,
        "fastest_method": fastest["method"],
        "success": True,
        "results": {
            "wget": wget_result,
            "requests": requests_result,
            "aiohttp": aiohttp_result
        }
    }

async def main():
    """Run the extraction comparison test."""
    print(f"\n{'=' * 80}")
    print(f"ARTICLE EXTRACTION METHOD COMPARISON")
    print(f"Testing {len(TEST_ARTICLES)} articles from major news sources")
    print(f"{'=' * 80}\n")
    
    start_time = time.time()
    
    # Process URLs concurrently
    tasks = [test_url(url) for url in TEST_ARTICLES]
    results = await asyncio.gather(*tasks)
    
    # Analyze results
    total_time = time.time() - start_time
    success_count = sum(1 for r in results if r["success"])
    
    # Count best methods
    best_methods = {}
    fastest_methods = {}
    
    for r in results:
        if r["best_method"]:
            best_methods[r["best_method"]] = best_methods.get(r["best_method"], 0) + 1
        if r["fastest_method"]:
            fastest_methods[r["fastest_method"]] = fastest_methods.get(r["fastest_method"], 0) + 1
    
    # Results by domain
    domain_results = {}
    for r in results:
        domain = r["domain"]
        if domain not in domain_results:
            domain_results[domain] = []
        domain_results[domain].append(r)
    
    # Print summary
    print(f"\n\n{'=' * 80}")
    print(f"RESULTS SUMMARY")
    print(f"{'=' * 80}")
    print(f"Tested {len(TEST_ARTICLES)} articles ({success_count} successful)")
    print(f"Total test time: {total_time:.2f} seconds")
    print(f"\nBest method (most content extracted):")
    for method, count in best_methods.items():
        print(f"  {method}: {count} articles ({count/len(results)*100:.1f}%)")
    
    print(f"\nFastest method:")
    for method, count in fastest_methods.items():
        print(f"  {method}: {count} articles ({count/len(results)*100:.1f}%)")
    
    print(f"\nResults by domain:")
    for domain, domain_results in domain_results.items():
        success = sum(1 for r in domain_results if r["success"])
        print(f"  {domain}: {success}/{len(domain_results)} successful")
        
        # Count best methods for this domain
        domain_best = {}
        for r in domain_results:
            if r["best_method"]:
                domain_best[r["best_method"]] = domain_best.get(r["best_method"], 0) + 1
        
        if domain_best:
            best = max(domain_best.items(), key=lambda x: x[1])[0]
            print(f"    Best method: {best}")
    
    # Save detailed results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"temp/extraction_comparison_{timestamp}.json"
    
    # Ensure directory exists
    os.makedirs("temp", exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": timestamp,
            "total_time": total_time,
            "success_rate": success_count / len(TEST_ARTICLES),
            "best_methods": best_methods,
            "fastest_methods": fastest_methods,
            "detailed_results": results
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")
    print(f"Run again with different URLs to compare more sources.")

def go():
    """Entry point for run.sh custom script execution."""
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())