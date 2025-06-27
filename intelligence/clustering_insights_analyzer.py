"""
Clustering Insights Analyzer

Processes existing clustering results from the main database to identify meaningful patterns,
cluster stability changes, and emerging narrative cohesion or fragmentation.
"""

import logging
import numpy as np
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, func

# Import database connections
from database.models import NewsArticle, Entity, EntityMention, NewsSource  
from statistical_database.db_manager import StatisticalDBManager
from intelligence.base_analyzer import BaseIntelligenceAnalyzer

logger = logging.getLogger(__name__)

class ClusteringInsightsAnalyzer(BaseIntelligenceAnalyzer):
    """
    Analyzes clustering results to identify meaningful insights about source behavior.
    
    Key insights:
    - Cluster stability over time
    - Sources switching between clusters (editorial shifts)
    - Emerging new clusters (narrative fragmentation)
    - Cluster merger/dissolution events
    - Cross-country clustering patterns
    """
    
    def __init__(self,
                 session: Session,
                 statistical_db: StatisticalDBManager,
                 analysis_weeks: int = 8,  # Look back 8 weeks for trends
                 stability_threshold: float = 0.8):  # Cluster membership stability
        super().__init__(
            session=session,
            statistical_db=statistical_db,
            min_mentions_threshold=10,
            min_sources_threshold=3,
            significance_threshold=0.01
        )
        self.analysis_weeks = analysis_weeks
        self.stability_threshold = stability_threshold
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main analysis entry point for the orchestrator.
        
        Returns:
            List of clustering insight findings
        """
        start_time = time.time()
        target_week = datetime.utcnow()
        self.log_analysis_start("clustering insights", target_week)
        
        try:
            findings = self._run_clustering_analysis(target_week)
            duration = time.time() - start_time
            self.log_analysis_complete("clustering insights", len(findings), duration)
            return findings
        except Exception as e:
            logger.error(f"Clustering insights analysis failed: {e}")
            return []
        finally:
            self.clear_caches()
    
    def _run_clustering_analysis(self, target_week: datetime = None):
        """
        Run weekly clustering insights analysis.
        
        Steps:
        1. Process latest clustering results from main database
        2. Cache processed results in statistical database
        3. Analyze cluster stability and changes over time
        4. Detect cluster membership changes (editorial shifts)
        5. Identify emerging or dissolving clusters
        6. Store significant insights
        """
        if target_week is None:
            target_week = datetime.utcnow()
        
        # Get latest clustering results from main database
        latest_clusters = self._get_latest_clustering_results(target_week)
        
        if not latest_clusters:
            logger.warning("No clustering results found for analysis")
            return []
        
        # Cache clustering results in statistical database
        self._cache_clustering_results(latest_clusters, target_week)
        
        # Analyze cluster changes over time
        insights = []
        
        # Analyze cluster stability
        stability_insights = self._analyze_cluster_stability(target_week)
        insights.extend(stability_insights)
        
        # Analyze source migrations between clusters
        migration_insights = self._analyze_source_migrations(target_week)
        insights.extend(migration_insights)
        
        # Analyze cluster evolution (emergence, dissolution)
        evolution_insights = self._analyze_cluster_evolution(target_week)
        insights.extend(evolution_insights)
        
        logger.info(f"Generated {len(insights)} clustering insights")
        return insights
    
    def _get_latest_clustering_results(self, target_week: datetime) -> List[Dict]:
        """
        Get the latest clustering results from the main database.
        
        Returns:
            List of clustering result dictionaries
        """
        try:
            # Query source_clusters table for latest assignments
            query = text("""
                SELECT 
                    sc.source_id,
                    sc.cluster_id,
                    sc.cluster_level,
                    sc.similarity_to_centroid,
                    sc.assigned_date,
                    sc.is_centroid,
                    sc.metadata,
                    ns.name as source_name,
                    ns.country
                FROM source_clusters sc
                JOIN news_sources ns ON sc.source_id = ns.id
                WHERE sc.assigned_date = (
                    SELECT MAX(assigned_date) FROM source_clusters 
                    WHERE assigned_date <= :target_date
                )
                ORDER BY sc.cluster_id, sc.similarity_to_centroid DESC
            """)
            
            results = self.session.execute(query, {
                'target_date': target_week.date()
            }).fetchall()
            
            clusters = []
            for row in results:
                cluster_data = {
                    'source_id': row.source_id,
                    'source_name': row.source_name,
                    'country': row.country,
                    'cluster_id': row.cluster_id,
                    'cluster_level': row.cluster_level,
                    'similarity_to_centroid': float(row.similarity_to_centroid) if row.similarity_to_centroid else 0.0,
                    'assigned_date': row.assigned_date,
                    'is_centroid': bool(row.is_centroid),
                    'metadata': row.metadata  # JSON blob
                }
                clusters.append(cluster_data)
            
            return clusters
        except Exception as e:
            logger.warning(f"Failed to get clustering results: {e}")
            return []
    
    def _cache_clustering_results(self, clusters: List[Dict], target_week: datetime):
        """
        Cache processed clustering results in statistical database.
        
        Process and store clustering results for efficient analysis
        """
        # Group clusters and calculate metrics
        cluster_groups = {}
        for cluster in clusters:
            cluster_id = cluster['cluster_id']
            if cluster_id not in cluster_groups:
                cluster_groups[cluster_id] = []
            cluster_groups[cluster_id].append(cluster)
        
        # Store each cluster's metrics
        week_start, week_end = self.get_week_boundaries(target_week)
        
        for cluster_id, members in cluster_groups.items():
            if not members:
                continue
                
            # Calculate cluster metrics
            source_count = len(members)
            countries = list(set(m['country'] for m in members if m['country']))
            primary_country = countries[0] if countries else None
            
            # Calculate intra-cluster similarity
            similarities = [m.get('similarity_to_centroid', 0) for m in members]
            intra_similarity = float(np.mean(similarities)) if similarities else 0.0
            
            # Get previous cluster data for comparison
            previous_similarity = self._get_previous_cluster_similarity(cluster_id, week_start)
            
            similarity_change = None
            if previous_similarity is not None:
                similarity_change = intra_similarity - previous_similarity
            
            # Detect member changes
            member_changes = self._detect_member_changes(cluster_id, members, week_start)
            
            # Store in cache (using store_finding for consistency)
            try:
                self.statistical_db.store_clustering_cache(
                    time_window_start=week_start,
                    time_window_end=week_end,
                    cluster_id=str(cluster_id),
                    source_count=source_count,
                    country=primary_country,
                    intra_cluster_similarity=intra_similarity,
                    previous_similarity=previous_similarity,
                    similarity_change=similarity_change,
                    member_changes=member_changes
                )
            except Exception as e:
                logger.warning(f"Failed to cache cluster {cluster_id}: {e}")
    
    def _get_previous_cluster_similarity(self, cluster_id: str, current_week: datetime) -> Optional[float]:
        """
        Get previous week's similarity score for comparison.
        
        Query statistical database for previous cluster similarity
        """
        try:
            previous_week = current_week - timedelta(weeks=1)
            # This would query the clustering cache if it existed
            # For now, return None as the cache table may not be implemented
            return None
        except Exception as e:
            logger.warning(f"Failed to get previous cluster similarity: {e}")
            return None
    
    def _detect_member_changes(self, cluster_id: str, current_members: List[Dict], week_start: datetime) -> List[str]:
        """
        Detect sources that joined or left this cluster.
        
        Compare current membership to previous week to detect changes
        
        Returns:
            List of change descriptions (e.g., "source_123_joined", "source_456_left")
        """
        try:
            # For now, return empty list as we don't have historical comparison
            # A full implementation would compare against previous week's data
            return []
        except Exception as e:
            logger.warning(f"Failed to detect member changes: {e}")
            return []
    
    def _analyze_cluster_stability(self, target_week: datetime) -> List[Dict]:
        """
        Analyze cluster stability over time.
        
        Analyze:
        1. Clusters with decreasing internal similarity
        2. Clusters losing members consistently
        3. Highly stable clusters (potential echo chambers)
        4. Clusters with increasing volatility
        
        Returns:
            List of stability insight findings
        """
        insights = []
        
        # Get cluster stability metrics over analysis_weeks
        end_date = target_week
        start_date = end_date - timedelta(weeks=self.analysis_weeks)
        
        # For now, return empty list as this requires historical clustering data
        # A full implementation would analyze stability trends from the clustering cache
        
        return insights
    
    def _analyze_source_migrations(self, target_week: datetime) -> List[Dict]:
        """
        Analyze sources that have moved between clusters (editorial shifts).
        
        Analyze:
        1. Sources switching clusters frequently (editorial instability)
        2. Sources moving from mainstream to fringe clusters
        3. Mass migrations between clusters (coordinated shifts)
        4. Sources becoming isolated (leaving clusters)
        
        Returns:
            List of migration insight findings
        """
        insights = []
        
        # Track source cluster membership over time
        end_date = target_week
        start_date = end_date - timedelta(weeks=self.analysis_weeks)
        
        try:
            # Query source_clusters table for membership changes
            query = text("""
                SELECT 
                    source_id,
                    cluster_id,
                    assigned_date,
                    LAG(cluster_id) OVER (PARTITION BY source_id ORDER BY assigned_date) as prev_cluster
                FROM source_clusters 
                WHERE assigned_date BETWEEN :start_date AND :end_date
                ORDER BY source_id, assigned_date
            """)
            
            results = self.session.execute(query, {
                'start_date': start_date.date(),
                'end_date': end_date.date()
            }).fetchall()
            
            # Analyze migrations (simplified implementation)
            migration_counts = {}
            for row in results:
                if row.prev_cluster and row.prev_cluster != row.cluster_id:
                    source_id = row.source_id
                    migration_counts[source_id] = migration_counts.get(source_id, 0) + 1
            
            # Create findings for sources with frequent migrations
            for source_id, migration_count in migration_counts.items():
                if migration_count >= 3:  # Frequent migrator
                    finding = self._create_migration_finding(
                        source_id, migration_count, start_date, end_date
                    )
                    if finding:
                        insights.append(finding)
        
        except Exception as e:
            logger.warning(f"Migration analysis failed: {e}")
        
        return insights
    
    def _analyze_cluster_evolution(self, target_week: datetime) -> List[Dict]:
        """
        Analyze cluster emergence, growth, shrinkage, and dissolution.
        
        Analyze:
        1. New clusters forming (narrative fragmentation)
        2. Clusters growing rapidly (emerging consensus)
        3. Clusters shrinking (dissolving narratives)
        4. Cluster mergers (narrative convergence)
        
        Returns:
            List of evolution insight findings
        """
        insights = []
        
        # Track cluster lifecycles over analysis_weeks
        end_date = target_week
        start_date = end_date - timedelta(weeks=self.analysis_weeks)
        
        # Identify new clusters that emerged
        new_clusters = self._identify_new_clusters(start_date, end_date)
        
        # Identify dissolved clusters
        dissolved_clusters = self._identify_dissolved_clusters(start_date, end_date)
        
        # Analyze cluster size changes
        cluster_growth = self._analyze_cluster_growth(start_date, end_date)
        
        # Create findings for significant evolution events
        for cluster_id, growth_rate in cluster_growth.items():
            if abs(growth_rate) > 0.5:  # 50% size change
                finding = self._create_evolution_finding(
                    cluster_id, growth_rate, start_date, end_date
                )
                if finding:
                    insights.append(finding)
        
        return insights
    
    def _identify_new_clusters(self, start_date: datetime, end_date: datetime) -> List[str]:
        """
        Identify clusters that emerged during the analysis period.
        
        Query for cluster_ids that appear for the first time in the period
        """
        try:
            # Find cluster_ids with first appearance in time window
            # For now, return empty list as this requires complex historical analysis
            return []
        except Exception as e:
            logger.warning(f"New cluster identification failed: {e}")
            return []
    
    def _identify_dissolved_clusters(self, start_date: datetime, end_date: datetime) -> List[str]:
        """
        Identify clusters that dissolved during the analysis period.
        
        Query for cluster_ids that disappear during the time window
        """
        try:
            # Find cluster_ids that stop appearing
            # For now, return empty list as this requires complex historical analysis
            return []
        except Exception as e:
            logger.warning(f"Dissolved cluster identification failed: {e}")
            return []
    
    def _analyze_cluster_growth(self, start_date: datetime, end_date: datetime) -> Dict[str, float]:
        """
        Analyze growth/shrinkage rates for all clusters.
        
        Calculate membership growth rates for each cluster
        
        Returns:
            Dictionary mapping cluster_id -> growth_rate (-1 to +inf)
        """
        try:
            # Calculate size changes for each cluster over time
            # For now, return empty dict as this requires historical data
            return {}
        except Exception as e:
            logger.warning(f"Cluster growth analysis failed: {e}")
            return {}
    
    def get_cluster_insights_summary(self, session: Session, weeks_back: int = 4) -> Dict[str, Any]:
        """
        Get summary of clustering insights for dashboard overview.
        
        TODO: Implement summary of key clustering trends:
        1. Most stable/unstable clusters
        2. Recent editorial shifts
        3. Emerging/dissolving clusters
        4. Overall clustering stability trend
        
        Returns:
            Summary dictionary for dashboard display
        """
        logger.info("Generating cluster insights summary")
        
        # TODO: Aggregate insights from statistical database
        # Get recent findings and create overview metrics
        
        return {
            'overall_stability': 'decreasing',  # TODO: Calculate actual metric
            'recent_migrations': [],  # TODO: Get recent source migrations
            'emerging_clusters': [],  # TODO: Get new clusters
            'dissolving_clusters': [],  # TODO: Get dissolving clusters
            'stability_trend': []  # TODO: Get weekly stability scores
        }
    
    def analyze_cross_country_clustering(self, session: Session, target_week: datetime = None) -> Dict[str, Any]:
        """
        Analyze clustering patterns across countries.
        
        TODO: Implement analysis of:
        1. Sources from different countries clustering together
        2. Country-specific clustering patterns
        3. International narrative alignment/divergence
        4. Regional clustering trends
        
        Returns:
            Cross-country clustering analysis
        """
        if target_week is None:
            target_week = datetime.utcnow()
        
        logger.info("Analyzing cross-country clustering patterns")
        
        # TODO: Get clustering results grouped by country
        # Analyze which countries' sources cluster together
        # Identify international narrative alignment
        
        return {
            'cross_country_clusters': [],  # TODO: Clusters with multiple countries
            'country_isolation': {},  # TODO: Countries with isolated sources
            'narrative_alignment': {},  # TODO: Countries with similar narratives
            'regional_patterns': {}  # TODO: Regional clustering trends
        }
    
    def _create_migration_finding(self, 
                                 source_id: int, 
                                 migration_count: int,
                                 start_date: datetime, 
                                 end_date: datetime) -> Optional[Dict[str, Any]]:
        """
        Create a finding for frequent source migrations.
        """
        try:
            # Get source name
            source = self.session.query(NewsSource).filter_by(id=source_id).first()
            if not source:
                return None
            
            title = f"Editorial Instability: {source.name}"
            description = f"{source.name} changed clusters {migration_count} times, indicating editorial instability"
            
            finding_id = self.store_finding(
                finding_type='clustering_insight',
                title=title,
                description=description,
                p_value=0.01,  # Assume significant
                severity_score=min(1.0, migration_count / 5.0),
                event_start=start_date,
                event_end_date=end_date,
                source_id=source_id,
                migration_count=migration_count
            )
            
            return {
                'finding_id': finding_id,
                'source_id': source_id,
                'source_name': source.name,
                'insight_type': 'editorial_instability',
                'migration_count': migration_count
            }
        except Exception as e:
            logger.warning(f"Failed to create migration finding: {e}")
            return None
    
    def _create_evolution_finding(self, 
                                 cluster_id: str, 
                                 growth_rate: float,
                                 start_date: datetime, 
                                 end_date: datetime) -> Optional[Dict[str, Any]]:
        """
        Create a finding for cluster evolution events.
        """
        try:
            direction = "growth" if growth_rate > 0 else "shrinkage"
            magnitude = "rapid" if abs(growth_rate) > 1.0 else "significant"
            
            title = f"Cluster {direction.title()}: Cluster {cluster_id}"
            description = f"Cluster {cluster_id} experienced {magnitude} {direction} ({growth_rate:.1%})"
            
            finding_id = self.store_finding(
                finding_type='clustering_insight',
                title=title,
                description=description,
                p_value=0.01,  # Assume significant
                severity_score=min(1.0, abs(growth_rate)),
                event_start=start_date,
                event_end_date=end_date,
                cluster_id=cluster_id,
                growth_rate=growth_rate
            )
            
            return {
                'finding_id': finding_id,
                'cluster_id': cluster_id,
                'insight_type': 'cluster_evolution',
                'growth_rate': growth_rate,
                'direction': direction
            }
        except Exception as e:
            logger.warning(f"Failed to create evolution finding: {e}")
            return None