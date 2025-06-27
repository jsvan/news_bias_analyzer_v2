"""
Core source similarity computation module.
"""

import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import numpy as np
from scipy import stats
from multiprocessing import Pool, cpu_count
from sqlalchemy.orm import Session
from sqlalchemy import text

from .base import BaseAnalyzer, ClusterConfig, log_timing
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    logger.warning("tqdm not available, using basic progress logging")

logger = logging.getLogger(__name__)


class SourceSimilarityComputer(BaseAnalyzer):
    """Computes pairwise similarities between news sources."""
    
    @log_timing
    def compute_weekly_similarities(self, week_start: datetime = None):
        """Main entry point for weekly similarity computation."""
        logger.info("Starting weekly similarity computation")
        
        # Get time window
        start_date, end_date = self.get_week_boundaries(week_start)
        logger.info(f"Computing similarities for week {start_date.date()} to {end_date.date()}")
        
        # Get list of countries with active sources
        countries = self._get_active_countries(start_date, end_date)
        logger.info(f"Found {len(countries)} countries with active sources")
        
        # Process each country
        for country in countries:
            logger.info(f"Processing country: {country}")
            self._process_country_similarities(country, start_date, end_date)
            
        # Compute global cluster similarities
        logger.info("Computing cross-country cluster similarities")
        self._compute_cluster_similarities(start_date, end_date)
        
        logger.info("Weekly similarity computation complete")
    
    def _get_active_countries(self, start_date: datetime, end_date: datetime) -> List[str]:
        """Get list of countries with active sources."""
        query = text("""
            SELECT DISTINCT ns.country
            FROM news_sources ns
            JOIN news_articles na ON ns.id = na.source_id
            WHERE 
                na.publish_date BETWEEN :start_date AND :end_date
                AND ns.country IS NOT NULL
            GROUP BY ns.country
            HAVING COUNT(DISTINCT na.id) >= :min_articles
        """)
        
        results = self.session.execute(query, {
            'start_date': start_date,
            'end_date': end_date,
            'min_articles': self.config.MIN_ARTICLES_FOR_COMPARISON
        }).fetchall()
        
        return [row.country for row in results]
    
    def _process_country_similarities(self, 
                                    country: str, 
                                    start_date: datetime, 
                                    end_date: datetime):
        """Process similarities for all sources in a country."""
        # Get active sources
        sources = self.get_active_sources(start_date, end_date, country)
        logger.info(f"Found {len(sources)} active sources in {country}")
        
        if len(sources) < 2:
            logger.warning(f"Not enough sources in {country} for comparison")
            return
            
        # Separate into tiers
        tier1_sources = sources[:self.config.TIER1_SOURCES_PER_COUNTRY]
        tier2_sources = sources[self.config.TIER1_SOURCES_PER_COUNTRY:]
        
        # Get entity vectors for all sources
        all_source_ids = [s['id'] for s in sources]
        entity_vectors = self.get_source_entity_vectors(
            all_source_ids, start_date, end_date
        )
        
        # Compute Tier 1 similarities (full pairwise)
        logger.info(f"Computing Tier 1 similarities for {len(tier1_sources)} major sources")
        tier1_similarities = self._compute_pairwise_similarities(
            tier1_sources, entity_vectors, start_date, end_date
        )
        
        # Store Tier 1 similarities
        self._store_similarities(tier1_similarities)
        
        # If we have Tier 2 sources, compute their cluster similarities
        if tier2_sources:
            logger.info(f"Computing cluster assignments for {len(tier2_sources)} Tier 2 sources")
            # This will be implemented in ClusterManager
            # For now, compute similarities to Tier 1 sources as representatives
            tier2_similarities = self._compute_tier2_similarities(
                tier1_sources, tier2_sources, entity_vectors, start_date, end_date
            )
            self._store_similarities(tier2_similarities)
    
    @log_timing
    def _compute_pairwise_similarities(self,
                                     sources: List[Dict],
                                     entity_vectors: Dict,
                                     start_date: datetime,
                                     end_date: datetime) -> List[Dict]:
        """Compute all pairwise similarities for a list of sources."""
        similarities = []
        
        total_pairs = len(sources) * (len(sources) - 1) // 2
        logger.info(f"Computing {total_pairs} pairwise similarities")
        
        if TQDM_AVAILABLE:
            progress_bar = tqdm(total=total_pairs, desc="Computing similarities")
        else:
            processed = 0
            log_interval = max(1, total_pairs // 10)
        
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                source1 = sources[i]
                source2 = sources[j]
                
                # Skip if we don't have vectors
                if source1['id'] not in entity_vectors or source2['id'] not in entity_vectors:
                    continue
                    
                # Compute similarity
                result = self.compute_pearson_correlation(
                    entity_vectors[source1['id']],
                    entity_vectors[source2['id']]
                )
                
                if result is not None:
                    correlation, common_entities = result
                    similarities.append({
                        'source_id_1': source1['id'],
                        'source_id_2': source2['id'],
                        'similarity_score': float(correlation),
                        'common_entities': common_entities,
                        'calculation_method': 'pearson_common',
                        'time_window_start': start_date,
                        'time_window_end': end_date
                    })
                
                if TQDM_AVAILABLE:
                    progress_bar.update(1)
                else:
                    processed += 1
                    if processed % log_interval == 0:
                        logger.info(f"Progress: {processed}/{total_pairs} pairs ({processed/total_pairs*100:.1f}%)")
        
        if TQDM_AVAILABLE:
            progress_bar.close()
            
        logger.info(f"Found {len(similarities)} valid similarities out of {total_pairs} possible pairs")
        return similarities
    
    def _compute_tier2_similarities(self,
                                   tier1_sources: List[Dict],
                                   tier2_sources: List[Dict],
                                   entity_vectors: Dict,
                                   start_date: datetime,
                                   end_date: datetime) -> List[Dict]:
        """Compute similarities between Tier 2 sources and Tier 1 representatives."""
        similarities = []
        
        for tier2_source in tier2_sources:
            if tier2_source['id'] not in entity_vectors:
                continue
                
            tier2_vector = entity_vectors[tier2_source['id']]
            
            # Find most similar Tier 1 source
            best_similarity = -1
            best_match = None
            
            for tier1_source in tier1_sources:
                if tier1_source['id'] not in entity_vectors:
                    continue
                    
                result = self.compute_pearson_correlation(
                    tier2_vector,
                    entity_vectors[tier1_source['id']]
                )
                
                if result is not None:
                    correlation, common_entities = result
                    if correlation > best_similarity:
                        best_similarity = correlation
                        best_match = {
                            'source_id_1': tier2_source['id'],
                            'source_id_2': tier1_source['id'],
                            'similarity_score': float(correlation),
                            'common_entities': common_entities,
                            'calculation_method': 'pearson_common',
                            'time_window_start': start_date,
                            'time_window_end': end_date
                        }
            
            if best_match:
                similarities.append(best_match)
                
        return similarities
    
    def _compute_cluster_similarities(self, start_date: datetime, end_date: datetime):
        """Compute similarities between cluster centroids across countries."""
        # This will be implemented after ClusterManager
        # For now, just log
        logger.info("Cluster similarity computation not yet implemented")
    
    def _store_similarities(self, similarities: List[Dict]):
        """Bulk store similarity results to database."""
        if not similarities:
            return
            
        # Delete existing similarities for this time window
        # (to handle re-runs)
        delete_query = text("""
            DELETE FROM source_similarity_matrix
            WHERE 
                time_window_start = :start_date
                AND time_window_end = :end_date
                AND (
                    (source_id_1 = ANY(:source_ids) AND source_id_2 = ANY(:source_ids))
                )
        """)
        
        all_source_ids = list(set(
            [s['source_id_1'] for s in similarities] + 
            [s['source_id_2'] for s in similarities]
        ))
        
        self.session.execute(delete_query, {
            'start_date': similarities[0]['time_window_start'],
            'end_date': similarities[0]['time_window_end'],
            'source_ids': all_source_ids
        })
        
        # Insert new similarities
        insert_query = text("""
            INSERT INTO source_similarity_matrix (
                source_id_1, source_id_2, similarity_score, 
                common_entities, calculation_method,
                time_window_start, time_window_end, created_at
            ) VALUES (
                :source_id_1, :source_id_2, :similarity_score,
                :common_entities, :calculation_method,
                :time_window_start, :time_window_end, NOW()
            )
        """)
        
        for sim in similarities:
            self.session.execute(insert_query, sim)
            
        self.session.commit()
        logger.info(f"Stored {len(similarities)} similarity scores")
    
    def compute_temporal_correlation(self,
                                   source1_id: int,
                                   source2_id: int,
                                   entity_id: int,
                                   days: int = 30) -> Optional[Dict]:
        """
        Compute correlation of sentiment changes over time.
        
        Returns correlation of daily sentiment changes, optimal lag,
        and other temporal metrics.
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        query = text("""
            WITH daily_sentiments AS (
                SELECT 
                    na.source_id,
                    DATE(na.publish_date) as date,
                    AVG((em.power_score + em.moral_score) / 2.0) as avg_sentiment
                FROM entity_mentions em
                JOIN news_articles na ON em.article_id = na.id
                WHERE 
                    na.source_id IN (:source1_id, :source2_id)
                    AND em.entity_id = :entity_id
                    AND na.publish_date BETWEEN :start_date AND :end_date
                GROUP BY na.source_id, DATE(na.publish_date)
            )
            SELECT 
                source_id,
                date,
                avg_sentiment
            FROM daily_sentiments
            ORDER BY date, source_id
        """)
        
        results = self.session.execute(query, {
            'source1_id': source1_id,
            'source2_id': source2_id,
            'entity_id': entity_id,
            'start_date': start_date,
            'end_date': end_date
        }).fetchall()
        
        # Organize by source
        source1_data = {}
        source2_data = {}
        
        for row in results:
            if row.source_id == source1_id:
                source1_data[row.date] = row.avg_sentiment
            else:
                source2_data[row.date] = row.avg_sentiment
        
        # Need at least 5 days of overlap
        common_dates = sorted(set(source1_data.keys()) & set(source2_data.keys()))
        if len(common_dates) < 5:
            return None
            
        # Calculate daily changes
        source1_changes = []
        source2_changes = []
        
        for i in range(1, len(common_dates)):
            prev_date = common_dates[i-1]
            curr_date = common_dates[i]
            
            source1_changes.append(source1_data[curr_date] - source1_data[prev_date])
            source2_changes.append(source2_data[curr_date] - source2_data[prev_date])
        
        # Compute correlation
        if len(source1_changes) > 0:
            correlation = np.corrcoef(source1_changes, source2_changes)[0, 1]
            
            # Compute lag correlation (simplified - full implementation would use ccf)
            max_lag = min(5, len(source1_changes) // 2)
            lag_correlations = []
            
            for lag in range(-max_lag, max_lag + 1):
                if lag < 0:
                    # Source 2 leads
                    s1 = source1_changes[-lag:]
                    s2 = source2_changes[:lag]
                elif lag > 0:
                    # Source 1 leads  
                    s1 = source1_changes[:-lag]
                    s2 = source2_changes[lag:]
                else:
                    s1 = source1_changes
                    s2 = source2_changes
                    
                if len(s1) > 0 and len(s2) > 0 and len(s1) == len(s2):
                    lag_corr = np.corrcoef(s1, s2)[0, 1]
                    lag_correlations.append((lag, lag_corr))
            
            # Find optimal lag
            optimal_lag = max(lag_correlations, key=lambda x: abs(x[1]))[0]
            
            return {
                'correlation': float(correlation),
                'optimal_lag': optimal_lag,
                'num_days': len(common_dates),
                'common_dates': len(common_dates)
            }
            
        return None