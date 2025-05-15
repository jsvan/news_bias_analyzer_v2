"""
OpenAI API integration for News Bias Analyzer.
Handles entity extraction and sentiment analysis with configurable prompts and models.
"""
import os
import time
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
import asyncio
import backoff

from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion
import tiktoken

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default system prompt for entity and sentiment extraction
DEFAULT_SYSTEM_PROMPT = """
You are an expert analyst specializing in media sentiment analysis. Your task is to extract named entities from news articles and analyze how they are portrayed along two dimensions:

1. POWER DIMENSION: How the entity is portrayed in terms of power, strength, or agency
   * 2: Extremely weak, vulnerable, helpless, or powerless
   * 0: Neutral portrayal of power
   * +2: Extremely powerful, strong, influential, or dominant

2. MORAL DIMENSION: How the entity is portrayed in terms of moral character. Ie, do we walk away liking this entity?
   * -2: Extremely evil, malevolent, corrupt, or immoral
   * 0: Morally neutral portrayal
   * +2: Extremely good, virtuous, ethical, or moral

For each entity, include 1-2 representative mentions from the text that support your analysis.

IMPORTANT GUIDELINES:
- Focus only on SIGNIFICANT entities (people, organizations, countries, political parties, etc.)
- Only include entities that have clear sentiment indicators in the text
- Base your analysis solely on how the entity is portrayed in THIS SPECIFIC article
- Be objective and avoid your own biases
- Provide precise, nuanced scores using decimal values when appropriate (e.g., +1.3, -1.5)
- Consider both explicit statements and implicit tone/context

FORMAT YOUR RESPONSE AS A JSON OBJECT with this exact structure:
{
  "entities": [
    {
      "entity": "Entity Name",
      "entity_type": "person|organization|country|political_party|company",
      "power_score": number,
      "moral_score": number,
      "mentions": [
        {"text": "exact quote from article", "context": "brief explanation of sentiment"}
      ]
    }
  ]
}
"""

class OpenAIProcessor:
    """
    Processor for OpenAI API integration, handling entity extraction and sentiment analysis.
    """
    
    def __init__(self, 
                 api_key: str = None, 
                 model: str = "gpt-4-turbo",
                 system_prompt: str = None,
                 max_tokens: int = 4000,
                 temperature: float = 0.1,
                 batch_size: int = 10,  # Increased from 5 to handle parallel processing better
                 max_retries: int = 3,
                 retry_delay: int = 2):
        """
        Initialize the OpenAI processor.
        
        Args:
            api_key: OpenAI API key (if None, use OPENAI_API_KEY env var)
            model: OpenAI model to use for analysis
            system_prompt: Custom system prompt (if None, use default)
            max_tokens: Maximum tokens to generate in response
            temperature: Sampling temperature (0.0-1.0)
            batch_size: Number of articles to process in parallel
            max_retries: Maximum number of retries for API calls
            retry_delay: Initial delay between retries (in seconds)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.model = model
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize OpenAI clients
        self.client = OpenAI(api_key=self.api_key)
        self.async_client = AsyncOpenAI(api_key=self.api_key)

        # Token counter with fallback for newer models
        try:
            self.tokenizer = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback for newer models not yet supported by tiktoken
            # Using cl100k_base which is used by most newer GPT models
            print(f"Model {model} not recognized by tiktoken, using cl100k_base encoding instead")
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

        # Stats
        self.total_tokens_used = 0
        self.total_api_calls = 0
        self.total_retries = 0
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in the given text."""
        return len(self.tokenizer.encode(text))
    
    def prepare_article_text(self, article: Dict[str, Any], max_tokens: int = 6000) -> str:
        """
        Prepare article text for analysis, truncating if necessary.
        
        Args:
            article: Article data with 'title' and 'text' fields
            max_tokens: Maximum tokens to include
            
        Returns:
            Formatted article text ready for analysis
        """
        title = article.get('title', '')
        text = article.get('text', '')
        url = article.get('url', '')
        source = article.get('source', '')
        
        # Create header with metadata
        header = f"ARTICLE TITLE: {title}\n"
        header += f"SOURCE: {source}\n"
        header += f"URL: {url}\n\n"
        header += "ARTICLE TEXT:\n"
        
        # Count tokens in header and leave room for response
        header_tokens = self.count_tokens(header)
        available_tokens = max_tokens - header_tokens - 1000  # Reserve 1000 tokens for response
        
        # Truncate text if needed
        if self.count_tokens(text) > available_tokens:
            # Truncate text to fit within available tokens
            encoded_text = self.tokenizer.encode(text)
            truncated_encoded = encoded_text[:available_tokens]
            text = self.tokenizer.decode(truncated_encoded)
            text += "\n\n[Text truncated due to length]"
        
        return header + text
    
    @backoff.on_exception(
        backoff.expo,
        (Exception),
        max_tries=3,
        giveup=lambda e: "maximum context length" in str(e).lower(),
        factor=2
    )
    def analyze_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single article for entities and sentiments.
        
        Args:
            article: Article data with title and text
            
        Returns:
            The original article data with added entity and sentiment analysis
        """
        try:
            # Prepare article text
            article_text = self.prepare_article_text(article)
            
            # Log token usage for monitoring
            input_tokens = self.count_tokens(self.system_prompt) + self.count_tokens(article_text)
            logger.debug(f"Input tokens for article '{article.get('title', '')[:30]}...': {input_tokens}")
            
            # Call OpenAI API
            logger.info(f"Analyzing article: {article.get('title', '')[:50]}...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": article_text}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Update stats
            self.total_tokens_used += response.usage.total_tokens
            self.total_api_calls += 1
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Add results to article data
            article['entities'] = result.get('entities', [])
            article['analysis_model'] = self.model
            article['processed_at'] = time.time()
            
            logger.info(f"Analyzed article with {len(article['entities'])} entities")
            return article
            
        except Exception as e:
            logger.error(f"Error analyzing article {article.get('id', '')}: {e}")
            
            # Add empty results and mark as error
            article['entities'] = []
            article['analysis_error'] = str(e)
            article['processed_at'] = time.time()
            
            # Re-raise certain errors for backoff
            if "maximum context length" in str(e).lower():
                raise e
                
            return article
    
    async def analyze_article_async(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single article for entities and sentiments asynchronously.
        
        Args:
            article: Article data with title and text
            
        Returns:
            The original article data with added entity and sentiment analysis
        """
        try:
            # Prepare article text
            article_text = self.prepare_article_text(article)
            
            # Call OpenAI API
            response = await self.async_client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": article_text}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Add results to article data
            article['entities'] = result.get('entities', [])
            article['analysis_model'] = self.model
            article['processed_at'] = time.time()
            
            logger.debug(f"Analyzed article: {article.get('title', '')[:30]}...")
            return article
            
        except Exception as e:
            logger.error(f"Error analyzing article {article.get('id', '')}: {e}")
            
            # Add empty results and mark as error
            article['entities'] = []
            article['analysis_error'] = str(e)
            article['processed_at'] = time.time()
            
            return article
    
    async def process_batch_async(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a batch of articles asynchronously.
        
        Args:
            articles: List of article data dictionaries
            
        Returns:
            List of processed articles with entity and sentiment data
        """
        tasks = []
        for article in articles:
            tasks.append(self.analyze_article_async(article))
        
        return await asyncio.gather(*tasks)
    
    def batch_process(self, articles: List[Dict[str, Any]], batch_size: int = None) -> List[Dict[str, Any]]:
        """
        Process articles in batches to manage API usage and rate limits.
        
        Args:
            articles: List of article data dictionaries
            batch_size: Number of articles to process in parallel (overrides instance setting)
            
        Returns:
            List of processed articles with entity and sentiment data
        """
        batch_size = batch_size or self.batch_size
        results = []
        
        # Process in batches
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(articles) + batch_size - 1)//batch_size}")
            
            # Process the batch
            batch_results = asyncio.run(self.process_batch_async(batch))
            results.extend(batch_results)
            
            # Add a small delay between batches to avoid rate limits
            if i + batch_size < len(articles):
                time.sleep(1)
        
        return results
    
    def analyze_text(self, text: str, custom_prompt: str = None) -> Dict[str, Any]:
        """
        Analyze arbitrary text with the sentiment analysis prompt.
        
        Args:
            text: Text to analyze
            custom_prompt: Optional custom system prompt to use
            
        Returns:
            Dictionary with entity and sentiment analysis
        """
        try:
            prompt = custom_prompt or self.system_prompt
            
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Update stats
            self.total_tokens_used += response.usage.total_tokens
            self.total_api_calls += 1
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing text: {e}")
            return {"entities": [], "error": str(e)}
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get statistics about API usage."""
        return {
            "total_tokens_used": self.total_tokens_used,
            "total_api_calls": self.total_api_calls,
            "total_retries": self.total_retries,
            "estimated_cost": f"${self.estimate_cost():.4f}"
        }
    
    def estimate_cost(self) -> float:
        """
        Estimate the cost of API calls made.
        Based on approximate pricing, should be updated as OpenAI prices change.
        """
        # These are approximate prices and should be updated
        if "gpt-4" in self.model:
            input_cost_per_token = 0.00001  # $0.01 per 1K tokens
            output_cost_per_token = 0.00003  # $0.03 per 1K tokens
        else:  # Assume GPT-3.5 Turbo
            input_cost_per_token = 0.0000015  # $0.0015 per 1K tokens
            output_cost_per_token = 0.000002  # $0.002 per 1K tokens
        
        # Assuming a 3:1 ratio of input to output tokens
        input_tokens = self.total_tokens_used * 0.75
        output_tokens = self.total_tokens_used * 0.25
        
        cost = (input_tokens * input_cost_per_token) + (output_tokens * output_cost_per_token)
        return cost


class SentimentAnalyzer:
    """High-level interface for sentiment analysis using OpenAI."""
    
    def __init__(self, api_key: str = None, model: str = "gpt-4-turbo"):
        """
        Initialize the sentiment analyzer.
        
        Args:
            api_key: OpenAI API key
            model: OpenAI model to use
        """
        self.processor = OpenAIProcessor(
            api_key=api_key,
            model=model
        )
    
    def analyze_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze an article for entities and sentiments.
        
        Args:
            article_data: Article data dictionary with title and text
            
        Returns:
            Article data with added entities and sentiments
        """
        return self.processor.analyze_article(article_data)
    
    def batch_process(self, articles: List[Dict[str, Any]], batch_size: int = 5) -> List[Dict[str, Any]]:
        """
        Process a batch of articles.
        
        Args:
            articles: List of article data dictionaries
            batch_size: Number of articles to process in parallel
            
        Returns:
            List of processed articles
        """
        return self.processor.batch_process(articles, batch_size)
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze arbitrary text for entities and sentiments.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with entities and sentiments
        """
        return self.processor.analyze_text(text)
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics."""
        return self.processor.get_usage_stats()


# Example usage
if __name__ == "__main__":
    # Example article for testing
    test_article = {
        "title": "Global Tensions Rise as Leaders Exchange Heated Rhetoric",
        "text": """
        GENEVA — Diplomatic relations between major powers deteriorated further yesterday as leaders exchanged increasingly hostile rhetoric at the International Summit.
        
        U.S. President Johnson accused Russian leader Vladimir Putin of "aggressive posturing" and "deliberately undermining international stability" through recent military exercises near NATO borders. "We will not stand idly by while democratic principles are threatened," Johnson declared, emphasizing America's commitment to defending its allies.
        
        Putin dismissed the accusations as "hypocritical theater" and claimed Western nations were using Russia as a "convenient scapegoat" for their own domestic problems. The Russian president pointed to the European Union's ongoing economic struggles, suggesting the bloc was "fracturing under its own contradictions."
        
        Chinese representatives attempted to position themselves as moderate voices, with Foreign Minister Li calling for "mutual respect and dialogue." However, critics noted China's recent naval expansion in the South China Sea contradicts their public stance of neutrality.
        
        The United Nations Secretary-General expressed deep concern over the "dangerous trajectory" of international relations, pleading for restraint and diplomatic solutions. "In our interconnected world, conflict benefits no one," she said in a statement that received only tepid applause from the assembled dignitaries.
        
        Meanwhile, smaller nations watched with growing anxiety as the confrontation between major powers intensified. "We are essentially hostages to their power games," said one African diplomat who requested anonymity.
        
        Military analysts warn that the combination of heated rhetoric, military exercises, and reduced diplomatic communications channels creates a high-risk environment for miscalculations.
        """,
        "source": "International Herald",
        "url": "https://example.com/global-tensions"
    }
    
    analyzer = SentimentAnalyzer()
    result = analyzer.analyze_article(test_article)
    
    print("\nAnalysis Results:")
    for entity in result['entities']:
        print(f"\n{entity['entity']} ({entity['entity_type']})")
        print(f"Power Score: {entity['power_score']}")
        print(f"Moral Score: {entity['moral_score']}")
        print("Mentions:")
        for mention in entity['mentions']:
            print(f"- \"{mention['text']}\" ({mention['context']})")
    
    print("\nAPI Usage Stats:")
    print(analyzer.get_usage_stats())