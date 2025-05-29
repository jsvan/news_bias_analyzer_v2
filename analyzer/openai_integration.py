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

# Try to import optional dependencies, but don't fail if they're not available
try:
    import backoff
    has_backoff = True
except ImportError:
    has_backoff = False

try:
    import tiktoken
    has_tiktoken = True
except ImportError:
    has_tiktoken = False

from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the prompt from the prompts module instead of duplicating it here
from analyzer.prompts import ENTITY_SENTIMENT_PROMPT

# Default system prompt for entity and sentiment extraction
DEFAULT_SYSTEM_PROMPT = ENTITY_SENTIMENT_PROMPT

class OpenAIProcessor:
    """
    Processor for OpenAI API integration, handling entity extraction and sentiment analysis.
    """
    
    def __init__(self, 
                 api_key: str = None, 
                 model: str = "gpt-4.1-nano",
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
        if has_tiktoken:
            try:
                self.tokenizer = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback for newer models not yet supported by tiktoken
                # Using cl100k_base which is used by most newer GPT models
                print(f"Model {model} not recognized by tiktoken, using cl100k_base encoding instead")
                self.tokenizer = tiktoken.get_encoding("cl100k_base")
        else:
            # If tiktoken is not available, use a simple tokenizer based on spaces and punctuation
            self.tokenizer = None
            print("tiktoken not available, using simple token count estimation")

        # Stats
        self.total_tokens_used = 0
        self.total_api_calls = 0
        self.total_retries = 0
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in the given text."""
        if has_tiktoken and self.tokenizer:
            # Use tiktoken if available
            return len(self.tokenizer.encode(text))
        else:
            # Simple approximation: about 4 chars per token for English
            return len(text) // 4
    
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
    
    def analyze_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single article for entities and sentiments.
        
        Args:
            article: Article data with title and text
            
        Returns:
            The original article data with added entity and sentiment analysis
        """
        try:
            max_retries = 3
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    # Prepare article text
                    article_text = self.prepare_article_text(article)
                    
                    # Log token usage for monitoring
                    input_tokens = self.count_tokens(self.system_prompt) + self.count_tokens(article_text)
                    logger.debug(f"Input tokens for article '{article.get('title', '')[:30]}...': {input_tokens}")
                    
                    # Call OpenAI API
                    logger.info(f"Analyzing article: {article.get('title', '')[:50]}...")
                    
                    # Log the model being used
                    print(f"Using OpenAI model for analysis: {self.model}")
                    
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
                    
                    # Log the model from the response
                    print(f"OpenAI response model: {response.model}")
                    logger.info(f"Analysis completed using model: {response.model}")
                    
                    
                    # If we get here, the API call was successful, so break the retry loop
                    break
                    
                except Exception as e:
                    last_error = e
                    # Don't retry if it's a context length error
                    if "maximum context length" in str(e).lower():
                        logger.warning(f"Hit maximum context length error, not retrying: {e}")
                        raise e
                    
                    retry_count += 1
                    if retry_count < max_retries:
                        # Add exponential backoff: 1s, 2s, 4s, ...
                        wait_time = 2 ** (retry_count - 1)
                        logger.warning(f"API error, retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Max retries reached, giving up: {e}")
                        raise e
            
            # If we exhausted retries and still have an error, re-raise it
            if retry_count == max_retries and last_error is not None:
                raise last_error
            
            # Update stats
            self.total_tokens_used += response.usage.total_tokens
            self.total_api_calls += 1
            
            # Parse the response
            response_content = response.choices[0].message.content
            print("\n====== OPENAI ENTITY RESPONSE ======")
            print(response_content)
            print("===================================\n")
            
            # Log the actual model used from the API response
            print(f"OpenAI model used: {response.model}")
            logger.info(f"Analysis performed using OpenAI model: {response.model}")
            
            result = json.loads(response_content)
            
            # Add results to article data
            article['entities'] = result.get('entities', [])
            article['source_country'] = result.get('source_country', None)  # Extract LLM-determined country
            article['analysis_model'] = response.model or self.model  # Use actual model from response
            article['processed_at'] = time.time()
            
            # Log detailed information about extracted entities
            entities = article['entities']
            print(f"\nExtracted {len(entities)} entities:")
            for entity in entities:
                print(f"  - {entity.get('entity', 'Unknown')} ({entity.get('entity_type', 'Unknown')})")
                print(f"    Power: {entity.get('power_score', 'N/A')}, Moral: {entity.get('moral_score', 'N/A')}")
                print(f"    Mentions: {len(entity.get('mentions', []))}")
            
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
            
            # Simple retry logic with exponential backoff
            max_retries = 3
            retry_count = 0
            
            while True:
                try:
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
                    break  # Success, exit the retry loop
                except Exception as e:
                    # Don't retry if it's a context length error
                    if "maximum context length" in str(e).lower():
                        raise e
                    
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise e  # Max retries reached, re-raise the exception
                    
                    # Exponential backoff
                    wait_time = 2 ** (retry_count - 1)
                    logger.warning(f"API error, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Log the actual model used
            logger.info(f"Async analysis performed using OpenAI model: {response.model}")
            
            # Add results to article data
            article['entities'] = result.get('entities', [])
            article['analysis_model'] = response.model or self.model  # Use actual model from response
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
    
    def __init__(self, api_key: str = None, model: str = "gpt-4.1-nano"):
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