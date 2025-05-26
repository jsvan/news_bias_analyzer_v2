"""
News source clustering and similarity computation module.

This module handles:
- Hierarchical clustering of news sources
- Similarity computation between sources
- Temporal drift analysis
- Entity volatility detection
"""

from .source_similarity import SourceSimilarityComputer
from .cluster_manager import ClusterManager
from .temporal_analyzer import TemporalAnalyzer
from .similarity_api import SimilarityAPI

__all__ = [
    'SourceSimilarityComputer',
    'ClusterManager', 
    'TemporalAnalyzer',
    'SimilarityAPI'
]