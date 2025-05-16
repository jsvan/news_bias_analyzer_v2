// Content script for News Bias Analyzer extension
console.log('News Bias Analyzer content script loaded');

// Listen for messages from the popup or background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Content script received message:', request);
  
  if (request.action === 'getPageContent') {
    console.log('Extracting page content...');
    
    try {
      const content = extractPageContent();
      console.log('Content extraction successful:', {
        url: content.url,
        source: content.source,
        headline: content.headline,
        contentLength: content.content ? content.content.length : 0,
        publishDate: content.publishDate
      });
      
      sendResponse({ content: content });
    } catch (error) {
      console.error('Error extracting page content:', error);
      sendResponse({ 
        error: error.message,
        content: {
          url: window.location.href,
          source: 'Error extracting source',
          headline: document.title || 'Error extracting headline',
          content: 'Error extracting content: ' + error.message
        }
      });
    }
  }
  return true; // Keep the message channel open for async responses
});

// Extract content from the current page
function extractPageContent() {
  // Get the publication source
  const source = extractSource();
  
  // Get the headline
  const headline = extractHeadline();
  
  // Get the main content text
  const content = extractMainContent();
  
  // Get the publication date
  const publishDate = extractPublishDate();
  
  return {
    url: window.location.href,
    source: source,
    headline: headline,
    content: content,
    publishDate: publishDate
  };
}

// Extract the source/publication name
function extractSource() {
  // Check meta tags first
  const siteName = document.querySelector('meta[property="og:site_name"]');
  if (siteName && siteName.content) {
    return siteName.content;
  }
  
  // Try to get from schema.org publisher
  const publisher = document.querySelector('[itemprop="publisher"] [itemprop="name"]');
  if (publisher) {
    return publisher.textContent.trim();
  }
  
  // Try to get from the domain
  const domain = window.location.hostname;
  const domainParts = domain.split('.');
  if (domainParts.length >= 2) {
    // Convert domain to a readable format
    // e.g., nytimes.com -> New York Times, washingtonpost.com -> Washington Post
    if (domain.includes('nytimes')) {
      return 'New York Times';
    } else if (domain.includes('washingtonpost')) {
      return 'Washington Post';
    } else if (domain.includes('bbc')) {
      return 'BBC';
    } else if (domain.includes('cnn')) {
      return 'CNN';
    } else if (domain.includes('foxnews')) {
      return 'Fox News';
    } else if (domain.includes('theguardian')) {
      return 'The Guardian';
    } else if (domain.includes('reuters')) {
      return 'Reuters';
    } else if (domain.includes('aljazeera')) {
      return 'Al Jazeera';
    }
    
    // Default to domain without TLD
    return domainParts[domainParts.length - 2].charAt(0).toUpperCase() + 
           domainParts[domainParts.length - 2].slice(1);
  }
  
  return domain.replace(/^www\./, '');
}

// Extract the headline
function extractHeadline() {
  // Check for common headline elements
  const selectors = [
    'h1[class*="headline"]',
    'h1[class*="title"]',
    'h1.entry-title',
    'h1.article-title',
    'h1.post-title',
    'h1[itemprop="headline"]',
    'meta[property="og:title"]',
    '.headline',
    '.article-headline',
    '.story-headline',
    'h1:first-of-type'
  ];
  
  for (const selector of selectors) {
    const element = document.querySelector(selector);
    if (element) {
      // For meta tags
      if (element.tagName === 'META') {
        return element.content;
      }
      // For regular elements
      return element.textContent.trim();
    }
  }
  
  // Fallback to page title
  return document.title;
}

// Extract the main content
function extractMainContent() {
  // Check for common article content selectors
  const selectors = [
    'article',
    '[itemprop="articleBody"]',
    '.article-content',
    '.story-content',
    '.post-content',
    '.entry-content',
    '#content',
    '.content',
    'main'
  ];
  
  for (const selector of selectors) {
    const element = document.querySelector(selector);
    if (element) {
      // Remove unnecessary elements
      const clone = element.cloneNode(true);
      
      // Remove comments, ads, related articles sections
      const removeSelectors = [
        '.comments',
        '.comment-section',
        '.related-articles',
        '.advertisement', 
        '.ad',
        '.social-share',
        '.newsletter',
        'aside',
        'footer',
        'nav',
        'iframe',
        '[role="complementary"]',
        'script',
        'style'
      ];
      
      removeSelectors.forEach(selector => {
        const elements = clone.querySelectorAll(selector);
        elements.forEach(el => {
          if (el.parentNode) {
            el.parentNode.removeChild(el);
          }
        });
      });
      
      return clone.textContent.trim()
        .replace(/\s+/g, ' ') // Normalize whitespace
        .substring(0, 15000); // Limit length
    }
  }
  
  // Fallback to body text
  return document.body.textContent
    .trim()
    .replace(/\s+/g, ' ')
    .substring(0, 15000);
}

// Extract the publication date
function extractPublishDate() {
  // Check meta tags first
  const metaSelectors = [
    'meta[property="article:published_time"]',
    'meta[itemprop="datePublished"]',
    'meta[name="date"]',
    'meta[name="DC.date.issued"]'
  ];
  
  for (const selector of metaSelectors) {
    const element = document.querySelector(selector);
    if (element && element.content) {
      return element.content;
    }
  }
  
  // Check for common date elements
  const dateSelectors = [
    'time',
    '[itemprop="datePublished"]',
    '.date',
    '.published-date',
    '.article-date',
    '.post-date'
  ];
  
  for (const selector of dateSelectors) {
    const element = document.querySelector(selector);
    if (element) {
      if (element.hasAttribute('datetime')) {
        return element.getAttribute('datetime');
      }
      return element.textContent.trim();
    }
  }
  
  // Return empty if not found
  return '';
}