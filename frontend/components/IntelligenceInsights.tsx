import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardHeader,
  Grid,
  Chip,
  Button,
  Tab,
  Tabs,
  Alert,
  Tooltip,
  CircularProgress,
  IconButton,
  Collapse,
  Divider
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Warning,
  Info,
  ExpandMore,
  ExpandLess,
  Timeline,
  CompareArrows,
  Grain
} from '@mui/icons-material';

interface IntelligenceFinding {
  id: number;
  finding_type: string;
  title: string;
  description: string;
  entity_id?: number;
  source_id?: number;
  source_id_2?: number;
  p_value: number;
  severity_score: number;
  dashboard_category: string;
  detection_date: string;
  baseline_value: number;
  current_value: number;
  change_magnitude?: number;
  consecutive_days?: number;
  supporting_data?: any;
}

interface GlobalTrends {
  sentiment_volatility_trend: string;
  polarization_trend: string;
  clustering_stability: string;
  cross_country_divergence: string;
  weekly_metrics: any[];
}

const IntelligenceInsights: React.FC = () => {
  const [findings, setFindings] = useState<IntelligenceFinding[]>([]);
  const [trends, setTrends] = useState<GlobalTrends | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState(0);
  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set());

  useEffect(() => {
    loadIntelligenceData();
  }, []);

  const loadIntelligenceData = async () => {
    try {
      setLoading(true);
      
      // Load findings and trends in parallel
      const [findingsResponse, trendsResponse] = await Promise.all([
        fetch('/intelligence/findings?limit=20'),
        fetch('/intelligence/trends?weeks_back=12')
      ]);

      if (!findingsResponse.ok || !trendsResponse.ok) {
        throw new Error('Failed to load intelligence data');
      }

      const findingsData = await findingsResponse.json();
      const trendsData = await trendsResponse.json();

      setFindings(findingsData);
      setTrends(trendsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const toggleCardExpansion = (findingId: number) => {
    const newExpanded = new Set(expandedCards);
    if (newExpanded.has(findingId)) {
      newExpanded.delete(findingId);
    } else {
      newExpanded.add(findingId);
    }
    setExpandedCards(newExpanded);
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'anomaly': return <Warning color="warning" />;
      case 'divergence': return <CompareArrows color="info" />;
      case 'polarization': return <Grain color="error" />;
      case 'trending': return <TrendingUp color="success" />;
      default: return <Info />;
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'anomaly': return 'warning';
      case 'divergence': return 'info';
      case 'polarization': return 'error';
      case 'trending': return 'success';
      default: return 'default';
    }
  };

  const formatPValue = (pValue: number) => {
    if (pValue < 0.001) return 'p < 0.001';
    if (pValue < 0.01) return `p < 0.01`;
    return `p = ${pValue.toFixed(3)}`;
  };

  const formatTrendValue = (trend: string) => {
    const color = trend === 'increasing' ? 'error' : 
                  trend === 'decreasing' ? 'success' : 'warning';
    return <Chip label={trend} color={color} size="small" />;
  };

  const filterFindings = (category?: string) => {
    if (!category) return findings;
    return findings.filter(f => f.dashboard_category === category);
  };

  const getTabFindings = () => {
    switch (selectedTab) {
      case 0: return findings; // All
      case 1: return filterFindings('anomaly');
      case 2: return filterFindings('divergence');
      case 3: return filterFindings('polarization');
      default: return findings;
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" action={
        <Button color="inherit" size="small" onClick={loadIntelligenceData}>
          Retry
        </Button>
      }>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Intelligence Insights
      </Typography>
      <Typography variant="body1" color="textSecondary" paragraph>
        Statistical analysis of global news sentiment patterns, detecting meaningful anomalies 
        and editorial shifts with p &lt; 0.01 significance.
      </Typography>

      {/* Global Trends Summary */}
      {trends && (
        <Card sx={{ mb: 3 }}>
          <CardHeader title="Global Trends" />
          <CardContent>
            <Grid container spacing={3}>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign="center">
                  <Typography variant="body2" color="textSecondary">
                    Sentiment Volatility
                  </Typography>
                  {formatTrendValue(trends.sentiment_volatility_trend)}
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign="center">
                  <Typography variant="body2" color="textSecondary">
                    Polarization
                  </Typography>
                  {formatTrendValue(trends.polarization_trend)}
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign="center">
                  <Typography variant="body2" color="textSecondary">
                    Clustering Stability
                  </Typography>
                  {formatTrendValue(trends.clustering_stability)}
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign="center">
                  <Typography variant="body2" color="textSecondary">
                    Cross-Country Divergence
                  </Typography>
                  {formatTrendValue(trends.cross_country_divergence)}
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Findings Tabs */}
      <Card>
        <CardHeader 
          title="Statistical Findings"
          action={
            <Button
              startIcon={<Timeline />}
              onClick={loadIntelligenceData}
              size="small"
            >
              Refresh
            </Button>
          }
        />
        <Tabs
          value={selectedTab}
          onChange={(_, value) => setSelectedTab(value)}
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label={`All (${findings.length})`} />
          <Tab label={`Anomalies (${filterFindings('anomaly').length})`} />
          <Tab label={`Divergences (${filterFindings('divergence').length})`} />
          <Tab label={`Polarization (${filterFindings('polarization').length})`} />
        </Tabs>

        <CardContent>
          {getTabFindings().length === 0 ? (
            <Alert severity="info">
              No {selectedTab === 0 ? '' : 'significant '}findings detected in the current analysis period.
            </Alert>
          ) : (
            <Grid container spacing={2}>
              {getTabFindings().map((finding) => (
                <Grid item xs={12} key={finding.id}>
                  <Card variant="outlined">
                    <CardContent>
                      <Box display="flex" alignItems="flex-start" justifyContent="space-between">
                        <Box display="flex" alignItems="center" gap={1} flex={1}>
                          {getCategoryIcon(finding.dashboard_category)}
                          <Box>
                            <Typography variant="h6" component="div">
                              {finding.title}
                            </Typography>
                            <Typography variant="body2" color="textSecondary">
                              {finding.description}
                            </Typography>
                          </Box>
                        </Box>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Chip
                            label={finding.dashboard_category}
                            color={getCategoryColor(finding.dashboard_category)}
                            size="small"
                          />
                          <IconButton
                            size="small"
                            onClick={() => toggleCardExpansion(finding.id)}
                          >
                            {expandedCards.has(finding.id) ? <ExpandLess /> : <ExpandMore />}
                          </IconButton>
                        </Box>
                      </Box>

                      <Collapse in={expandedCards.has(finding.id)}>
                        <Divider sx={{ my: 2 }} />
                        <Grid container spacing={2}>
                          <Grid item xs={12} sm={6} md={3}>
                            <Typography variant="body2" color="textSecondary">
                              Statistical Significance
                            </Typography>
                            <Typography variant="body1">
                              {formatPValue(finding.p_value)}
                            </Typography>
                          </Grid>
                          <Grid item xs={12} sm={6} md={3}>
                            <Typography variant="body2" color="textSecondary">
                              Severity Score
                            </Typography>
                            <Typography variant="body1">
                              {(finding.severity_score * 100).toFixed(0)}%
                            </Typography>
                          </Grid>
                          <Grid item xs={12} sm={6} md={3}>
                            <Typography variant="body2" color="textSecondary">
                              Baseline Value
                            </Typography>
                            <Typography variant="body1">
                              {finding.baseline_value.toFixed(2)}
                            </Typography>
                          </Grid>
                          <Grid item xs={12} sm={6} md={3}>
                            <Typography variant="body2" color="textSecondary">
                              Current Value
                            </Typography>
                            <Typography variant="body1">
                              {finding.current_value.toFixed(2)}
                              {finding.change_magnitude && (
                                <Typography
                                  component="span"
                                  color={finding.change_magnitude > 0 ? 'success.main' : 'error.main'}
                                  sx={{ ml: 1 }}
                                >
                                  ({finding.change_magnitude > 0 ? '+' : ''}
                                  {finding.change_magnitude.toFixed(2)})
                                </Typography>
                              )}
                            </Typography>
                          </Grid>
                          {finding.consecutive_days && (
                            <Grid item xs={12} sm={6} md={3}>
                              <Typography variant="body2" color="textSecondary">
                                Duration
                              </Typography>
                              <Typography variant="body1">
                                {finding.consecutive_days} consecutive days
                              </Typography>
                            </Grid>
                          )}
                          <Grid item xs={12} sm={6} md={3}>
                            <Typography variant="body2" color="textSecondary">
                              Detected
                            </Typography>
                            <Typography variant="body1">
                              {new Date(finding.detection_date).toLocaleDateString()}
                            </Typography>
                          </Grid>
                        </Grid>
                      </Collapse>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default IntelligenceInsights;