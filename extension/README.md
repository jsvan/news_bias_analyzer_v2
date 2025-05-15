# Chrome Extension Component

The extension component provides article context by comparing with global sentiment patterns.

## Features
- Article content extraction
- Sentiment visualization
- Entity opinion comparison
- Topic clustering
- Article similarity analysis

## Key Files
### Extension
- `manifest.json` - Extension configuration
- `background.js` - Background service worker
- `content.js` - Page content extraction
- `popup.html/js` - Extension popup interface
- Visualization modules:
  - `sentiment_histogram.js`
  - `similarity_cluster.js`
  - `entity_tracking.js`
  - `topic_cluster.js`

### API
- `api/article_endpoints.py` - Article analysis endpoints
- `api/main.py` - Main API entry point