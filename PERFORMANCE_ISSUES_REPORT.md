# News Bias Analyzer - Performance Issues Report

## Executive Summary

This report identifies code patterns that could cause high CPU/energy usage in the news_bias_analyzer project. The analysis focused on running services, API endpoints, and background workers.

## Critical Issues Found

### 1. Polling Without Proper Delays

#### scheduler/job_scheduler.py
- **Issue**: Main loop with 60-second sleep cycle continuously checking for work
- **Location**: Line 243 - `time.sleep(60)`
- **Impact**: Constant CPU wake-ups every minute, even when no work is pending
- **Recommendation**: Implement exponential backoff or event-driven scheduling

#### server/server_manager.py  
- **Issue**: Process monitoring loop with 1-second sleep
- **Location**: Line 303 - `time.sleep(1)`
- **Impact**: Very frequent CPU wake-ups (every second) to check subprocess status
- **Recommendation**: Use process.wait() with timeout or increase polling interval

#### analyzer/batch_analyzer.py
- **Issue**: Daemon mode polls every 5 minutes regardless of workload
- **Location**: Line 1068 - `time.sleep(POLL_INTERVAL_SECONDS)` where POLL_INTERVAL_SECONDS=300
- **Impact**: Regular CPU wake-ups even when no articles need processing
- **Recommendation**: Implement adaptive polling based on queue size

### 2. Database Query Inefficiencies

#### database/repositories.py
- **Issue**: Potential N+1 query pattern in find_with_entities_by_article_id
- **Location**: Lines 156-159 - Joins Entity and EntityMention tables
- **Impact**: Could result in excessive queries when processing multiple articles
- **Recommendation**: Use eager loading with joinedload() or selectinload()

#### server/extension_api.py
- **Issue**: Entity autocomplete performs multiple database queries for tiered search
- **Location**: Lines 136-170 - get_popular_entities function
- **Impact**: Cache refresh queries all entities with count aggregation
- **Recommendation**: Implement proper database indexing and consider materialized views

### 3. Synchronous Blocking Operations

#### scrapers/scrape_to_db.py
- **Issue**: Synchronous database operations in batch insertion
- **Location**: Lines 148-165 - Multiple synchronous queries per article
- **Impact**: Blocks event loop during database I/O
- **Recommendation**: Use async database operations or batch queries

#### scrapers/parallel_scraper.py
- **Issue**: Uses subprocess.run for synchronous scraping
- **Impact**: Blocks main thread during external process execution
- **Recommendation**: Use asyncio subprocess or thread pool

### 4. CPU-Intensive Operations

#### clustering/source_similarity.py
- **Issue**: Pairwise similarity computation using nested loops
- **Location**: Lines 133-135 - O(n²) algorithm for source comparisons
- **Impact**: Quadratic time complexity for large source sets
- **Recommendation**: Use vectorized operations or approximate algorithms

#### analyzer/hotelling_t2.py
- **Issue**: Matrix operations for statistical calculations
- **Impact**: Heavy CPU usage for large entity sets
- **Recommendation**: Consider caching computed statistics or using incremental updates

### 5. Resource Leaks

#### analyzer/batch_analyzer.py
- **Issue**: File handles not properly closed in error cases
- **Location**: Lines 214-224 - upload_batch_file function
- **Impact**: Potential file descriptor exhaustion
- **Recommendation**: Use context managers (with statements) consistently

### 6. Excessive Logging

#### Multiple files
- **Issue**: Synchronous file I/O for logging throughout the codebase
- **Impact**: Disk I/O blocking on every log statement
- **Recommendation**: Use async logging handlers or log aggregation service

#### scrapers/scrape_to_db.py
- **Issue**: Excessive print statements in insertion loop
- **Location**: Lines 97-126 - Multiple prints per article
- **Impact**: Console I/O overhead for large batches
- **Recommendation**: Use debug-level logging or batch progress reporting

### 7. Missing Connection Pooling

#### database/db.py
- **Issue**: Creates new database connections without proper pooling configuration
- **Impact**: Connection overhead for each request
- **Recommendation**: Configure SQLAlchemy connection pool with appropriate size limits

### 8. Inefficient Caching

#### server/extension_api.py
- **Issue**: In-memory caching without size limits
- **Location**: Lines 130-135 - Global cache dictionaries
- **Impact**: Unbounded memory growth
- **Recommendation**: Use LRU cache with size limits or Redis

## Recommendations Summary

1. **Immediate Actions**:
   - Increase polling intervals in server_manager.py and scheduler
   - Add database indexes for frequently queried columns
   - Implement connection pooling with appropriate limits
   - Replace synchronous subprocess calls with async alternatives

2. **Medium-term Improvements**:
   - Refactor similarity computations to use vectorized operations
   - Implement proper async/await patterns for I/O operations
   - Add caching layer with TTL and size limits
   - Use background job queue (Celery/RQ) instead of polling

3. **Long-term Optimizations**:
   - Consider time-series database for sentiment data
   - Implement event-driven architecture using message queue
   - Use approximate algorithms for similarity computations
   - Add monitoring and profiling instrumentation

## Energy Efficiency Tips

1. Use event-driven patterns instead of polling
2. Batch database operations to reduce connection overhead
3. Implement proper sleep/wake cycles for background workers
4. Use indexes and query optimization to reduce CPU usage
5. Consider serverless functions for infrequent tasks
6. Implement circuit breakers for external API calls

## Monitoring Recommendations

1. Add CPU and memory usage metrics
2. Track database query performance
3. Monitor background job queue depths
4. Set up alerts for resource exhaustion
5. Use APM tools for bottleneck identification