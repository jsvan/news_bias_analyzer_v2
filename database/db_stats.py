"""
Database statistics module for News Bias Analyzer.
Provides information about the database state.
"""

import os
import sys
import logging
from typing import Dict, Any, List, Tuple
from sqlalchemy import func, case, text
import datetime

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import DatabaseManager
from database.models import NewsArticle, NewsSource, Entity, EntityMention, Quote, Topic, PublicFigure

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_database_stats() -> Dict[str, Any]:
    """
    Get comprehensive statistics about the database.
    
    Returns:
        Dictionary with statistics about articles, entities, and processing
    """
    try:
        # Initialize database connection
        db_manager = DatabaseManager()
        session = db_manager.get_session()
        
        stats = {}
        
        # Get article statistics
        article_stats = {}
        
        # Total articles count
        article_stats['total_count'] = session.query(func.count(NewsArticle.id)).scalar() or 0
        
        # Articles with text content
        article_stats['with_text_count'] = session.query(
            func.count(NewsArticle.id)
        ).filter(
            NewsArticle.text.isnot(None),
            func.length(NewsArticle.text) > 0
        ).scalar() or 0
        
        # Articles that have been processed
        article_stats['processed_count'] = session.query(
            func.count(NewsArticle.id)
        ).filter(
            NewsArticle.processed_at.isnot(None)
        ).scalar() or 0
        
        # Articles processing percentage
        if article_stats['total_count'] > 0:
            article_stats['processed_percentage'] = round(
                (article_stats['processed_count'] / article_stats['total_count']) * 100, 2
            )
        else:
            article_stats['processed_percentage'] = 0
        
        # Average article length (if there are articles with text)
        if article_stats['with_text_count'] > 0:
            article_stats['avg_length'] = session.query(
                func.avg(func.length(NewsArticle.text))
            ).filter(
                NewsArticle.text.isnot(None),
                func.length(NewsArticle.text) > 0
            ).scalar() or 0
            article_stats['avg_length'] = int(article_stats['avg_length'])
        else:
            article_stats['avg_length'] = 0
        
        # Recent articles
        current_time = datetime.datetime.now()
        article_stats['last_24h_count'] = session.query(
            func.count(NewsArticle.id)
        ).filter(
            NewsArticle.scraped_at > (current_time - datetime.timedelta(days=1))
        ).scalar() or 0
        
        article_stats['last_7d_count'] = session.query(
            func.count(NewsArticle.id)
        ).filter(
            NewsArticle.scraped_at > (current_time - datetime.timedelta(days=7))
        ).scalar() or 0
        
        # Get source statistics
        source_stats = {}
        
        # Total sources count
        source_stats['total_count'] = session.query(func.count(NewsSource.id)).scalar() or 0
        
        # Top 5 sources by article count
        top_sources = session.query(
            NewsSource.name,
            func.count(NewsArticle.id).label('article_count')
        ).join(
            NewsArticle, NewsSource.id == NewsArticle.source_id
        ).group_by(
            NewsSource.name
        ).order_by(
            text('article_count DESC')
        ).limit(5).all()
        
        source_stats['top_sources'] = [{'name': name, 'article_count': count} for name, count in top_sources]
        
        # Get entity statistics
        entity_stats = {}
        
        # Total entities count
        entity_stats['total_count'] = session.query(func.count(Entity.id)).scalar() or 0
        
        # Total entity mentions
        entity_stats['mentions_count'] = session.query(func.count(EntityMention.id)).scalar() or 0
        
        # Most mentioned entities
        top_entities = session.query(
            Entity.name,
            Entity.entity_type,
            func.count(EntityMention.id).label('mention_count')
        ).join(
            EntityMention, Entity.id == EntityMention.entity_id
        ).group_by(
            Entity.name, Entity.entity_type
        ).order_by(
            text('mention_count DESC')
        ).limit(5).all()
        
        entity_stats['top_entities'] = [
            {'name': name, 'type': entity_type, 'mention_count': count} 
            for name, entity_type, count in top_entities
        ]
        
        # Entity types distribution
        entity_types = session.query(
            Entity.entity_type,
            func.count(Entity.id).label('count')
        ).group_by(
            Entity.entity_type
        ).order_by(
            text('count DESC')
        ).all()
        
        entity_stats['entity_types'] = [
            {'type': entity_type or 'unknown', 'count': count} 
            for entity_type, count in entity_types
        ]
        
        # Compile all statistics
        stats['article_stats'] = article_stats
        stats['source_stats'] = source_stats
        stats['entity_stats'] = entity_stats
        
        # Check if Quote table exists
        quote_exists = True
        try:
            quote_count = session.query(func.count(Quote.id)).scalar() or 0
        except:
            # Quote table doesn't exist or isn't accessible
            quote_exists = False
            
        # Quote statistics if we have any
        if quote_exists and quote_count > 0:
            quote_stats = {}
            quote_stats['total_count'] = quote_count
            
            # Check if PublicFigure table exists and is accessible
            try:
                # Top public figures with quotes
                top_figures = session.query(
                    PublicFigure.name,
                    func.count(Quote.id).label('quote_count')
                ).join(
                    Quote, PublicFigure.id == Quote.public_figure_id
                ).group_by(
                    PublicFigure.name
                ).order_by(
                    text('quote_count DESC')
                ).limit(5).all()
                
                quote_stats['top_figures'] = [
                    {'name': name, 'quote_count': count}
                    for name, count in top_figures
                ]
            except:
                # PublicFigure table might not exist or relation is different
                quote_stats['top_figures'] = []
            
            stats['quote_stats'] = quote_stats
        
        session.close()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting database statistics: {e}")
        if 'session' in locals():
            session.close()
        return {"error": str(e)}

def format_stats_output(stats: Dict[str, Any]) -> str:
    """
    Format the database statistics for display.
    
    Args:
        stats: Dictionary with statistics
        
    Returns:
        Formatted string for console output
    """
    if "error" in stats:
        return f"Error retrieving database statistics: {stats['error']}"
        
    output = []
    
    # Format article statistics
    article_stats = stats['article_stats']
    output.append("\n===== ARTICLE STATISTICS =====")
    output.append(f"Total articles: {article_stats['total_count']}")
    output.append(f"Articles with text: {article_stats['with_text_count']}")
    output.append(f"Processed articles: {article_stats['processed_count']} ({article_stats['processed_percentage']}%)")
    output.append(f"Average article length: {article_stats['avg_length']} characters")
    output.append(f"Articles in last 24 hours: {article_stats['last_24h_count']}")
    output.append(f"Articles in last 7 days: {article_stats['last_7d_count']}")
    
    # Format source statistics
    source_stats = stats['source_stats']
    output.append("\n===== SOURCE STATISTICS =====")
    output.append(f"Total news sources: {source_stats['total_count']}")
    if source_stats['top_sources']:
        output.append("Top sources by article count:")
        for i, source in enumerate(source_stats['top_sources'], 1):
            output.append(f"  {i}. {source['name']}: {source['article_count']} articles")
    
    # Format entity statistics
    entity_stats = stats['entity_stats']
    output.append("\n===== ENTITY STATISTICS =====")
    output.append(f"Total entities: {entity_stats['total_count']}")
    output.append(f"Total entity mentions: {entity_stats['mentions_count']}")
    
    if entity_stats['top_entities']:
        output.append("Most mentioned entities:")
        for i, entity in enumerate(entity_stats['top_entities'], 1):
            output.append(f"  {i}. {entity['name']} ({entity['type']}): {entity['mention_count']} mentions")
    
    # Format quote statistics if available
    if 'quote_stats' in stats:
        quote_stats = stats['quote_stats']
        output.append("\n===== QUOTE STATISTICS =====")
        output.append(f"Total quotes: {quote_stats['total_count']}")
        
        if quote_stats.get('top_figures', []):
            output.append("Top quoted figures:")
            for i, figure in enumerate(quote_stats['top_figures'], 1):
                output.append(f"  {i}. {figure['name']}: {figure['quote_count']} quotes")
    
    return "\n".join(output)

def main():
    """Main entry point for database statistics."""
    stats = get_database_stats()
    print(format_stats_output(stats))
    return 0

if __name__ == "__main__":
    sys.exit(main())