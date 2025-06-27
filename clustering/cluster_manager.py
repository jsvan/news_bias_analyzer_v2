"""
Manages hierarchical clustering of news sources.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform
from sklearn.metrics import silhouette_score
from sqlalchemy.orm import Session
from sqlalchemy import text
import json

from .base import BaseAnalyzer, ClusterConfig
# Import statistical database for storing results
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from statistical_database.db_manager import StatisticalDBManager

logger = logging.getLogger(__name__)


class ClusterManager(BaseAnalyzer):
    """Handles clustering of news sources within countries."""
    
    def __init__(self, session: Session):
        super().__init__(session)
        # Initialize statistical database for storing results
        self.statistical_db = StatisticalDBManager()
    
    def analyze(self):
        """Run clustering analysis - called by statistical orchestrator."""
        logger.info("Running monthly clustering analysis...")
        return self.perform_monthly_clustering()
    
    def perform_monthly_clustering(self, month_start: datetime = None):
        """Run monthly clustering job for all countries."""
        if month_start is None:
            # Use the most recent similarity data time window
            similarity_window = self._get_latest_similarity_window()
            if similarity_window:
                month_start, month_end = similarity_window
                logger.info(f"Using latest similarity window {month_start.date()} to {month_end.date()}")
            else:
                # Default to start of current month
                now = datetime.utcnow()
                month_start = datetime(now.year, now.month, 1)
                month_end = self._get_month_end(month_start)
                logger.info(f"No similarity data found, using default month {month_start.date()} to {month_end.date()}")
        else:
            month_end = self._get_month_end(month_start)
            logger.info(f"Performing clustering for month {month_start.date()} to {month_end.date()}")
        
        # Get active countries
        countries = self._get_countries_for_clustering(month_start, month_end)
        
        for country in countries:
            logger.info(f"Clustering sources in {country}")
            self._cluster_country_sources(country, month_start, month_end)
            
        logger.info("Monthly clustering complete")
    
    def _get_month_end(self, month_start: datetime) -> datetime:
        """Get the last moment of the month."""
        if month_start.month == 12:
            next_month = datetime(month_start.year + 1, 1, 1)
        else:
            next_month = datetime(month_start.year, month_start.month + 1, 1)
        return next_month - timedelta(seconds=1)
    
    def _get_latest_similarity_window(self) -> Optional[Tuple[datetime, datetime]]:
        """Get the time window of the most recent similarity data."""
        query = text("""
            SELECT time_window_start, time_window_end 
            FROM source_similarity_matrix 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        result = self.session.execute(query).fetchone()
        if result:
            return result.time_window_start, result.time_window_end
        return None
    
    def _get_countries_for_clustering(self, start_date: datetime, end_date: datetime) -> List[str]:
        """Get countries with enough sources for clustering."""
        query = text("""
            SELECT 
                ns.country,
                COUNT(DISTINCT ns.id) as source_count
            FROM news_sources ns
            JOIN news_articles na ON ns.id = na.source_id
            WHERE 
                na.publish_date BETWEEN :start_date AND :end_date
                AND ns.country IS NOT NULL
            GROUP BY ns.country
            HAVING COUNT(DISTINCT ns.id) >= :min_sources
            ORDER BY COUNT(DISTINCT ns.id) DESC
        """)
        
        results = self.session.execute(query, {
            'start_date': start_date,
            'end_date': end_date,
            'min_sources': self.config.MIN_CLUSTER_SIZE * 2  # Need at least 2 clusters worth
        }).fetchall()
        
        return [row.country for row in results]
    
    def _cluster_country_sources(self, country: str, start_date: datetime, end_date: datetime):
        """Perform hierarchical clustering for sources in a country."""
        # Get active sources
        sources = self.get_active_sources(start_date, end_date, country)
        
        if len(sources) < self.config.MIN_CLUSTER_SIZE * 2:  # Need at least 4 for meaningful clustering
            logger.warning(f"Not enough sources in {country} for clustering ({len(sources)} sources)")
            return
            
        # If we have many sources, separate into tiers; otherwise cluster all sources
        if len(sources) > self.config.TIER1_SOURCES_PER_COUNTRY + 2:
            tier1_sources = sources[:self.config.TIER1_SOURCES_PER_COUNTRY]
            tier2_sources = sources[self.config.TIER1_SOURCES_PER_COUNTRY:]
            sources_to_cluster = tier2_sources
            logger.info(f"Clustering {len(tier2_sources)} Tier 2 sources in {country}")
        else:
            # Cluster all sources when we don't have enough for tier separation
            tier1_sources = []
            tier2_sources = sources
            sources_to_cluster = sources
            logger.info(f"Clustering all {len(sources)} sources in {country}")
        
        if len(sources_to_cluster) < self.config.MIN_CLUSTER_SIZE * 2:
            logger.warning(f"Not enough sources to cluster in {country}")
            return
            
        # Get similarity matrix for sources to cluster
        similarity_matrix = self._build_similarity_matrix(sources_to_cluster, start_date, end_date)
        
        if similarity_matrix is None:
            logger.warning(f"Could not build similarity matrix for {country}")
            return
            
        # Perform hierarchical clustering
        clusters = self._hierarchical_clustering(sources_to_cluster, similarity_matrix)
        
        # Calculate cluster quality metrics
        quality_metrics = self._calculate_cluster_quality(similarity_matrix, clusters)
        
        # Store cluster assignments
        self._store_cluster_assignments(country, tier1_sources, sources_to_cluster, 
                                      clusters, quality_metrics, start_date)
    
    def _build_similarity_matrix(self, 
                                sources: List[Dict], 
                                start_date: datetime, 
                                end_date: datetime) -> Optional[np.ndarray]:
        """Build similarity matrix from stored similarities or compute new ones."""
        source_ids = [s['id'] for s in sources]
        n = len(source_ids)
        
        # Initialize similarity matrix
        similarity_matrix = np.zeros((n, n))
        np.fill_diagonal(similarity_matrix, 1.0)
        
        # Query existing similarities
        query = text("""
            SELECT 
                source_id_1,
                source_id_2,
                similarity_score
            FROM source_similarity_matrix
            WHERE 
                time_window_start >= :start_date
                AND time_window_end <= :end_date
                AND source_id_1 = ANY(:source_ids)
                AND source_id_2 = ANY(:source_ids)
        """)
        
        results = self.session.execute(query, {
            'start_date': start_date,
            'end_date': end_date,
            'source_ids': source_ids
        }).fetchall()
        
        # Build ID to index mapping
        id_to_idx = {sid: idx for idx, sid in enumerate(source_ids)}
        
        # Fill matrix with known similarities
        found_pairs = 0
        for row in results:
            if row.source_id_1 in id_to_idx and row.source_id_2 in id_to_idx:
                idx1 = id_to_idx[row.source_id_1]
                idx2 = id_to_idx[row.source_id_2]
                similarity_matrix[idx1, idx2] = row.similarity_score
                similarity_matrix[idx2, idx1] = row.similarity_score
                found_pairs += 1
        
        # If we have too few similarities, compute missing ones
        expected_pairs = (n * (n - 1)) // 2
        if found_pairs < expected_pairs * 0.5:  # Less than 50% coverage
            logger.info(f"Computing missing similarities for clustering ({found_pairs}/{expected_pairs} found)")
            # Would compute missing similarities here
            # For now, return None to skip clustering
            return None
            
        return similarity_matrix
    
    def _hierarchical_clustering(self, 
                               sources: List[Dict], 
                               similarity_matrix: np.ndarray) -> Dict[int, str]:
        """Perform hierarchical clustering and return cluster assignments."""
        # Convert similarity to distance
        distance_matrix = 1 - similarity_matrix
        
        # Ensure it's a valid distance matrix
        distance_matrix = (distance_matrix + distance_matrix.T) / 2
        np.fill_diagonal(distance_matrix, 0)
        
        # Convert to condensed form for scipy
        condensed = squareform(distance_matrix)
        
        # Check if we have enough data for clustering
        if len(condensed) == 0 or len(sources) < 2:
            logger.warning(f"Insufficient data for clustering: {len(sources)} sources")
            # Return single cluster for all sources
            return {source['id']: 'cluster_1' for source in sources}
        
        # Perform hierarchical clustering
        linkage_matrix = hierarchy.linkage(condensed, method='average')
        
        # Cut tree at similarity threshold
        distance_threshold = 1 - self.config.CLUSTER_SIMILARITY_THRESHOLD
        cluster_labels = hierarchy.fcluster(linkage_matrix, 
                                          distance_threshold, 
                                          criterion='distance')
        
        # Create cluster assignments
        clusters = {}
        for idx, source in enumerate(sources):
            cluster_id = f"{source['country']}_cluster_{cluster_labels[idx]}"
            clusters[source['id']] = cluster_id
            
        # Validate cluster sizes
        cluster_counts = {}
        for cluster_id in clusters.values():
            cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1
            
        # Merge small clusters
        for source_id, cluster_id in list(clusters.items()):
            if cluster_counts[cluster_id] < self.config.MIN_CLUSTER_SIZE:
                # Find nearest cluster with sufficient size
                # For now, just merge with largest cluster
                largest_cluster = max(cluster_counts.items(), key=lambda x: x[1])[0]
                clusters[source_id] = largest_cluster
                
        return clusters
    
    def _calculate_cluster_quality(self, 
                                 similarity_matrix: np.ndarray, 
                                 clusters: Dict[int, str]) -> Dict:
        """Calculate quality metrics for clustering."""
        # Get cluster labels in order
        source_ids = sorted(clusters.keys())
        labels = [clusters[sid] for sid in source_ids]
        
        # Calculate silhouette score if we have multiple clusters
        unique_clusters = len(set(labels))
        if unique_clusters > 1 and unique_clusters < len(labels):
            distance_matrix = 1 - similarity_matrix
            silhouette = silhouette_score(distance_matrix, labels, metric='precomputed')
        else:
            silhouette = 0.0
            
        # Calculate intra-cluster similarity
        cluster_similarities = {}
        for cluster_id in set(clusters.values()):
            cluster_sources = [sid for sid, cid in clusters.items() if cid == cluster_id]
            if len(cluster_sources) > 1:
                # Get similarities within cluster
                similarities = []
                for i, s1 in enumerate(cluster_sources):
                    for s2 in cluster_sources[i+1:]:
                        idx1 = source_ids.index(s1)
                        idx2 = source_ids.index(s2)
                        similarities.append(similarity_matrix[idx1, idx2])
                cluster_similarities[cluster_id] = np.mean(similarities) if similarities else 0.0
            else:
                cluster_similarities[cluster_id] = 1.0
                
        return {
            'silhouette_score': float(silhouette),
            'num_clusters': unique_clusters,
            'avg_intra_cluster_similarity': float(np.mean(list(cluster_similarities.values()))),
            'cluster_similarities': cluster_similarities
        }
    
    def _store_cluster_assignments(self,
                                 country: str,
                                 tier1_sources: List[Dict],
                                 tier2_sources: List[Dict],
                                 clusters: Dict[int, str],
                                 quality_metrics: Dict,
                                 assigned_date: datetime):
        """Store cluster assignments in database."""
        # Delete existing assignments for this country and date
        delete_query = text("""
            DELETE FROM source_clusters
            WHERE 
                source_id IN (
                    SELECT id FROM news_sources WHERE country = :country
                )
                AND assigned_date = :assigned_date
        """)
        
        self.session.execute(delete_query, {
            'country': country,
            'assigned_date': assigned_date.date()
        })
        
        # Insert Tier 1 sources (each is its own cluster)
        insert_query = text("""
            INSERT INTO source_clusters (
                source_id, cluster_id, cluster_level, 
                similarity_to_centroid, assigned_date, 
                is_centroid, metadata
            ) VALUES (
                :source_id, :cluster_id, :cluster_level,
                :similarity_to_centroid, :assigned_date,
                :is_centroid, :metadata
            )
        """)
        
        # Tier 1 sources
        for source in tier1_sources:
            self.session.execute(insert_query, {
                'source_id': source['id'],
                'cluster_id': f"{country}_tier1_{source['id']}",
                'cluster_level': 1,
                'similarity_to_centroid': 1.0,
                'assigned_date': assigned_date.date(),
                'is_centroid': True,
                'metadata': json.dumps({
                    'source_name': source['name'],
                    'article_count': source['article_count']
                })
            })
        
        # Tier 2 sources with clusters
        for source in tier2_sources:
            if source['id'] in clusters:
                cluster_id = clusters[source['id']]
                # For now, all members have similarity 1.0 to centroid
                # In practice, would calculate actual similarity to centroid
                self.session.execute(insert_query, {
                    'source_id': source['id'],
                    'cluster_id': cluster_id,
                    'cluster_level': 2,
                    'similarity_to_centroid': 0.8,  # Placeholder
                    'assigned_date': assigned_date.date(),
                    'is_centroid': False,  # Would mark actual centroid
                    'metadata': json.dumps({
                        'source_name': source['name'],
                        'article_count': source['article_count'],
                        'quality_metrics': quality_metrics
                    })
                })
        
        self.session.commit()
        logger.info(f"Stored cluster assignments for {len(tier1_sources) + len(tier2_sources)} sources in {country}")
        
        # Also store clustering results in statistical database for intelligence analysis
        self._store_clustering_in_statistical_db(
            country=country,
            clusters=clusters,
            tier1_sources=tier1_sources,
            tier2_sources=tier2_sources,
            quality_metrics=quality_metrics,
            assigned_date=assigned_date
        )
    
    def get_cluster_centroid_vectors(self, 
                                   start_date: datetime, 
                                   end_date: datetime) -> Dict[str, Dict[int, float]]:
        """Get sentiment vectors for cluster centroids."""
        # Get latest cluster assignments
        query = text("""
            SELECT DISTINCT ON (cluster_id)
                cluster_id,
                source_id,
                is_centroid
            FROM source_clusters
            WHERE 
                assigned_date <= :end_date
                AND cluster_level IN (1, 2)
            ORDER BY cluster_id, assigned_date DESC
        """)
        
        results = self.session.execute(query, {
            'end_date': end_date.date()
        }).fetchall()
        
        # For Tier 1, use the source directly
        # For Tier 2, compute average of cluster members
        centroid_vectors = {}
        
        for row in results:
            if row.is_centroid:
                # Get vector for this source
                vectors = self.get_source_entity_vectors([row.source_id], start_date, end_date)
                if row.source_id in vectors:
                    centroid_vectors[row.cluster_id] = vectors[row.source_id]
            else:
                # Compute average for cluster members
                # Would need to get all members and average their vectors
                # For now, skip
                pass
                
        return centroid_vectors
    
    def _store_clustering_in_statistical_db(self,
                                           country: str,
                                           clusters: Dict[int, str],
                                           tier1_sources: List[Dict],
                                           tier2_sources: List[Dict],
                                           quality_metrics: Dict,
                                           assigned_date: datetime):
        """Store clustering results in statistical database for intelligence analysis."""
        try:
            # Calculate time window (use monthly clustering window)
            month_start = datetime(assigned_date.year, assigned_date.month, 1)
            month_end = self._get_month_end(month_start)
            
            # Group clusters and calculate metrics for each
            cluster_groups = {}
            
            # Add Tier 1 sources (each is its own cluster)
            for source in tier1_sources:
                cluster_id = f"{country}_tier1_{source['id']}"
                cluster_groups[cluster_id] = [source]
            
            # Add Tier 2 source clusters
            for source in tier2_sources:
                if source['id'] in clusters:
                    cluster_id = clusters[source['id']]
                    if cluster_id not in cluster_groups:
                        cluster_groups[cluster_id] = []
                    cluster_groups[cluster_id].append(source)
            
            # Store each cluster in statistical database
            for cluster_id, members in cluster_groups.items():
                source_count = len(members)
                
                # Calculate average similarity (placeholder - would use actual similarity matrix)
                avg_similarity = quality_metrics.get('avg_intra_cluster_similarity', 0.8)
                silhouette = quality_metrics.get('silhouette_score', 0.0)
                
                # Store cluster cache entry
                self.statistical_db.store_clustering_cache(
                    time_window_start=month_start,
                    time_window_end=month_end,
                    country=country,
                    cluster_id=cluster_id,
                    source_count=source_count,
                    intra_cluster_similarity=avg_similarity,
                    silhouette_score=silhouette
                )
            
            logger.info(f"Stored {len(cluster_groups)} clusters in statistical database for {country}")
            
        except Exception as e:
            logger.error(f"Error storing clustering results in statistical database: {e}")
            # Don't fail the main clustering process if statistical storage fails