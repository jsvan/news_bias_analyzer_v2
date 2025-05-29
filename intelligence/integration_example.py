"""
Intelligence System Integration Example

Shows how to integrate the intelligence system with the existing dashboard API.
"""

# Example of how to integrate intelligence endpoints with the main dashboard API

# In server/dashboard_api.py, add this import and router inclusion:

"""
from intelligence.api_endpoints import router as intelligence_router

# Add intelligence endpoints to the main app
app.include_router(intelligence_router)
"""

# Example of how to use the intelligence system in the dashboard:

"""
# Get trending findings for dashboard homepage
findings = intelligence_manager.get_dashboard_findings(limit=5)

# Get global trends for dashboard overview
trends = intelligence_manager.get_global_trends(weeks_back=12)

# Example findings structure:
{
    "id": 123,
    "finding_type": "sentiment_anomaly",
    "title": "China: dramatically more negative sentiment", 
    "description": "China sentiment shifted dramatically more negative (-0.8 vs baseline 0.2, p=0.0023) for 5 consecutive days",
    "entity_id": 456,
    "p_value": 0.0023,
    "severity_score": 0.85,
    "dashboard_category": "anomaly",
    "detection_date": "2025-05-27T10:30:00",
    "supporting_data": {
        "baseline_value": 0.2,
        "current_value": -0.8,
        "z_score": 3.2,
        "chart_data": {...}
    }
}
"""

# Example of scheduling weekly analysis:

"""
# In scheduler/job_scheduler.py or similar:

from intelligence.intelligence_manager import IntelligenceManager
from database.db import get_session

def run_weekly_intelligence_analysis():
    intelligence = IntelligenceManager()
    
    with get_session() as session:
        results = intelligence.run_weekly_analysis(session)
        
        # Log results
        total_findings = (
            len(results['sentiment_anomalies']) +
            len(results['source_divergences']) + 
            len(results['polarization_events']) +
            len(results['clustering_insights'])
        )
        
        print(f"Intelligence analysis complete: {total_findings} findings")
        
        # Optionally send alerts for high-severity findings
        high_severity = [
            f for f in intelligence.get_dashboard_findings()
            if f.get('severity_score', 0) > 0.8
        ]
        
        if high_severity:
            print(f"High-severity findings: {len(high_severity)}")
            # Send notifications, emails, etc.

# Schedule to run weekly
schedule.every().monday.at("02:00").do(run_weekly_intelligence_analysis)
"""

# Example dashboard component integration:

"""
// Frontend component example (React)
function IntelligenceInsights() {
    const [findings, setFindings] = useState([]);
    const [trends, setTrends] = useState({});
    
    useEffect(() => {
        // Get latest findings
        fetch('/intelligence/findings?limit=10')
            .then(res => res.json())
            .then(setFindings);
            
        // Get global trends
        fetch('/intelligence/trends?weeks_back=12')
            .then(res => res.json()) 
            .then(setTrends);
    }, []);
    
    return (
        <div className="intelligence-insights">
            <h2>Intelligence Insights</h2>
            
            <div className="global-trends">
                <h3>Global Trends</h3>
                <div>Sentiment Volatility: {trends.sentiment_volatility_trend}</div>
                <div>Polarization: {trends.polarization_trend}</div>
                <div>Source Clustering: {trends.clustering_stability}</div>
            </div>
            
            <div className="recent-findings">
                <h3>Recent Findings</h3>
                {findings.map(finding => (
                    <div key={finding.id} className="finding-card">
                        <h4>{finding.title}</h4>
                        <p>{finding.description}</p>
                        <div className="finding-meta">
                            <span>Severity: {finding.severity_score.toFixed(2)}</span>
                            <span>p-value: {finding.p_value.toFixed(4)}</span>
                            <span>{finding.dashboard_category}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
"""

# Example of using the system for specific analysis:

def example_usage():
    """Example of how to use the intelligence system for analysis."""
    from intelligence.intelligence_manager import IntelligenceManager
    from database.db import get_session
    
    intelligence = IntelligenceManager()
    
    with get_session() as session:
        # Run analysis for specific entity
        entity_analysis = intelligence.run_entity_focused_analysis(
            session=session,
            entity_id=123,  # e.g., "China"
            weeks_back=8
        )
        
        print(f"Entity analysis: {entity_analysis}")
        
        # Get source divergences
        divergences = intelligence.statistical_db.get_significant_divergences(limit=5)
        
        for div in divergences:
            print(f"Divergence: Source {div['source_id_1']} vs {div['source_id_2']}")
            print(f"  Historical correlation: {div['historical_correlation']:.2f}")
            print(f"  Recent correlation: {div['recent_correlation']:.2f}")
            print(f"  Divergence p-value: {div['divergence_p_value']:.4f}")
        
        # Get dashboard findings by category
        anomalies = intelligence.get_dashboard_findings(category='anomaly', limit=5)
        polarization = intelligence.get_dashboard_findings(category='polarization', limit=5)
        
        print(f"Recent anomalies: {len(anomalies)}")
        print(f"Recent polarization: {len(polarization)}")

if __name__ == "__main__":
    example_usage()