"""
Intelligence API Endpoints

FastAPI endpoints for accessing intelligence analysis results.
These endpoints provide dashboard-ready data for statistical findings and insights.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import sys
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent))

# Import database utilities
from database.db import get_session

from .intelligence_manager import IntelligenceManager
from .statistical_database.db_manager import StatisticalDBManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intelligence", tags=["intelligence"])

# Initialize intelligence manager
# TODO: Configure with proper database path
intelligence_manager = IntelligenceManager()

@router.get("/findings", response_model=List[Dict[str, Any]])
async def get_findings(
    category: Optional[str] = Query(None, description="Filter by category: anomaly, divergence, polarization, trending"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of findings to return"),
    min_severity: float = Query(0.0, ge=0.0, le=1.0, description="Minimum severity score")
):
    """
    Get statistical findings for dashboard display.
    
    Returns significant sentiment anomalies, source divergences, polarization events,
    and clustering insights sorted by priority and recency.
    """
    try:
        findings = intelligence_manager.get_dashboard_findings(
            category=category,
            limit=limit
        )
        
        # TODO: Filter by minimum severity if specified
        if min_severity > 0.0:
            findings = [f for f in findings if f.get('severity_score', 0) >= min_severity]
        
        return findings
        
    except Exception as e:
        logger.error(f"Error getting findings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving findings: {str(e)}")

@router.get("/status", response_model=Dict[str, Any])
async def get_analysis_status():
    """
    Get current status of the intelligence analysis system.
    
    Returns system health, last analysis time, module status, and any errors.
    """
    try:
        status = intelligence_manager.get_analysis_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting analysis status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")

@router.get("/trends", response_model=Dict[str, Any])
async def get_global_trends(
    weeks_back: int = Query(12, ge=1, le=52, description="Number of weeks to analyze")
):
    """
    Get global sentiment and polarization trends.
    
    Returns high-level metrics about global sentiment volatility, polarization,
    and source clustering stability over time.
    """
    try:
        trends = intelligence_manager.get_global_trends(weeks_back=weeks_back)
        return trends
        
    except Exception as e:
        logger.error(f"Error getting global trends: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving trends: {str(e)}")

@router.get("/entity/{entity_id}/analysis", response_model=Dict[str, Any])
async def get_entity_analysis(
    entity_id: int,
    weeks_back: int = Query(8, ge=1, le=26, description="Number of weeks to analyze"),
    session = Depends(get_session)
):
    """
    Get detailed analysis for a specific entity.
    
    Returns sentiment anomalies, polarization history, and source divergences
    related to the specified entity.
    """
    try:
        analysis = intelligence_manager.run_entity_focused_analysis(
            session=session,
            entity_id=entity_id,
            weeks_back=weeks_back
        )
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error getting entity analysis for {entity_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing entity: {str(e)}")

@router.get("/source/{source_id}/analysis", response_model=Dict[str, Any])
async def get_source_analysis(
    source_id: int,
    weeks_back: int = Query(8, ge=1, le=26, description="Number of weeks to analyze"),
    session = Depends(get_session)
):
    """
    Get detailed analysis for a specific news source.
    
    Returns editorial shifts, clustering history, and divergence patterns
    for the specified source.
    """
    try:
        analysis = intelligence_manager.run_source_focused_analysis(
            session=session,
            source_id=source_id,
            weeks_back=weeks_back
        )
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error getting source analysis for {source_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing source: {str(e)}")

@router.get("/divergences", response_model=List[Dict[str, Any]])
async def get_source_divergences(
    limit: int = Query(10, ge=1, le=50, description="Maximum number of divergences to return"),
    min_magnitude: float = Query(0.3, ge=0.0, le=1.0, description="Minimum divergence magnitude")
):
    """
    Get significant source divergences.
    
    Returns pairs of sources that historically moved together but have recently diverged,
    indicating potential editorial shifts or emerging polarization.
    """
    try:
        # TODO: Get divergences from statistical database
        divergences = intelligence_manager.statistical_db.get_significant_divergences(limit=limit)
        
        # Filter by magnitude if specified
        if min_magnitude > 0.0:
            divergences = [d for d in divergences if d.get('divergence_magnitude', 0) >= min_magnitude]
        
        return divergences
        
    except Exception as e:
        logger.error(f"Error getting source divergences: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving divergences: {str(e)}")

@router.get("/anomalies", response_model=List[Dict[str, Any]])
async def get_sentiment_anomalies(
    category: Optional[str] = Query(None, description="Filter by finding category"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of anomalies to return"),
    min_p_value: float = Query(0.01, ge=0.0, le=1.0, description="Maximum p-value for significance")
):
    """
    Get recent sentiment anomalies.
    
    Returns entities with statistically significant sentiment shifts that deviate
    from historical baselines.
    """
    try:
        findings = intelligence_manager.get_dashboard_findings(
            category='anomaly',
            limit=limit
        )
        
        # Filter by p-value significance
        findings = [f for f in findings if f.get('p_value', 1.0) <= min_p_value]
        
        return findings
        
    except Exception as e:
        logger.error(f"Error getting sentiment anomalies: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving anomalies: {str(e)}")

@router.get("/polarization", response_model=List[Dict[str, Any]])
async def get_polarization_events(
    limit: int = Query(15, ge=1, le=50, description="Maximum number of events to return"),
    min_severity: float = Query(0.5, ge=0.0, le=1.0, description="Minimum severity score")
):
    """
    Get recent polarization events.
    
    Returns entities that have become more polarized across news sources,
    indicating increasing disagreement or bimodal sentiment distributions.
    """
    try:
        findings = intelligence_manager.get_dashboard_findings(
            category='polarization',
            limit=limit
        )
        
        # Filter by severity
        findings = [f for f in findings if f.get('severity_score', 0) >= min_severity]
        
        return findings
        
    except Exception as e:
        logger.error(f"Error getting polarization events: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving polarization events: {str(e)}")

@router.get("/clustering/insights", response_model=Dict[str, Any])
async def get_clustering_insights(
    weeks_back: int = Query(4, ge=1, le=12, description="Number of weeks to analyze")
    # TODO: Add session dependency
    # session: Session = Depends(get_session)
):
    """
    Get clustering insights and source behavior patterns.
    
    Returns information about cluster stability, source migrations between clusters,
    and emerging or dissolving narrative clusters.
    """
    try:
        # TODO: Use actual database session
        session = None  # Placeholder
        
        insights = intelligence_manager.clustering_insights_analyzer.get_cluster_insights_summary(
            session=session,
            weeks_back=weeks_back
        )
        
        return insights
        
    except Exception as e:
        logger.error(f"Error getting clustering insights: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving clustering insights: {str(e)}")

@router.post("/analyze/run", response_model=Dict[str, Any])
async def run_analysis(
    target_week: Optional[datetime] = None
    # TODO: Add session dependency and authentication
    # session: Session = Depends(get_session)
):
    """
    Trigger a new intelligence analysis run.
    
    This endpoint runs the complete weekly analysis pipeline and returns
    a summary of results. Should be called weekly or when fresh analysis is needed.
    
    NOTE: This is a potentially long-running operation.
    """
    try:
        # TODO: Add authentication/authorization for this endpoint
        # Only authorized users should be able to trigger analysis
        
        # TODO: Use actual database session
        session = None  # Placeholder
        
        logger.info("Manual analysis run triggered via API")
        
        results = intelligence_manager.run_weekly_analysis(
            session=session,
            target_week=target_week
        )
        
        return {
            'status': 'completed',
            'analysis_date': results['analysis_date'].isoformat() if results['analysis_date'] else None,
            'summary': results['summary'],
            'error': results.get('error')
        }
        
    except Exception as e:
        logger.error(f"Error running analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error running analysis: {str(e)}")

@router.get("/report/weekly", response_model=Dict[str, Any])
async def get_weekly_report(
    target_week: Optional[datetime] = Query(None, description="Week to generate report for"),
    format: str = Query("json", description="Report format: json, summary")
    # TODO: Add session dependency
    # session: Session = Depends(get_session)
):
    """
    Get comprehensive weekly intelligence report.
    
    Returns executive summary, key findings, trends, and recommendations
    for the specified week.
    """
    try:
        # TODO: Use actual database session
        session = None  # Placeholder
        
        report = intelligence_manager.generate_weekly_report(
            session=session,
            target_week=target_week
        )
        
        if format == "summary":
            # Return abbreviated summary
            return {
                'report_date': report['report_date'],
                'executive_summary': report['executive_summary'],
                'key_findings_count': len(report['key_findings']),
                'trends': report['trends']
            }
        else:
            # Return full report
            return report
        
    except Exception as e:
        logger.error(f"Error generating weekly report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

# TODO: Add additional endpoints as needed:
# - GET /intelligence/entities/trending - Most trending entities
# - GET /intelligence/sources/unstable - Sources with frequent editorial shifts  
# - GET /intelligence/countries/comparison - Cross-country sentiment comparison
# - GET /intelligence/timeline/{entity_id} - Entity sentiment timeline
# - POST /intelligence/alerts/configure - Configure alert thresholds