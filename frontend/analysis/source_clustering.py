"""
Source Clustering Module for News Bias Analyzer
==============================================

This module provides models and functions for clustering news sources based on 
their sentiment patterns across entities. It enables analyzing how news sources
relate to each other in their coverage and identifying media bias patterns.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans, DBSCAN
import umap
from sqlalchemy.orm import Session

# Local imports
from database.models import NewsArticle, Entity, EntityMention, NewsSource

class SourceClusteringModel:
    """
    Model for clustering news sources by sentiment patterns.
    
    This model analyzes how different news sources portray entities and
    identifies clusters of sources with similar sentiment patterns, which
    can reveal political leanings and bias patterns.
    """
    
    def __init__(self, min_entities: int = 10):
        """
        Initialize the source clustering model.
        
        Args:
            min_entities: Minimum number of entities a source must cover to be included
        """
        self.min_entities = min_entities
        self.source_vectors = {}  # Map source_id to sentiment vector
        self.sources = {}  # Map source_id to source object
        self.entity_columns = []  # Entity IDs used as columns in the source-entity matrix
        self.similarity_matrix = None
        self.cluster_labels = None
        self.embedding = None
    
    def compute_source_vectors(self, db_session: Session,
                             start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None,
                             entity_types: Optional[List[str]] = None) -> Dict[int, np.ndarray]:
        """
        Compute vector representations for each source based on sentiment patterns.
        
        Args:
            db_session: SQLAlchemy database session
            start_date: Optional start date for filtering mentions
            end_date: Optional end date for filtering mentions
            entity_types: Optional list of entity types to include
            
        Returns:
            Dictionary mapping source IDs to their sentiment vectors
        """
        # Base query to get entity mentions with filters
        query = db_session.query(
            EntityMention.entity_id,
            NewsArticle.source_id,
            EntityMention.power_score,
            EntityMention.moral_score,
            Entity.entity_type
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        ).join(
            Entity, EntityMention.entity_id == Entity.id
        )
        
        # Apply filters if provided
        if start_date:
            query = query.filter(NewsArticle.publish_date >= start_date)
        if end_date:
            query = query.filter(NewsArticle.publish_date <= end_date)
        if entity_types:
            query = query.filter(Entity.entity_type.in_(entity_types))
            
        # Execute query
        results = query.all()
        
        # Convert to dataframe
        df = pd.DataFrame(results, columns=['entity_id', 'source_id', 'power_score', 'moral_score', 'entity_type'])
        
        # Calculate combined sentiment score (you can adjust this formula)
        df['sentiment'] = (df['power_score'] + df['moral_score']) / 2
        
        # Get source metadata
        source_data = db_session.query(NewsSource).all()
        self.sources = {source.id: source for source in source_data}
        
        # Find entities that are covered by multiple sources
        entity_counts = df.groupby('entity_id')['source_id'].nunique()
        common_entities = entity_counts[entity_counts >= 3].index.tolist()  # Entities covered by at least 3 sources
        
        if not common_entities:
            return {}
            
        # Filter to keep only common entities
        df = df[df['entity_id'].isin(common_entities)]
        
        # Count entities per source and filter out sources with too few entities
        source_entity_counts = df.groupby('source_id')['entity_id'].nunique()
        valid_sources = source_entity_counts[source_entity_counts >= self.min_entities].index.tolist()
        df = df[df['source_id'].isin(valid_sources)]
        
        if df.empty:
            return {}
        
        # Create the pivot table: sources as rows, entities as columns
        pivot_df = df.pivot_table(
            index='source_id',
            columns='entity_id',
            values='sentiment',
            aggfunc='mean'
        ).fillna(0)  # Fill missing values with 0
        
        # Store entity columns for reference
        self.entity_columns = pivot_df.columns.tolist()
        
        # Convert to dictionary of source vectors
        self.source_vectors = {
            source_id: pivot_df.loc[source_id].values 
            for source_id in pivot_df.index
        }
        
        return self.source_vectors
    
    def compute_source_similarity(self, method: str = 'cosine') -> np.ndarray:
        """
        Compute similarity between sources based on their sentiment vectors.
        
        Args:
            method: Similarity method ('cosine' or 'correlation')
            
        Returns:
            Similarity matrix as numpy array
        """
        if not self.source_vectors:
            raise ValueError("Source vectors have not been computed yet")
            
        # Create a matrix of source vectors
        source_ids = list(self.source_vectors.keys())
        source_matrix = np.vstack([self.source_vectors[sid] for sid in source_ids])
        
        # Compute similarity matrix
        if method == 'cosine':
            self.similarity_matrix = cosine_similarity(source_matrix)
        elif method == 'correlation':
            # Correlation-based similarity
            corr_matrix = np.corrcoef(source_matrix)
            # Replace NaNs with 0
            corr_matrix = np.nan_to_num(corr_matrix)
            self.similarity_matrix = corr_matrix
        else:
            raise ValueError(f"Unknown similarity method: {method}")
        
        # Store source IDs for reference
        self.source_ids = source_ids
        
        return self.similarity_matrix
    
    def cluster_sources(self, n_clusters: Optional[int] = None, min_similarity: float = 0.6) -> List[int]:
        """
        Identify clusters of news sources with similar sentiment patterns.
        
        Args:
            n_clusters: Number of clusters for K-means (if None, use DBSCAN)
            min_similarity: Minimum similarity threshold for DBSCAN clustering
            
        Returns:
            Cluster labels for each source
        """
        if self.similarity_matrix is None:
            raise ValueError("Similarity matrix has not been computed yet")
            
        if n_clusters is not None:
            # Use K-means clustering
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            # Convert similarity to distance
            distance_matrix = 1 - self.similarity_matrix
            np.fill_diagonal(distance_matrix, 0)  # Ensure zero distance to self
            self.cluster_labels = kmeans.fit_predict(distance_matrix)
        else:
            # Use DBSCAN for density-based clustering
            # Convert similarity to distance
            distance_matrix = 1 - self.similarity_matrix
            np.fill_diagonal(distance_matrix, 0)  # Ensure zero distance to self
            
            clustering = DBSCAN(
                eps=1 - min_similarity,  # Convert similarity threshold to distance
                min_samples=2,  # Minimum cluster size
                metric='precomputed'  # Use our precomputed distance matrix
            )
            self.cluster_labels = clustering.fit_predict(distance_matrix)
            
        return self.cluster_labels
    
    def reduce_dimensions(self, method: str = 'umap', n_dimensions: int = 2) -> np.ndarray:
        """
        Reduce source vectors to 2D for visualization.
        
        Args:
            method: Dimensionality reduction method ('umap')
            n_dimensions: Number of dimensions in the output
            
        Returns:
            Reduced-dimensional coordinates for each source
        """
        if not self.source_vectors:
            raise ValueError("Source vectors have not been computed yet")
            
        # Create a matrix of source vectors
        source_ids = list(self.source_vectors.keys())
        source_matrix = np.vstack([self.source_vectors[sid] for sid in source_ids])
        
        # Apply dimensionality reduction
        if method == 'umap':
            reducer = umap.UMAP(
                n_components=n_dimensions,
                metric='cosine',
                min_dist=0.1,
                n_neighbors=min(15, max(5, len(source_ids) // 2))
            )
            self.embedding = reducer.fit_transform(source_matrix)
        else:
            raise ValueError(f"Unsupported embedding method: {method}")
            
        return self.embedding
    
    def get_source_positions(self) -> Dict[int, Tuple[float, float]]:
        """
        Get the 2D positions of sources after dimensionality reduction.
        
        Returns:
            Dictionary mapping source IDs to their (x, y) coordinates
        """
        if self.embedding is None or len(self.source_ids) != self.embedding.shape[0]:
            raise ValueError("Embedding has not been computed yet")
            
        return {
            self.source_ids[i]: (float(self.embedding[i, 0]), float(self.embedding[i, 1]))
            for i in range(len(self.source_ids))
        }
    
    def get_source_clusters(self) -> Dict[int, int]:
        """
        Get the cluster assignment for each source.
        
        Returns:
            Dictionary mapping source IDs to their cluster IDs
        """
        if self.cluster_labels is None or len(self.source_ids) != len(self.cluster_labels):
            raise ValueError("Clustering has not been performed yet")
            
        return {
            self.source_ids[i]: int(self.cluster_labels[i])
            for i in range(len(self.source_ids))
        }
    
    def get_clustering_result(self) -> Dict[str, Any]:
        """
        Get a comprehensive result of the source clustering analysis.
        
        Returns:
            Dictionary with sources, clusters, and visualization data
        """
        if self.embedding is None or self.cluster_labels is None:
            raise ValueError("Both embedding and clustering must be computed first")
            
        # Prepare source data with positions and clusters
        source_points = []
        for i, source_id in enumerate(self.source_ids):
            source = self.sources[source_id]
            source_points.append({
                "id": source_id,
                "name": source.name,
                "country": source.country,
                "x": float(self.embedding[i, 0]),
                "y": float(self.embedding[i, 1]),
                "cluster": int(self.cluster_labels[i]) if self.cluster_labels[i] != -1 else None
            })
            
        # Get cluster information
        clusters = []
        unique_clusters = sorted(list(set(self.cluster_labels)))
        if -1 in unique_clusters:  # DBSCAN marks outliers as -1
            unique_clusters.remove(-1)
            
        for cluster_id in unique_clusters:
            # Sources in this cluster
            cluster_sources = [
                self.source_ids[i] for i in range(len(self.source_ids)) 
                if self.cluster_labels[i] == cluster_id
            ]
            
            # Calculate cluster centroid
            cluster_indices = [i for i in range(len(self.source_ids)) if self.cluster_labels[i] == cluster_id]
            centroid = np.mean(self.embedding[cluster_indices], axis=0)
            
            # Get most distinctive entities for this cluster
            if cluster_sources:
                cluster_source_vectors = np.vstack([self.source_vectors[sid] for sid in cluster_sources])
                cluster_avg_vector = np.mean(cluster_source_vectors, axis=0)
                
                # Compare to overall average
                all_source_vectors = np.vstack(list(self.source_vectors.values()))
                overall_avg_vector = np.mean(all_source_vectors, axis=0)
                
                # Calculate difference
                vector_diff = cluster_avg_vector - overall_avg_vector
                
                # Get top 5 most distinctive entities (positive)
                positive_entities = []
                negative_entities = []
                
                if self.entity_columns:
                    top_pos_indices = np.argsort(vector_diff)[-5:][::-1]
                    for idx in top_pos_indices:
                        if vector_diff[idx] > 0:
                            positive_entities.append({
                                "id": self.entity_columns[idx],
                                "score": float(vector_diff[idx])
                            })
                    
                    # Get top 5 most distinctive entities (negative)
                    top_neg_indices = np.argsort(vector_diff)[:5]
                    for idx in top_neg_indices:
                        if vector_diff[idx] < 0:
                            negative_entities.append({
                                "id": self.entity_columns[idx],
                                "score": float(vector_diff[idx])
                            })
            
            clusters.append({
                "id": int(cluster_id),
                "size": len(cluster_sources),
                "sources": [self.sources[sid].name for sid in cluster_sources],
                "centroid": [float(centroid[0]), float(centroid[1])],
                "positive_entities": positive_entities,
                "negative_entities": negative_entities
            })
            
        return {
            "sources": source_points,
            "clusters": clusters
        }
    
    def analyze_source_bias(self, source_id: int) -> Dict[str, Any]:
        """
        Analyze the bias pattern of a specific news source.
        
        Args:
            source_id: ID of the news source to analyze
            
        Returns:
            Dictionary with bias analysis information
        """
        if source_id not in self.source_vectors:
            raise ValueError(f"Source ID {source_id} not found in source vectors")
            
        # Get source info
        source = self.sources[source_id]
        
        # Find source index in our data
        source_idx = self.source_ids.index(source_id)
        
        # Get cluster information
        cluster_id = int(self.cluster_labels[source_idx]) if self.cluster_labels is not None else None
        cluster_sources = []
        
        if cluster_id is not None and cluster_id != -1:
            cluster_sources = [
                self.source_ids[i] for i in range(len(self.source_ids))
                if self.cluster_labels[i] == cluster_id and self.source_ids[i] != source_id
            ]
        
        # Find most similar sources
        similar_sources = []
        if self.similarity_matrix is not None:
            # Get similarities for this source
            similarities = self.similarity_matrix[source_idx]
            
            # Get top 5 most similar sources (excluding self)
            most_similar_indices = np.argsort(similarities)[::-1][1:6]
            
            for i in most_similar_indices:
                similar_source_id = self.source_ids[i]
                similar_source = self.sources[similar_source_id]
                similar_sources.append({
                    "id": similar_source_id,
                    "name": similar_source.name,
                    "country": similar_source.country,
                    "similarity": float(similarities[i])
                })
        
        # Find distinctive entity sentiments (compared to overall average)
        distinctive_entities = []
        
        if self.entity_columns:
            # Get source vector
            source_vector = self.source_vectors[source_id]
            
            # Get overall average vector
            all_source_vectors = np.vstack(list(self.source_vectors.values()))
            overall_avg_vector = np.mean(all_source_vectors, axis=0)
            
            # Calculate difference
            vector_diff = source_vector - overall_avg_vector
            
            # Get top distinctive entities (both positive and negative)
            top_indices = np.argsort(np.abs(vector_diff))[-10:][::-1]
            
            for idx in top_indices:
                entity_id = self.entity_columns[idx]
                entity = db_session.query(Entity).get(entity_id)
                
                if entity:
                    distinctive_entities.append({
                        "id": entity_id,
                        "name": entity.name,
                        "type": entity.entity_type,
                        "sentiment_diff": float(vector_diff[idx]),
                        "source_sentiment": float(source_vector[idx]),
                        "avg_sentiment": float(overall_avg_vector[idx])
                    })
        
        return {
            "source": {
                "id": source_id,
                "name": source.name,
                "country": source.country
            },
            "cluster_id": cluster_id,
            "cluster_sources": [self.sources[sid].name for sid in cluster_sources],
            "similar_sources": similar_sources,
            "distinctive_entities": distinctive_entities
        }


class SourceSentimentTrends:
    """
    Analyzes how news source sentiment patterns evolve over time.
    
    This class tracks how sources change their sentiment toward entities
    over time, enabling the detection of shifts in editorial stance
    and political leanings.
    """
    
    def __init__(self, time_window_days: int = 30):
        """
        Initialize the source sentiment trends analyzer.
        
        Args:
            time_window_days: Size of the time window in days
        """
        self.time_window_days = time_window_days
        
    def track_source_evolution(self, db_session: Session,
                             source_id: int,
                             start_date: datetime,
                             end_date: datetime) -> List[Dict[str, Any]]:
        """
        Track how a source's sentiment patterns evolve over time.
        
        Args:
            db_session: SQLAlchemy database session
            source_id: ID of the source to track
            start_date: Start date for tracking
            end_date: End date for tracking
            
        Returns:
            List of sentiment data points over time
        """
        # Get source info
        source = db_session.query(NewsSource).get(source_id)
        if not source:
            raise ValueError(f"Source with ID {source_id} not found")
            
        # Calculate time intervals
        current_date = start_date
        intervals = []
        
        while current_date < end_date:
            interval_end = min(current_date + timedelta(days=self.time_window_days), end_date)
            intervals.append((current_date, interval_end))
            current_date = interval_end
            
        # Track sentiment over time
        tracking_data = []
        
        for interval_start, interval_end in intervals:
            # Get entity mentions for this source in this time interval
            mentions = db_session.query(
                EntityMention.entity_id,
                EntityMention.power_score,
                EntityMention.moral_score,
                Entity.name,
                Entity.entity_type
            ).join(
                NewsArticle, EntityMention.article_id == NewsArticle.id
            ).join(
                Entity, EntityMention.entity_id == Entity.id
            ).filter(
                NewsArticle.source_id == source_id,
                NewsArticle.publish_date >= interval_start,
                NewsArticle.publish_date <= interval_end
            ).all()
            
            if not mentions:
                continue
                
            # Calculate average sentiment for each entity
            entity_sentiments = {}
            for entity_id, power_score, moral_score, name, entity_type in mentions:
                sentiment = (power_score + moral_score) / 2
                
                if entity_id not in entity_sentiments:
                    entity_sentiments[entity_id] = {
                        "id": entity_id,
                        "name": name,
                        "type": entity_type,
                        "sentiments": []
                    }
                    
                entity_sentiments[entity_id]["sentiments"].append(sentiment)
            
            # Calculate averages
            for entity_id, data in entity_sentiments.items():
                if data["sentiments"]:
                    data["avg_sentiment"] = sum(data["sentiments"]) / len(data["sentiments"])
                    data["count"] = len(data["sentiments"])
                    del data["sentiments"]
                    
            # Add tracking data for this interval
            tracking_data.append({
                "start_date": interval_start.isoformat(),
                "end_date": interval_end.isoformat(),
                "entity_sentiments": list(entity_sentiments.values())
            })
            
        return tracking_data
    
    def compare_sources_over_time(self, db_session: Session,
                                source_ids: List[int],
                                entity_id: int,
                                start_date: datetime,
                                end_date: datetime) -> Dict[str, Any]:
        """
        Compare how different sources cover the same entity over time.
        
        Args:
            db_session: SQLAlchemy database session
            source_ids: List of source IDs to compare
            entity_id: ID of the entity to analyze
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            Dictionary with comparison data
        """
        # Get entity info
        entity = db_session.query(Entity).get(entity_id)
        if not entity:
            raise ValueError(f"Entity with ID {entity_id} not found")
            
        # Get source info
        sources = db_session.query(NewsSource).filter(NewsSource.id.in_(source_ids)).all()
        source_dict = {source.id: source for source in sources}
        
        # Calculate time intervals
        current_date = start_date
        intervals = []
        
        while current_date < end_date:
            interval_end = min(current_date + timedelta(days=self.time_window_days), end_date)
            intervals.append((current_date, interval_end))
            current_date = interval_end
            
        # Track sentiment by source over time
        source_data = {source_id: [] for source_id in source_ids}
        
        for interval_start, interval_end in intervals:
            # For each source, get entity mentions
            for source_id in source_ids:
                mentions = db_session.query(
                    EntityMention.power_score,
                    EntityMention.moral_score
                ).join(
                    NewsArticle, EntityMention.article_id == NewsArticle.id
                ).filter(
                    NewsArticle.source_id == source_id,
                    EntityMention.entity_id == entity_id,
                    NewsArticle.publish_date >= interval_start,
                    NewsArticle.publish_date <= interval_end
                ).all()
                
                if mentions:
                    # Calculate average sentiment
                    power_scores = [m[0] for m in mentions]
                    moral_scores = [m[1] for m in mentions]
                    
                    avg_power = sum(power_scores) / len(power_scores)
                    avg_moral = sum(moral_scores) / len(moral_scores)
                    
                    source_data[source_id].append({
                        "date": interval_start.isoformat(),
                        "power_score": float(avg_power),
                        "moral_score": float(avg_moral),
                        "combined_score": float((avg_power + avg_moral) / 2),
                        "mention_count": len(mentions)
                    })
        
        # Format result
        result = {
            "entity": {
                "id": entity_id,
                "name": entity.name,
                "type": entity.entity_type
            },
            "sources": [],
            "time_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "window_days": self.time_window_days
            }
        }
        
        for source_id, data_points in source_data.items():
            source = source_dict.get(source_id)
            if source and data_points:
                result["sources"].append({
                    "id": source_id,
                    "name": source.name,
                    "country": source.country,
                    "data": data_points
                })
                
        return result