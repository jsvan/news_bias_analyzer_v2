#!/usr/bin/env python3
"""
Statistical Analysis Orchestrator

This script coordinates all statistical and clustering analysis functions with proper throttling:
- Intelligence functions (run max once per day)
- Clustering functions (run max once per 7 days)

Each function tracks its last run time to avoid excessive computation.
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import json

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# Import statistical and clustering modules
try:
    from intelligence.sentiment_anomaly_detector import SentimentAnomalyDetector
    from intelligence.source_divergence_detector import SourceDivergenceDetector
    from intelligence.polarization_detector import PolarizationDetector
    from intelligence.clustering_insights_analyzer import ClusteringInsights
    has_intelligence = True
except ImportError as e:
    print(f"Warning: Could not import intelligence modules: {e}")
    has_intelligence = False

try:
    from clustering.cluster_manager import ClusterManager
    from clustering.temporal_analyzer import TemporalAnalyzer
    has_clustering = True
except ImportError as e:
    print(f"Warning: Could not import clustering modules: {e}")
    has_clustering = False

try:
    from statistical_database.db_manager import StatisticalDBManager
    has_statistical_db = True
except ImportError as e:
    print(f"Warning: Could not import statistical database: {e}")
    has_statistical_db = False

# Setup logging
LOG_DIR = os.path.join(ROOT_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'statistical_orchestrator.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StatisticalOrchestrator:
    """Orchestrates all statistical and clustering analysis with proper throttling."""
    
    def __init__(self, database_url: str = None):
        """
        Initialize the orchestrator.
        
        Args:
            database_url: Database connection string
        """
        self.database_url = database_url or os.getenv("DATABASE_URL", 
            "postgresql://newsbias:newsbias@localhost:5432/news_bias")
        
        # Initialize database connection
        try:
            self.engine = create_engine(self.database_url)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.session = self.SessionLocal()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
        
        # Initialize statistical database if available
        self.statistical_db = None
        if has_statistical_db:
            try:
                self.statistical_db = StatisticalDBManager()
                logger.info("Statistical database connection established")
            except Exception as e:
                logger.warning(f"Could not connect to statistical database: {e}")
        
        # Initialize analysis modules
        self.intelligence_analyzers = {}
        self.clustering_analyzers = {}
        
        if has_intelligence:
            self.intelligence_analyzers = {
                'sentiment_anomaly': SentimentAnomalyDetector(self.session),
                'source_divergence': SourceDivergenceDetector(self.session),
                'polarization': PolarizationDetector(self.session),
                'clustering_insights': ClusteringInsights(self.session)
            }
            logger.info(f"Initialized {len(self.intelligence_analyzers)} intelligence analyzers")
        
        if has_clustering:
            self.clustering_analyzers = {
                'cluster_manager': ClusterManager(self.session),
                'temporal_analyzer': TemporalAnalyzer(self.session)
            }
            logger.info(f"Initialized {len(self.clustering_analyzers)} clustering analyzers")
        
        # Throttling configuration
        self.intelligence_throttle_hours = 24  # Run intelligence functions max once per day
        self.clustering_throttle_hours = 168  # Run clustering functions max once per week (7 days)
    
    def get_last_run_time(self, analysis_type: str) -> Optional[datetime]:
        """
        Get the last run time for a specific analysis type.
        
        Args:
            analysis_type: Type of analysis (e.g., 'sentiment_anomaly', 'cluster_manager')
            
        Returns:
            Last run time or None if never run
        """
        if not self.statistical_db:
            return None
        
        try:
            result = self.statistical_db.get_analysis_state(analysis_type)
            if result and result.get('last_run_timestamp'):
                return datetime.fromisoformat(result['last_run_timestamp'])
        except Exception as e:
            logger.warning(f"Could not get last run time for {analysis_type}: {e}")
        
        return None
    
    def set_last_run_time(self, analysis_type: str, timestamp: datetime = None):
        """
        Set the last run time for a specific analysis type.
        
        Args:
            analysis_type: Type of analysis
            timestamp: Timestamp to set (defaults to now)
        """
        if not self.statistical_db:
            return
        
        timestamp = timestamp or datetime.now()
        
        try:
            self.statistical_db.store_analysis_state(
                analysis_type=analysis_type,
                last_run_timestamp=timestamp.isoformat(),
                status='completed'
            )
        except Exception as e:
            logger.warning(f"Could not set last run time for {analysis_type}: {e}")
    
    def should_run_analysis(self, analysis_type: str, throttle_hours: int) -> bool:
        """
        Check if an analysis should run based on throttling rules.
        
        Args:
            analysis_type: Type of analysis
            throttle_hours: Minimum hours between runs
            
        Returns:
            True if analysis should run
        """
        last_run = self.get_last_run_time(analysis_type)
        
        if last_run is None:
            logger.info(f"{analysis_type} has never run - will execute")
            return True
        
        time_since_last_run = datetime.now() - last_run
        time_since_hours = time_since_last_run.total_seconds() / 3600
        
        if time_since_hours >= throttle_hours:
            logger.info(f"{analysis_type} last ran {time_since_hours:.1f} hours ago - will execute")
            return True
        else:
            logger.info(f"{analysis_type} last ran {time_since_hours:.1f} hours ago - throttled for {throttle_hours - time_since_hours:.1f} more hours")
            return False
    
    def run_intelligence_analysis(self, force: bool = False) -> Dict[str, bool]:
        """
        Run all intelligence analysis functions with throttling.
        
        Args:
            force: Skip throttling and run all analyses
            
        Returns:
            Dictionary of analysis results (analysis_name -> success)
        """
        results = {}
        
        if not has_intelligence:
            logger.warning("Intelligence modules not available")
            return results
        
        logger.info("Running intelligence analysis...")
        
        for name, analyzer in self.intelligence_analyzers.items():
            try:
                if force or self.should_run_analysis(name, self.intelligence_throttle_hours):
                    logger.info(f"Running {name} analysis...")
                    start_time = time.time()
                    
                    # Run the analysis
                    if hasattr(analyzer, 'analyze'):
                        analyzer.analyze()
                    elif hasattr(analyzer, 'run_analysis'):
                        analyzer.run_analysis()
                    else:
                        logger.warning(f"No analysis method found for {name}")
                        results[name] = False
                        continue
                    
                    # Mark as completed
                    self.set_last_run_time(name)
                    
                    execution_time = time.time() - start_time
                    logger.info(f"Completed {name} analysis in {execution_time:.2f} seconds")
                    results[name] = True
                else:
                    results[name] = False  # Throttled
                    
            except Exception as e:
                logger.error(f"Error running {name} analysis: {e}")
                results[name] = False
        
        return results
    
    def run_clustering_analysis(self, force: bool = False) -> Dict[str, bool]:
        """
        Run all clustering analysis functions with throttling.
        
        Args:
            force: Skip throttling and run all analyses
            
        Returns:
            Dictionary of analysis results (analysis_name -> success)
        """
        results = {}
        
        if not has_clustering:
            logger.warning("Clustering modules not available")
            return results
        
        logger.info("Running clustering analysis...")
        
        for name, analyzer in self.clustering_analyzers.items():
            try:
                if force or self.should_run_analysis(name, self.clustering_throttle_hours):
                    logger.info(f"Running {name} analysis...")
                    start_time = time.time()
                    
                    # Run the analysis
                    if hasattr(analyzer, 'cluster_all_countries'):
                        # For cluster manager
                        analyzer.cluster_all_countries()
                    elif hasattr(analyzer, 'analyze_temporal_patterns'):
                        # For temporal analyzer
                        analyzer.analyze_temporal_patterns()
                    elif hasattr(analyzer, 'run_analysis'):
                        analyzer.run_analysis()
                    else:
                        logger.warning(f"No analysis method found for {name}")
                        results[name] = False
                        continue
                    
                    # Mark as completed
                    self.set_last_run_time(name)
                    
                    execution_time = time.time() - start_time
                    logger.info(f"Completed {name} analysis in {execution_time:.2f} seconds")
                    results[name] = True
                else:
                    results[name] = False  # Throttled
                    
            except Exception as e:
                logger.error(f"Error running {name} analysis: {e}")
                results[name] = False
        
        return results
    
    def run_all_analysis(self, force: bool = False) -> Dict[str, Dict[str, bool]]:
        """
        Run all statistical and clustering analysis.
        
        Args:
            force: Skip throttling and run all analyses
            
        Returns:
            Dictionary with intelligence and clustering results
        """
        logger.info("Starting comprehensive statistical analysis...")
        start_time = time.time()
        
        results = {
            'intelligence': self.run_intelligence_analysis(force),
            'clustering': self.run_clustering_analysis(force)
        }
        
        total_time = time.time() - start_time
        logger.info(f"Completed all statistical analysis in {total_time:.2f} seconds")
        
        # Print summary
        self.print_summary(results)
        
        return results
    
    def print_summary(self, results: Dict[str, Dict[str, bool]]):
        """Print a summary of analysis results."""
        logger.info("=" * 60)
        logger.info("STATISTICAL ANALYSIS SUMMARY")
        logger.info("=" * 60)
        
        for category, category_results in results.items():
            logger.info(f"\n{category.upper()} ANALYSIS:")
            if not category_results:
                logger.info("  No modules available")
                continue
                
            for analysis_name, success in category_results.items():
                status = "✓ EXECUTED" if success else "⏭ THROTTLED/FAILED"
                logger.info(f"  {analysis_name}: {status}")
        
        # Calculate totals
        total_executed = sum(sum(1 for success in cat_results.values() if success) 
                           for cat_results in results.values())
        total_available = sum(len(cat_results) for cat_results in results.values())
        
        logger.info(f"\nTotal: {total_executed}/{total_available} analyses executed")
        logger.info("=" * 60)
    
    def status(self) -> Dict[str, any]:
        """Get status of all analysis modules."""
        status_info = {
            'database_connected': bool(self.session),
            'statistical_db_available': bool(self.statistical_db),
            'intelligence_modules': len(self.intelligence_analyzers),
            'clustering_modules': len(self.clustering_analyzers),
            'last_run_times': {}
        }
        
        # Get last run times for all modules
        all_modules = list(self.intelligence_analyzers.keys()) + list(self.clustering_analyzers.keys())
        for module_name in all_modules:
            last_run = self.get_last_run_time(module_name)
            status_info['last_run_times'][module_name] = {
                'last_run': last_run.isoformat() if last_run else None,
                'hours_since_last_run': (datetime.now() - last_run).total_seconds() / 3600 if last_run else None
            }
        
        return status_info
    
    def __del__(self):
        """Clean up database connections."""
        if hasattr(self, 'session') and self.session:
            self.session.close()


def main():
    """Main entry point for the statistical orchestrator."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Statistical Analysis Orchestrator')
    parser.add_argument('--force', action='store_true', 
                       help='Force execution of all analyses, ignoring throttling')
    parser.add_argument('--intelligence-only', action='store_true',
                       help='Run only intelligence analyses')
    parser.add_argument('--clustering-only', action='store_true',
                       help='Run only clustering analyses')
    parser.add_argument('--status', action='store_true',
                       help='Show status of all analysis modules')
    parser.add_argument('--database-url', type=str,
                       help='Database connection URL')
    
    args = parser.parse_args()
    
    try:
        orchestrator = StatisticalOrchestrator(database_url=args.database_url)
        
        if args.status:
            status = orchestrator.status()
            print("\nSTATISTICAL ORCHESTRATOR STATUS")
            print("=" * 40)
            print(f"Database Connected: {status['database_connected']}")
            print(f"Statistical DB Available: {status['statistical_db_available']}")
            print(f"Intelligence Modules: {status['intelligence_modules']}")
            print(f"Clustering Modules: {status['clustering_modules']}")
            print("\nLast Run Times:")
            for module_name, info in status['last_run_times'].items():
                last_run = info['last_run']
                hours_since = info['hours_since_last_run']
                if last_run:
                    print(f"  {module_name}: {last_run} ({hours_since:.1f} hours ago)")
                else:
                    print(f"  {module_name}: Never run")
            return
        
        if args.intelligence_only:
            results = orchestrator.run_intelligence_analysis(force=args.force)
            print(f"\nIntelligence analysis results: {results}")
        elif args.clustering_only:
            results = orchestrator.run_clustering_analysis(force=args.force)
            print(f"\nClustering analysis results: {results}")
        else:
            results = orchestrator.run_all_analysis(force=args.force)
        
    except Exception as e:
        logger.error(f"Fatal error in statistical orchestrator: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()