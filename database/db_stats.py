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
from statistical_database.db_manager import StatisticalDBManager

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
        
        # Articles that have been processed (both completed and in-progress)
        article_stats['processed_count'] = session.query(
            func.count(NewsArticle.id)
        ).filter(
            NewsArticle.analysis_status.in_(["completed", "in_progress"])
        ).scalar() or 0
        
        # Articles that have completed processing
        article_stats['completed_count'] = session.query(
            func.count(NewsArticle.id)
        ).filter(
            NewsArticle.analysis_status == "completed"
        ).scalar() or 0
        
        # Articles with T² scores
        article_stats['t2_score_count'] = session.query(
            func.count(NewsArticle.id)
        ).filter(
            NewsArticle.hotelling_t2_score.isnot(None)
        ).scalar() or 0
        
        # T² score distribution (if any exist)
        if article_stats['t2_score_count'] > 0:
            t2_stats = session.query(
                func.min(NewsArticle.hotelling_t2_score).label('min_t2'),
                func.avg(NewsArticle.hotelling_t2_score).label('avg_t2'),
                func.max(NewsArticle.hotelling_t2_score).label('max_t2')
            ).filter(
                NewsArticle.hotelling_t2_score.isnot(None)
            ).first()
            
            article_stats['t2_min'] = round(t2_stats.min_t2, 2) if t2_stats.min_t2 else 0
            article_stats['t2_avg'] = round(t2_stats.avg_t2, 2) if t2_stats.avg_t2 else 0
            article_stats['t2_max'] = round(t2_stats.max_t2, 2) if t2_stats.max_t2 else 0
        
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
        
        # Get analysis status breakdown
        status_breakdown = session.query(
            NewsArticle.analysis_status,
            func.count(NewsArticle.id)
        ).group_by(
            NewsArticle.analysis_status
        ).all()
        
        article_stats['status_breakdown'] = {
            status or 'null': count for status, count in status_breakdown
        }
        
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
        
        # Get total deleted entities from statistical database
        try:
            stats_db = StatisticalDBManager()
            entity_stats['total_deleted'] = stats_db.get_system_metric('total_entities_deleted')
        except Exception as e:
            logger.warning(f"Could not get deleted entities metric: {e}")
            entity_stats['total_deleted'] = 0
        
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
    if 'completed_count' in article_stats:
        completed_percentage = round((article_stats['completed_count'] / article_stats['total_count'] * 100) if article_stats['total_count'] > 0 else 0, 1)
        output.append(f"Completed articles: {article_stats['completed_count']} ({completed_percentage}%)")
    if 't2_score_count' in article_stats:
        t2_percentage = round((article_stats['t2_score_count'] / article_stats['completed_count'] * 100) if article_stats['completed_count'] > 0 else 0, 1)
        output.append(f"Articles with T² scores: {article_stats['t2_score_count']} ({t2_percentage}% of completed)")
        if article_stats['t2_score_count'] > 0 and 't2_min' in article_stats:
            output.append(f"  T² range: {article_stats['t2_min']} - {article_stats['t2_max']} (avg: {article_stats['t2_avg']})")
    
    # Add analysis status breakdown if available
    if 'status_breakdown' in article_stats:
        output.append("\nAnalysis Status Breakdown:")
        for status, count in article_stats['status_breakdown'].items():
            output.append(f"  - {status}: {count} articles")
    
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
    if 'total_deleted' in entity_stats and entity_stats['total_deleted'] > 0:
        output.append(f"Total entities deleted (all-time): {entity_stats['total_deleted']}")
    
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

def get_source_statistics() -> List[Dict[str, Any]]:
    """
    Get detailed statistics for all news sources.
    
    Returns:
        List of dictionaries with statistics for each source
    """
    try:
        # Initialize database connection
        db_manager = DatabaseManager()
        session = db_manager.get_session()
        
        # Query for source statistics
        source_stats = session.query(
            NewsSource.id,
            NewsSource.name,
            NewsSource.country,
            NewsSource.language,
            func.count(NewsArticle.id).label('article_count'),
            func.count(case([(NewsArticle.analysis_status.in_(["completed", "in_progress"]), 1)])).label('processed_count'),
            func.count(case([(NewsArticle.analysis_status == 'completed', 1)])).label('analyzed_count')
        ).outerjoin(
            NewsArticle, NewsSource.id == NewsArticle.source_id
        ).group_by(
            NewsSource.id,
            NewsSource.name,
            NewsSource.country,
            NewsSource.language
        ).order_by(
            text('article_count DESC')
        ).all()
        
        # Format the results
        results = []
        for source in source_stats:
            source_data = {
                'id': source.id,
                'name': source.name,
                'country': source.country or 'Unknown',
                'language': source.language or 'Unknown',
                'article_count': source.article_count,
                'processed_count': source.processed_count,
                'analyzed_count': source.analyzed_count,
                'processed_percentage': round((source.processed_count / source.article_count * 100) if source.article_count > 0 else 0, 1),
                'analyzed_percentage': round((source.analyzed_count / source.article_count * 100) if source.article_count > 0 else 0, 1)
            }
            results.append(source_data)
            
        session.close()
        return results
        
    except Exception as e:
        logger.error(f"Error getting source statistics: {e}")
        if 'session' in locals():
            session.close()
        return []

def format_source_statistics(sources: List[Dict[str, Any]]) -> str:
    """
    Format the source statistics for display.
    
    Args:
        sources: List of dictionaries with source statistics
        
    Returns:
        Formatted string for console output
    """
    if not sources:
        return "No news sources found in the database."
        
    # Calculate totals
    total_articles = sum(source['article_count'] for source in sources)
    total_processed = sum(source['processed_count'] for source in sources)
    total_analyzed = sum(source['analyzed_count'] for source in sources)
    
    # Calculate overall percentages
    overall_processed_pct = round((total_processed / total_articles * 100) if total_articles > 0 else 0, 1)
    overall_analyzed_pct = round((total_analyzed / total_articles * 100) if total_articles > 0 else 0, 1)
    
    output = []
    output.append("\n===== NEWS SOURCE STATISTICS =====")
    output.append(f"Total Sources: {len(sources)}")
    output.append(f"Total Articles: {total_articles}")
    output.append(f"Total Processed: {total_processed} ({overall_processed_pct}%)")
    output.append(f"Total Analyzed: {total_analyzed} ({overall_analyzed_pct}%)")
    output.append("\nDetailed Source Statistics:")
    output.append("-" * 100)
    output.append(f"{'ID':<5} {'Name':<30} {'Country':<15} {'Articles':<10} {'Processed':<20} {'Analyzed':<20}")
    output.append("-" * 100)
    
    for source in sources:
        processed_info = f"{source['processed_count']} ({source['processed_percentage']}%)"
        analyzed_info = f"{source['analyzed_count']} ({source['analyzed_percentage']}%)"
        
        output.append(f"{source['id']:<5} {source['name'][:30]:<30} {source['country'][:15]:<15} "
                     f"{source['article_count']:<10} {processed_info:<20} {analyzed_info:<20}")
    
    return "\n".join(output)

def main():
    """Main entry point for database statistics."""
    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "sources":
        # Show detailed source statistics
        source_stats = get_source_statistics()
        print(format_source_statistics(source_stats))
    else:
        # Show general statistics
        stats = get_database_stats()
        print(format_stats_output(stats))
    return 0

if __name__ == "__main__":
    sys.exit(main())