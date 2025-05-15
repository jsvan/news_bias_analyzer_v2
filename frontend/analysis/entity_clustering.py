"""
Entity Clustering Module for News Bias Analyzer
==============================================

This module provides models and functions for clustering entities based on 
sentiment patterns across news sources over time. It enables tracking how 
entities are grouped together in news coverage and how these relationships 
evolve over time.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN
import umap
from sqlalchemy.orm import Session

# Local imports
from database.models import NewsArticle, Entity, EntityMention, NewsSource

class EntitySimilarityMatrix:
    """
    Computes and manages similarity between entities based on sentiment patterns.
    
    This class creates a matrix of similarities between entities based on how they
    are portrayed by different news sources.
    """
    
    def __init__(self, min_mentions: int = 5):
        """
        Initialize the similarity matrix calculator.
        
        Args:
            min_mentions: Minimum number of mentions required for an entity to be included
        """
        self.min_mentions = min_mentions
        self.entities = {}  # Map entity_id to entity object
        self.entity_vectors = {}  # Map entity_id to sentiment vector
        self.similarity_matrix = None
        self.source_weights = {}  # Optional weights for different sources
    
    def _create_entity_source_matrix(self, db_session: Session, 
                                     start_date: Optional[datetime] = None,
                                     end_date: Optional[datetime] = None,
                                     entity_types: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Create a matrix of entities (rows) vs sources (columns) with sentiment values.
        
        Args:
            db_session: SQLAlchemy database session
            start_date: Optional start date for filtering mentions
            end_date: Optional end date for filtering mentions
            entity_types: Optional list of entity types to include
            
        Returns:
            DataFrame with entities as rows, sources as columns, and avg sentiment as values
        """
        # Base query to get entity mentions with filters
        query = db_session.query(
            EntityMention.entity_id,
            NewsArticle.source_id,
            EntityMention.power_score,
            EntityMention.moral_score
        ).join(
            NewsArticle, EntityMention.article_id == NewsArticle.id
        )
        
        # Apply filters if provided
        if start_date:
            query = query.filter(NewsArticle.publish_date >= start_date)
        if end_date:
            query = query.filter(NewsArticle.publish_date <= end_date)
        if entity_types:
            # Get entity IDs of the specified types
            entity_ids = db_session.query(Entity.id).filter(Entity.entity_type.in_(entity_types)).all()
            entity_ids = [id[0] for id in entity_ids]
            query = query.filter(EntityMention.entity_id.in_(entity_ids))
            
        # Execute query
        results = query.all()
        
        # Convert to dataframe
        df = pd.DataFrame(results, columns=['entity_id', 'source_id', 'power_score', 'moral_score'])
        
        # Calculate combined sentiment score (you can adjust this formula)
        df['sentiment'] = (df['power_score'] + df['moral_score']) / 2
        
        # Get entity metadata
        entity_data = db_session.query(Entity).all()
        self.entities = {entity.id: entity for entity in entity_data}
        
        # Count mentions per entity and filter out entities with too few mentions
        mention_counts = df['entity_id'].value_counts()
        valid_entities = mention_counts[mention_counts >= self.min_mentions].index.tolist()
        df = df[df['entity_id'].isin(valid_entities)]
        
        if df.empty:
            return pd.DataFrame()
        
        # Create the pivot table: entities as rows, sources as columns
        pivot_df = df.pivot_table(
            index='entity_id',
            columns='source_id',
            values='sentiment',
            aggfunc='mean'
        ).fillna(0)  # Fill missing values with 0
        
        return pivot_df
    
    def compute_similarity(self, db_session: Session,
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None,
                          entity_types: Optional[List[str]] = None,
                          method: str = 'cosine') -> np.ndarray:
        """
        Compute similarity between entities based on their sentiment vectors.
        
        Args:
            db_session: SQLAlchemy database session
            start_date: Optional start date for filtering mentions
            end_date: Optional end date for filtering mentions
            entity_types: Optional list of entity types to include
            method: Similarity method ('cosine' or 'correlation')
            
        Returns:
            Similarity matrix as numpy array
        """
        # Create entity-source matrix
        entity_source_matrix = self._create_entity_source_matrix(
            db_session, start_date, end_date, entity_types
        )
        
        if entity_source_matrix.empty:
            return np.array([])
        
        # Store entity vectors for later use
        self.entity_vectors = {
            entity_id: entity_source_matrix.loc[entity_id].values 
            for entity_id in entity_source_matrix.index
        }
        
        # Compute similarity matrix
        if method == 'cosine':
            self.similarity_matrix = cosine_similarity(entity_source_matrix.values)
        elif method == 'correlation':
            # Correlation-based similarity
            corr_matrix = np.corrcoef(entity_source_matrix.values)
            # Replace NaNs with 0
            corr_matrix = np.nan_to_num(corr_matrix)
            self.similarity_matrix = corr_matrix
        else:
            raise ValueError(f"Unknown similarity method: {method}")
        
        # Create lookup from matrix index to entity_id
        self.entity_ids = entity_source_matrix.index.tolist()
        
        return self.similarity_matrix
    
    def get_most_similar_entities(self, entity_id: int, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most similar entities to a given entity.
        
        Args:
            entity_id: ID of the entity to find similarities for
            top_n: Number of similar entities to return
            
        Returns:
            List of dicts with entity info and similarity score
        """
        if self.similarity_matrix is None:
            raise ValueError("Similarity matrix has not been computed yet")
        
        # Find the index of the entity in our matrix
        try:
            idx = self.entity_ids.index(entity_id)
        except ValueError:
            raise ValueError(f"Entity ID {entity_id} not found in similarity matrix")
        
        # Get similarities for this entity
        similarities = self.similarity_matrix[idx]
        
        # Get top N most similar entities (excluding self)
        most_similar_indices = np.argsort(similarities)[::-1][1:top_n+1]
        
        result = []
        for i in most_similar_indices:
            similar_entity_id = self.entity_ids[i]
            entity = self.entities[similar_entity_id]
            result.append({
                'id': entity.id,
                'name': entity.name,
                'type': entity.entity_type,
                'similarity': float(similarities[i])
            })
            
        return result


class EntityClusteringModel:
    """
    Model for clustering entities based on how they're viewed by news sources.
    
    This model identifies groups of entities that tend to be portrayed similarly
    in news coverage, enabling analysis of entity relationships and tracking
    how these relationships evolve over time.
    """
    
    def __init__(self, min_mentions: int = 5):
        """
        Initialize the entity clustering model.
        
        Args:
            min_mentions: Minimum number of mentions required for an entity to be included
        """
        self.min_mentions = min_mentions
        self.similarity_calculator = EntitySimilarityMatrix(min_mentions=min_mentions)
        self.cluster_labels = None
        self.embedding = None
    
    def compute_entity_clusters(self, db_session: Session,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None,
                               entity_types: Optional[List[str]] = None,
                               min_similarity: float = 0.6,
                               clustering_method: str = 'dbscan') -> Dict[str, Any]:
        """
        Identify clusters of entities that tend to be viewed similarly.
        
        Args:
            db_session: SQLAlchemy database session
            start_date: Optional start date for filtering mentions
            end_date: Optional end date for filtering mentions
            entity_types: Optional list of entity types to include
            min_similarity: Minimum similarity threshold for clustering
            clustering_method: Clustering algorithm to use ('dbscan' or 'hierarchical')
            
        Returns:
            Dictionary with cluster information
        """
        # Compute similarity matrix
        similarity_matrix = self.similarity_calculator.compute_similarity(
            db_session, start_date, end_date, entity_types
        )
        
        if similarity_matrix.size == 0:
            return {"entities": [], "clusters": [], "links": []}
        
        entity_ids = self.similarity_calculator.entity_ids
        entities = self.similarity_calculator.entities
        
        # Apply clustering algorithm
        if clustering_method == 'dbscan':
            # Convert similarity to distance (1 - similarity)
            distance_matrix = 1 - similarity_matrix
            np.fill_diagonal(distance_matrix, 0)  # Ensure zero distance to self
            
            # Apply DBSCAN clustering
            clustering = DBSCAN(
                eps=1 - min_similarity,  # Convert similarity threshold to distance
                min_samples=2,  # Minimum cluster size
                metric='precomputed'  # Use our precomputed distance matrix
            )
            self.cluster_labels = clustering.fit_predict(distance_matrix)
        else:
            raise ValueError(f"Unsupported clustering method: {clustering_method}")
        
        # Create a result dictionary with entity and cluster information
        result = {"entities": [], "clusters": [], "links": []}
        
        # Add entity information
        unique_clusters = sorted(list(set(self.cluster_labels)))
        if -1 in unique_clusters:  # DBSCAN marks outliers as -1
            unique_clusters.remove(-1)
            
        cluster_sizes = {}
        for cluster_id in unique_clusters:
            cluster_size = np.sum(self.cluster_labels == cluster_id)
            cluster_sizes[cluster_id] = cluster_size
            result["clusters"].append({
                "id": int(cluster_id),
                "size": int(cluster_size)
            })
        
        # Add entity info
        for i, entity_id in enumerate(entity_ids):
            entity = entities[entity_id]
            cluster_id = self.cluster_labels[i]
            
            result["entities"].append({
                "id": entity_id,
                "name": entity.name,
                "type": entity.entity_type,
                "cluster": int(cluster_id) if cluster_id != -1 else None
            })
        
        # Add links between entities based on similarity
        for i in range(len(entity_ids)):
            for j in range(i+1, len(entity_ids)):
                similarity = similarity_matrix[i, j]
                if similarity >= min_similarity:
                    result["links"].append({
                        "source": entity_ids[i],
                        "target": entity_ids[j],
                        "similarity": float(similarity)
                    })
        
        return result
    
    def compute_2d_embedding(self, method: str = 'umap') -> np.ndarray:
        """
        Compute a 2D embedding of entities for visualization.
        
        Args:
            method: Dimensionality reduction method ('umap' or 'tsne')
            
        Returns:
            2D coordinates for each entity
        """
        if self.similarity_calculator.similarity_matrix is None:
            raise ValueError("Similarity matrix has not been computed yet")
            
        # Get similarity matrix
        similarity_matrix = self.similarity_calculator.similarity_matrix
        
        # Apply dimensionality reduction
        if method == 'umap':
            # Distance is 1 - similarity
            distance_matrix = 1 - similarity_matrix
            np.fill_diagonal(distance_matrix, 0)
            
            # Apply UMAP
            reducer = umap.UMAP(
                n_components=2,
                metric='precomputed',
                min_dist=0.1,
                n_neighbors=min(15, max(5, similarity_matrix.shape[0] // 5))
            )
            self.embedding = reducer.fit_transform(distance_matrix)
        else:
            raise ValueError(f"Unsupported embedding method: {method}")
            
        return self.embedding
    
    def get_entity_network_data(self, min_similarity: float = 0.5) -> Dict[str, Any]:
        """
        Get entity network data for visualization.
        
        Args:
            min_similarity: Minimum similarity threshold for including links
            
        Returns:
            Dictionary with nodes and links for network visualization
        """
        if self.similarity_calculator.similarity_matrix is None:
            raise ValueError("Similarity matrix has not been computed yet")
            
        entity_ids = self.similarity_calculator.entity_ids
        entities = self.similarity_calculator.entities
        similarity_matrix = self.similarity_calculator.similarity_matrix
        
        # Compute 2D embedding if not already done
        if self.embedding is None:
            self.compute_2d_embedding()
            
        # Create result
        result = {"nodes": [], "links": []}
        
        # Add nodes (entities)
        for i, entity_id in enumerate(entity_ids):
            entity = entities[entity_id]
            cluster_id = int(self.cluster_labels[i]) if self.cluster_labels is not None and self.cluster_labels[i] != -1 else None
            
            result["nodes"].append({
                "id": entity_id,
                "name": entity.name,
                "type": entity.entity_type,
                "cluster": cluster_id,
                "x": float(self.embedding[i, 0]),
                "y": float(self.embedding[i, 1])
            })
            
        # Add links (similarities above threshold)
        for i in range(len(entity_ids)):
            for j in range(i+1, len(entity_ids)):
                similarity = similarity_matrix[i, j]
                if similarity >= min_similarity:
                    result["links"].append({
                        "source": entity_ids[i],
                        "target": entity_ids[j],
                        "similarity": float(similarity)
                    })
                    
        return result
    
    def track_entity_movement(self, db_session: Session,
                             entity_id: int,
                             start_date: datetime,
                             end_date: datetime,
                             interval_days: int = 30) -> List[Dict[str, Any]]:
        """
        Track how an entity moves between clusters over time.
        
        Args:
            db_session: SQLAlchemy database session
            entity_id: ID of the entity to track
            start_date: Start date for tracking
            end_date: End date for tracking
            interval_days: Number of days in each time interval
            
        Returns:
            List of dicts with clustering data for each time interval
        """
        # Calculate time intervals
        current_date = start_date
        intervals = []
        
        while current_date < end_date:
            interval_end = min(current_date + timedelta(days=interval_days), end_date)
            intervals.append((current_date, interval_end))
            current_date = interval_end
            
        # Get entity info
        entity = db_session.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            raise ValueError(f"Entity with ID {entity_id} not found")
            
        # Track the entity's position and cluster at each interval
        tracking_data = []
        
        for interval_start, interval_end in intervals:
            # Run clustering for this time interval
            cluster_data = self.compute_entity_clusters(
                db_session,
                start_date=interval_start,
                end_date=interval_end,
                entity_types=[entity.entity_type]
            )
            
            # Check if the entity is in the results
            entity_data = next((e for e in cluster_data["entities"] if e["id"] == entity_id), None)
            
            if entity_data:
                # Get 2D embedding
                self.compute_2d_embedding()
                
                # Find entity index in the current results
                entity_index = self.similarity_calculator.entity_ids.index(entity_id)
                
                # Add tracking data for this interval
                tracking_data.append({
                    "start_date": interval_start.isoformat(),
                    "end_date": interval_end.isoformat(),
                    "cluster": entity_data["cluster"],
                    "x": float(self.embedding[entity_index, 0]),
                    "y": float(self.embedding[entity_index, 1]),
                    "similar_entities": self.similarity_calculator.get_most_similar_entities(entity_id, top_n=5)
                })
                
        return tracking_data


class TopicClusterModel:
    """
    Model for identifying related entities that form topics.
    
    This model analyzes entity co-occurrence patterns to identify
    groups of entities that form cohesive topics in news coverage.
    """
    
    def __init__(self, min_entities: int = 3, co_occurrence_threshold: float = 0.3):
        """
        Initialize the topic cluster model.
        
        Args:
            min_entities: Minimum number of entities in a topic
            co_occurrence_threshold: Minimum co-occurrence score to consider entities related
        """
        self.min_entities = min_entities
        self.co_occurrence_threshold = co_occurrence_threshold
        
    def _compute_co_occurrence_matrix(self, db_session: Session,
                                     start_date: Optional[datetime] = None,
                                     end_date: Optional[datetime] = None) -> Tuple[np.ndarray, List[int]]:
        """
        Compute a co-occurrence matrix of entities within articles.
        
        Args:
            db_session: SQLAlchemy database session
            start_date: Optional start date for filtering articles
            end_date: Optional end date for filtering articles
            
        Returns:
            Tuple of (co-occurrence matrix, entity IDs)
        """
        # Get all articles in the time range
        article_query = db_session.query(NewsArticle.id)
        if start_date:
            article_query = article_query.filter(NewsArticle.publish_date >= start_date)
        if end_date:
            article_query = article_query.filter(NewsArticle.publish_date <= end_date)
        article_ids = [a[0] for a in article_query.all()]
        
        if not article_ids:
            return np.array([]), []
        
        # Get all entity mentions for these articles
        mentions = db_session.query(
            EntityMention.article_id, 
            EntityMention.entity_id
        ).filter(
            EntityMention.article_id.in_(article_ids)
        ).all()
        
        # Convert to dataframe
        df = pd.DataFrame(mentions, columns=['article_id', 'entity_id'])
        
        # Count occurrences of each entity
        entity_counts = df['entity_id'].value_counts()
        
        # Filter out entities with too few mentions
        min_mentions = 3  # Minimum to establish meaningful co-occurrence
        frequent_entities = entity_counts[entity_counts >= min_mentions].index.tolist()
        df = df[df['entity_id'].isin(frequent_entities)]
        
        if df.empty:
            return np.array([]), []
        
        # Create entity-article matrix (1 if entity appears in article, 0 otherwise)
        entity_article_matrix = pd.crosstab(
            df['entity_id'],
            df['article_id']
        )
        
        # Calculate co-occurrence matrix
        co_occurrence = entity_article_matrix.dot(entity_article_matrix.T)
        
        # Convert to numpy array
        entity_ids = co_occurrence.index.tolist()
        co_occurrence_matrix = co_occurrence.values
        
        # Normalize by the minimum of individual occurrences
        for i in range(len(entity_ids)):
            for j in range(len(entity_ids)):
                if i != j:
                    min_occurrences = min(co_occurrence_matrix[i, i], co_occurrence_matrix[j, j])
                    if min_occurrences > 0:
                        co_occurrence_matrix[i, j] /= min_occurrences
        
        # Set diagonal to 1
        np.fill_diagonal(co_occurrence_matrix, 1.0)
        
        return co_occurrence_matrix, entity_ids
    
    def identify_topics(self, db_session: Session,
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Identify topics based on entity co-occurrence patterns.
        
        Args:
            db_session: SQLAlchemy database session
            start_date: Optional start date for filtering articles
            end_date: Optional end date for filtering articles
            
        Returns:
            List of topic dictionaries with their constituent entities
        """
        # Compute co-occurrence matrix
        co_occurrence_matrix, entity_ids = self._compute_co_occurrence_matrix(
            db_session, start_date, end_date
        )
        
        if len(entity_ids) == 0:
            return []
        
        # Apply clustering to co-occurrence matrix
        # Using DBSCAN for density-based clustering
        clustering = DBSCAN(
            eps=1 - self.co_occurrence_threshold,  # Convert threshold to distance
            min_samples=self.min_entities,
            metric='precomputed'
        )
        
        # Convert co-occurrence to distance (1 - co_occurrence)
        distance_matrix = 1 - co_occurrence_matrix
        np.fill_diagonal(distance_matrix, 0)  # Ensure zero distance to self
        
        cluster_labels = clustering.fit_predict(distance_matrix)
        
        # Get entity information
        entity_info = db_session.query(Entity).filter(Entity.id.in_(entity_ids)).all()
        entity_dict = {entity.id: entity for entity in entity_info}
        
        # Organize results by topic
        topics = []
        unique_clusters = sorted(list(set(cluster_labels)))
        if -1 in unique_clusters:  # DBSCAN marks outliers as -1
            unique_clusters.remove(-1)
            
        for cluster_id in unique_clusters:
            # Get entities in this cluster
            cluster_entity_indices = np.where(cluster_labels == cluster_id)[0]
            cluster_entity_ids = [entity_ids[i] for i in cluster_entity_indices]
            
            # Calculate topic coherence (average co-occurrence between entities)
            topic_coherence = 0.0
            count = 0
            for i in range(len(cluster_entity_indices)):
                for j in range(i+1, len(cluster_entity_indices)):
                    idx1 = cluster_entity_indices[i]
                    idx2 = cluster_entity_indices[j]
                    topic_coherence += co_occurrence_matrix[idx1, idx2]
                    count += 1
                    
            if count > 0:
                topic_coherence /= count
            
            # Get entity details
            topic_entities = []
            for entity_id in cluster_entity_ids:
                entity = entity_dict.get(entity_id)
                if entity:
                    topic_entities.append({
                        "id": entity.id,
                        "name": entity.name,
                        "type": entity.entity_type
                    })
            
            # Derive a topic name (can be improved with NLP)
            person_entities = [e for e in topic_entities if e["type"] == "person"]
            org_entities = [e for e in topic_entities if e["type"] == "organization"]
            country_entities = [e for e in topic_entities if e["type"] == "country"]
            
            if person_entities:
                topic_key_entities = person_entities[:2]
            elif org_entities:
                topic_key_entities = org_entities[:2]
            elif country_entities:
                topic_key_entities = country_entities[:2]
            else:
                topic_key_entities = topic_entities[:2]
                
            topic_name = " & ".join([e["name"] for e in topic_key_entities])
            
            # Add topic to results
            topics.append({
                "id": int(cluster_id),
                "name": topic_name,
                "coherence": float(topic_coherence),
                "entities": topic_entities
            })
            
        return topics