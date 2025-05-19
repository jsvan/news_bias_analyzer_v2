# Cultural Navigation Extension

This browser extension helps readers navigate the implicit moral frameworks embedded in news articles. It reveals how current news portrays entities as orientation points, positioning them relative to an implicit vision of societal progress or regression.

## Features
- Real-time analysis of news article moral positioning
- Power/Moral quadrant visualization revealing narrative archetypes (Hero, Villain, Victim, Threat) 
- Statistical comparison with typical portrayals across global news ecosystem
- Identification of entities serving as moral anchors within the article
- Historical tracking of how the same entities are positioned over time
- Visualization of the article's position within larger information environments

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