"""
API layer for serving similarity and clustering data.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import json

from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class SimilarityAPI(BaseAnalyzer):
    """Provides API methods for accessing similarity data."""
    
    def get_source_similarities(self, 
                              source_id: int, 
                              limit: int = 20,
                              week: Optional[datetime] = None) -> List[Dict]:
        """Get most similar sources for a given source."""
        if week is None:
            week = datetime.utcnow()
        
        start_date, end_date = self.get_week_boundaries(week)
        
        query = text("""
            SELECT 
                CASE 
                    WHEN ssm.source_id_1 = :source_id THEN ssm.source_id_2
                    ELSE ssm.source_id_1
                END as other_source_id,
                ns.name as source_name,
                ns.country,
                ssm.similarity_score,
                ssm.common_entities,
                ssm.calculation_method
            FROM source_similarity_matrix ssm
            JOIN news_sources ns ON ns.id = CASE 
                WHEN ssm.source_id_1 = :source_id THEN ssm.source_id_2
                ELSE ssm.source_id_1
            END
            WHERE 
                (:source_id = ssm.source_id_1 OR :source_id = ssm.source_id_2)
                AND ssm.time_window_start >= :start_date
                AND ssm.time_window_end <= :end_date
            ORDER BY ssm.similarity_score DESC
            LIMIT :limit
        """)
        
        results = self.session.execute(query, {
            'source_id': source_id,
            'start_date': start_date,
            'end_date': end_date,
            'limit': limit
        }).fetchall()
        
        return [
            {
                'source_id': row.other_source_id,
                'source_name': row.source_name,
                'country': row.country,
                'similarity_score': float(row.similarity_score),
                'common_entities': row.common_entities,
                'method': row.calculation_method
            }
            for row in results
        ]
    
    def get_source_drift(self, 
                       source_id: int, 
                       weeks: int = 4,
                       top_entities: int = 20) -> Dict:
        """Get sentiment drift for top entities over time."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(weeks=weeks)
        
        # Get drift data
        query = text("""
            WITH entity_importance AS (
                SELECT 
                    entity_id,
                    SUM(mention_count) as total_mentions,
                    AVG(ABS(sentiment_change)) as avg_change
                FROM source_temporal_drift
                WHERE 
                    source_id = :source_id
                    AND week_start >= :start_date
                GROUP BY entity_id
                ORDER BY total_mentions DESC
                LIMIT :top_entities
            )
            SELECT 
                std.entity_id,
                e.name as entity_name,
                std.week_start,
                std.avg_sentiment,
                std.sentiment_change,
                std.mention_count
            FROM source_temporal_drift std
            JOIN entities e ON std.entity_id = e.id
            WHERE 
                std.source_id = :source_id
                AND std.entity_id IN (SELECT entity_id FROM entity_importance)
                AND std.week_start >= :start_date
            ORDER BY std.entity_id, std.week_start
        """)
        
        results = self.session.execute(query, {
            'source_id': source_id,
            'start_date': start_date.date(),
            'top_entities': top_entities
        }).fetchall()
        
        # Organize by entity
        entity_trends = {}
        for row in results:
            if row.entity_id not in entity_trends:
                entity_trends[row.entity_id] = {
                    'entity_name': row.entity_name,
                    'weekly_data': []
                }
            
            entity_trends[row.entity_id]['weekly_data'].append({
                'week': row.week_start.isoformat(),
                'sentiment': float(row.avg_sentiment),
                'change': float(row.sentiment_change) if row.sentiment_change else 0,
                'mentions': row.mention_count
            })
        
        # Calculate summary stats
        total_change = sum(
            abs(week['change']) 
            for trend in entity_trends.values() 
            for week in trend['weekly_data']
        )
        
        return {
            'source_id': source_id,
            'weeks_analyzed': weeks,
            'entity_trends': list(entity_trends.values()),
            'total_volatility': float(total_change)
        }
    
    def get_volatile_entities(self, 
                            limit: int = 50,
                            week: Optional[datetime] = None) -> List[Dict]:
        """Get entities with highest volatility scores."""
        if week is None:
            week = datetime.utcnow()
            
        start_date, end_date = self.get_week_boundaries(week)
        
        query = text("""
            SELECT 
                ev.entity_id,
                e.name as entity_name,
                e.entity_type,
                ev.volatility_score,
                ev.source_divergence,
                ev.mention_count,
                -- Get top disagreeing sources
                (
                    SELECT json_agg(source_sentiment)
                    FROM (
                        SELECT json_build_object(
                            'source_name', ns.name,
                            'sentiment', AVG((em.power_score + em.moral_score) / 2.0)
                        ) as source_sentiment
                        FROM entity_mentions em
                        JOIN news_articles na ON em.article_id = na.id
                        JOIN news_sources ns ON na.source_id = ns.id
                        WHERE 
                            em.entity_id = ev.entity_id
                            AND na.publish_date BETWEEN ev.time_window_start AND ev.time_window_end
                        GROUP BY ns.id, ns.name
                        ORDER BY ABS(AVG((em.power_score + em.moral_score) / 2.0)) DESC
                        LIMIT 5
                    ) top_sources
                ) as top_sources
            FROM entity_volatility ev
            JOIN entities e ON ev.entity_id = e.id
            WHERE 
                ev.time_window_start >= :start_date
                AND ev.time_window_end <= :end_date
            ORDER BY ev.volatility_score DESC
            LIMIT :limit
        """)
        
        results = self.session.execute(query, {
            'start_date': start_date,
            'end_date': end_date,
            'limit': limit
        }).fetchall()
        
        return [
            {
                'entity_id': row.entity_id,
                'entity_name': row.entity_name,
                'entity_type': row.entity_type,
                'volatility_score': float(row.volatility_score),
                'source_divergence': float(row.source_divergence),
                'mention_count': row.mention_count,
                'divergent_sources': json.loads(row.top_sources) if row.top_sources else []
            }
            for row in results
        ]
    
    def get_source_clusters(self, 
                          country: Optional[str] = None,
                          date: Optional[datetime] = None) -> Dict:
        """Get clustering visualization data."""
        if date is None:
            date = datetime.utcnow()
            
        query = text("""
            WITH latest_clusters AS (
                SELECT DISTINCT ON (source_id)
                    sc.source_id,
                    sc.cluster_id,
                    sc.cluster_level,
                    sc.similarity_to_centroid,
                    sc.is_centroid,
                    sc.metadata,
                    ns.name as source_name,
                    ns.country
                FROM source_clusters sc
                JOIN news_sources ns ON sc.source_id = ns.id
                WHERE 
                    sc.assigned_date <= :date
                    AND (:country IS NULL OR ns.country = :country)
                ORDER BY sc.source_id, sc.assigned_date DESC
            )
            SELECT 
                cluster_id,
                cluster_level,
                json_agg(
                    json_build_object(
                        'source_id', source_id,
                        'source_name', source_name,
                        'country', country,
                        'is_centroid', is_centroid,
                        'similarity_to_centroid', similarity_to_centroid
                    )
                ) as members
            FROM latest_clusters
            GROUP BY cluster_id, cluster_level
            ORDER BY cluster_level, cluster_id
        """)
        
        results = self.session.execute(query, {
            'date': date.date(),
            'country': country
        }).fetchall()
        
        clusters = []
        for row in results:
            members = json.loads(row.members)
            clusters.append({
                'cluster_id': row.cluster_id,
                'level': row.cluster_level,
                'size': len(members),
                'members': members
            })
        
        return {
            'date': date.date().isoformat(),
            'country': country,
            'num_clusters': len(clusters),
            'clusters': clusters
        }
    
    def get_article_source_comparison(self, article_id: str) -> Dict:
        """Get alternative source perspectives for an article's entities."""
        # Get article's source and main entities
        query = text("""
            SELECT 
                na.source_id,
                ns.name as source_name,
                ns.country,
                em.entity_id,
                e.name as entity_name,
                AVG((em.power_score + em.moral_score) / 2.0) as sentiment
            FROM news_articles na
            JOIN news_sources ns ON na.source_id = ns.id
            JOIN entity_mentions em ON na.id = em.article_id
            JOIN entities e ON em.entity_id = e.id
            WHERE 
                na.id = :article_id
                AND em.power_score IS NOT NULL
            GROUP BY na.source_id, ns.name, ns.country, em.entity_id, e.name
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """)
        
        results = self.session.execute(query, {'article_id': article_id}).fetchall()
        
        if not results:
            return {'error': 'Article not found or no entities'}
        
        source_id = results[0].source_id
        source_name = results[0].source_name
        country = results[0].country
        
        # Get top entities from this article
        entities = [
            {
                'entity_id': row.entity_id,
                'entity_name': row.entity_name,
                'sentiment': float(row.sentiment)
            }
            for row in results
        ]
        
        # Get similar sources
        similar_sources = self.get_source_similarities(source_id, limit=5)
        
        # Get sentiment from similar sources for same entities
        if similar_sources and entities:
            entity_ids = [e['entity_id'] for e in entities]
            similar_source_ids = [s['source_id'] for s in similar_sources]
            
            comparison_query = text("""
                SELECT 
                    na.source_id,
                    em.entity_id,
                    AVG((em.power_score + em.moral_score) / 2.0) as sentiment,
                    COUNT(*) as mentions
                FROM entity_mentions em
                JOIN news_articles na ON em.article_id = na.id
                WHERE 
                    na.source_id = ANY(:source_ids)
                    AND em.entity_id = ANY(:entity_ids)
                    AND na.publish_date >= :start_date
                GROUP BY na.source_id, em.entity_id
            """)
            
            week_ago = datetime.utcnow() - timedelta(days=7)
            comp_results = self.session.execute(comparison_query, {
                'source_ids': similar_source_ids,
                'entity_ids': entity_ids,
                'start_date': week_ago
            }).fetchall()
            
            # Organize comparisons
            comparisons = {}
            for row in comp_results:
                key = (row.source_id, row.entity_id)
                comparisons[key] = {
                    'sentiment': float(row.sentiment),
                    'mentions': row.mentions
                }
            
            # Add comparison data to similar sources
            for source in similar_sources:
                source['entity_sentiments'] = []
                for entity in entities:
                    key = (source['source_id'], entity['entity_id'])
                    if key in comparisons:
                        source['entity_sentiments'].append({
                            'entity_name': entity['entity_name'],
                            'sentiment': comparisons[key]['sentiment'],
                            'mentions': comparisons[key]['mentions'],
                            'difference': comparisons[key]['sentiment'] - entity['sentiment']
                        })
        
        return {
            'article_id': article_id,
            'source': {
                'id': source_id,
                'name': source_name,
                'country': country
            },
            'entities': entities,
            'similar_sources': similar_sources
        }