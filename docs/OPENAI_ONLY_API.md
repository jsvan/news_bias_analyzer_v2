# OpenAI-Only Analysis API

This document explains the implementation of the OpenAI-only version of the News Bias Analyzer API, which completely removes random entity detection and sentiment scoring.

## Overview

The OpenAI-only API (`api_openai_only.py`) is a modified version of the original API that:

1. Exclusively uses OpenAI for article analysis
2. Provides proper error handling when OpenAI API is not available
3. Eliminates all randomness in entity detection and sentiment scoring
4. Calculates composite scores based on actual entity sentiment values
5. Maintains the same API interface for seamless integration with the Chrome extension

## Key Changes

### 1. OpenAI Dependency

The API now explicitly requires OpenAI to function. If no API key is available, it will return a clear HTTP exception with status code 503.

```python
# Check if OpenAI API is available
if not USE_OPENAI:
    logger.error("OpenAI API is required for analysis but not available")
    raise HTTPException(
        status_code=503, 
        detail="Article analysis requires OpenAI API key. Please set the OPENAI_API_KEY environment variable."
    )
```

### 2. No Fallback to Random Data

The previous implementation would fall back to random entity detection and sentiment scoring if OpenAI analysis failed or wasn't available. This fallback behavior has been completely removed.

### 3. Calculation of Composite Scores

Instead of using random percentiles, the API now calculates composite scores based on the actual entity sentiment values returned by OpenAI:

```python
# Calculate composite score based on entities (instead of random)
if entities:
    # Extract scores
    power_scores = [entity.get("power_score", 0) for entity in entities if "power_score" in entity]
    moral_scores = [entity.get("moral_score", 0) for entity in entities if "moral_score" in entity]
    
    # Calculate average scores (if available)
    avg_power = sum(power_scores) / len(power_scores) if power_scores else 0
    avg_moral = sum(moral_scores) / len(moral_scores) if moral_scores else 0
    
    # Convert to a percentile-like value between 1-99
    norm_power = (avg_power + 5) / 10
    norm_moral = (avg_moral + 5) / 10
    
    # Convert to percentile (1-99)
    percentile = max(1, min(99, int((norm_power * 0.6 + norm_moral * 0.4) * 100)))
else:
    # If no entities, use a neutral score
    percentile = 50
```

### 4. Proper Error Handling

All errors during OpenAI analysis are now properly caught and returned as HTTP exceptions with appropriate status codes:

```python
except Exception as e:
    logger.error(f"OpenAI analysis failed with error: {e}")
    raise HTTPException(
        status_code=500,
        detail=f"Article analysis failed: {str(e)}"
    )
```

## Running the OpenAI-Only API

A dedicated script has been created to run the OpenAI-only version of the API:

```bash
# Set your OpenAI API key
export OPENAI_API_KEY=your_api_key_here

# Run the API server
./run_openai_api.sh
```

The API will be available at http://localhost:8008

## Testing

You can test the OpenAI integration using the included `test_openai_analyze.py` script:

```bash
# Set your OpenAI API key
export OPENAI_API_KEY=your_api_key_here

# Run the test
python test_openai_analyze.py --file test_article.txt
```

## Integration with Chrome Extension

The Chrome extension will continue to work with this API without any modifications, as the response format remains the same. The only difference is that all analysis results will now be based on OpenAI's analysis rather than random values.

## Limitations

1. The API now requires an OpenAI API key to function
2. Analysis will fail if the OpenAI API is unavailable or returns errors
3. Analysis will incur OpenAI API usage costs based on the length of articles analyzed