import React, { useState, useMemo } from 'react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend,
  ReferenceLine,
  Label
} from 'recharts';
import { 
  Box, 
  Typography, 
  ToggleButtonGroup, 
  ToggleButton, 
  Paper,
  Tooltip as MuiTooltip,
  Chip,
  Grid
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';

// Define interfaces
interface TrendPoint {
  date: string;
  power_score: number;
  moral_score: number;
  mention_count: number;
}

interface MultiSourceTrendChartProps {
  entityName: string;
  sourcesTrends: Record<string, TrendPoint[]>;
  height?: number;
  dimension?: 'power' | 'moral' | 'both';
}

// Country-based color palettes
const COUNTRY_COLORS: Record<string, string[]> = {
  'USA': ['#e53e3e', '#fc8181', '#feb2b2', '#fed7d7'], // Reds
  'UK': ['#3182ce', '#63b3ed', '#90cdf4', '#bee3f8'], // Blues  
  'Russia': ['#38a169', '#68d391', '#9ae6b4', '#c6f6d5'], // Greens
  'China': ['#d69e2e', '#f6e05e', '#faf089', '#fefcbf'], // Yellows
  'Germany': ['#805ad5', '#b794f6', '#d6bcfa', '#e9d8fd'], // Purples
  'France': ['#ed8936', '#fbb454', '#fdd089', '#fdefdb'], // Oranges
  'Canada': ['#319795', '#4fd1c7', '#81e6d9', '#b2f5ea'], // Teals
  'Australia': ['#e53e3e', '#fc8181', '#feb2b2', '#fed7d7'], // Reds (share with USA)
  'Japan': ['#9f7aea', '#c3aed6', '#d6bcfa', '#e9d8fd'], // Light purples
  'India': ['#f56500', '#fd9801', '#feb454', '#fed7aa'], // Bright oranges
  'default': ['#718096', '#a0aec0', '#cbd5e0', '#e2e8f0'] // Grays for unknown countries
};

// Line style patterns: Power lines are always dashed, Moral lines are always solid

const MultiSourceTrendChart: React.FC<MultiSourceTrendChartProps> = ({
  entityName,
  sourcesTrends,
  height = 400,
  dimension = 'moral'
}) => {
  const [selectedDimension, setSelectedDimension] = useState<'both' | 'power' | 'moral'>(dimension);
  const [smoothing, setSmoothing] = useState<boolean>(true);
  const [chartMode, setChartMode] = useState<'sentiment' | 'netsum'>('sentiment');

  // Get all source names first
  const allSourceNames = Object.keys(sourcesTrends);

  // Combine all source data into a single dataset for the chart
  const combineSourceData = () => {
    const allDates = new Set<string>();
    
    // Collect all unique dates across all sources
    Object.values(sourcesTrends).forEach(trends => {
      trends.forEach(point => allDates.add(point.date));
    });
    
    const sortedDates = Array.from(allDates).sort();
    
    // Create combined dataset
    return sortedDates.map(date => {
      const dataPoint: any = { date };
      
      Object.entries(sourcesTrends).forEach(([sourceName, trends]) => {
        const point = trends.find(t => t.date === date);
        if (point) {
          if (chartMode === 'sentiment') {
            // Current behavior - keep exactly as is, but validate against NaN
            dataPoint[`${sourceName}_power`] = (typeof point.power_score === 'number' && !isNaN(point.power_score)) ? point.power_score : null;
            dataPoint[`${sourceName}_moral`] = (typeof point.moral_score === 'number' && !isNaN(point.moral_score)) ? point.moral_score : null;
          } else {
            // Net sum calculation - ONLY if both values are valid numbers
            if (typeof point.power_score === 'number' && !isNaN(point.power_score) && 
                typeof point.mention_count === 'number' && !isNaN(point.mention_count)) {
              const netSum = point.power_score * point.mention_count;
              dataPoint[`${sourceName}_power`] = isNaN(netSum) ? null : netSum;
            } else {
              dataPoint[`${sourceName}_power`] = null; // Same as sentiment mode
            }
            
            if (typeof point.moral_score === 'number' && !isNaN(point.moral_score) && 
                typeof point.mention_count === 'number' && !isNaN(point.mention_count)) {
              const netSum = point.moral_score * point.mention_count;
              dataPoint[`${sourceName}_moral`] = isNaN(netSum) ? null : netSum;
            } else {
              dataPoint[`${sourceName}_moral`] = null; // Same as sentiment mode
            }
          }
          dataPoint[`${sourceName}_mentions`] = point.mention_count;
        }
      });
      
      return dataPoint;
    });
  };

  const combinedData = useMemo(() => combineSourceData(), [sourcesTrends, chartMode]);
  
  // Use all source names - don't filter them out
  const sourceNames = allSourceNames;
  
  // Check if we have valid data for rendering
  const hasValidData = useMemo(() => {
    if (sourceNames.length === 0 || combinedData.length === 0) return false;
    
    // Check if there's at least one non-null value in the data
    const hasValidValues = combinedData.some(dataPoint => 
      sourceNames.some(sourceName => {
        const powerValue = dataPoint[`${sourceName}_power`];
        const moralValue = dataPoint[`${sourceName}_moral`];
        return (typeof powerValue === 'number' && !isNaN(powerValue)) || 
               (typeof moralValue === 'number' && !isNaN(moralValue));
      })
    );
    
    return hasValidValues;
  }, [sourceNames, combinedData]);
  
  const hasData = hasValidData;



  // Format date for display
  const formatDate = (date: string) => {
    const d = new Date(date);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  // State for tracking which line is being hovered
  const [hoveredLine, setHoveredLine] = useState<string | null>(null);

  // Custom tooltip that only shows the hovered line
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length && hoveredLine) {
      // Find the entry that matches the hovered line
      const hoveredEntry = payload.find((p: any) => 
        p.dataKey && p.dataKey.startsWith(hoveredLine) && p.value !== undefined && p.value !== null
      );
      
      if (!hoveredEntry) return null;
      
      const sourceName = hoveredEntry.dataKey.replace(/_power|_moral/, '');
      const dimension = hoveredEntry.dataKey.includes('_power') ? 'Power' : 'Moral';
      const country = getCountryFromSource(sourceName);
      const isCountryColored = COUNTRY_COLORS[country] !== undefined;
      
      // Determine line style based on dimension
      const isDashed = dimension === 'Power';
      
      return (
        <Paper 
          elevation={6} 
          sx={{ 
            p: 2, 
            bgcolor: 'rgba(255, 255, 255, 0.95)',
            border: `2px solid ${hoveredEntry.color}`,
            borderRadius: 2,
            minWidth: 180
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            <Box 
              sx={{ 
                width: 20, 
                height: 3, 
                bgcolor: hoveredEntry.color,
                mr: 1,
                borderRadius: 1,
                ...(isDashed && {
                  background: `linear-gradient(to right, ${hoveredEntry.color} 60%, transparent 60%)`,
                  backgroundSize: '8px 3px',
                  backgroundRepeat: 'repeat-x'
                })
              }} 
            />
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
              {sourceName}
            </Typography>
          </Box>
          
          <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
            {formatDate(label)}
          </Typography>
          
          <Box sx={{ mt: 1 }}>
            <Typography 
              variant="body2" 
              sx={{ 
                color: hoveredEntry.color,
                fontWeight: 'bold',
                fontSize: '0.9rem'
              }}
            >
              {dimension}: {
                typeof hoveredEntry.value === 'number' && !isNaN(hoveredEntry.value) 
                  ? (chartMode === 'sentiment' 
                      ? hoveredEntry.value.toFixed(2) 
                      : `${hoveredEntry.value.toFixed(1)} (net sum)`)
                  : 'No data'
              }
            </Typography>
          </Box>
          
          <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip 
              label={country} 
              size="small" 
              sx={{
                backgroundColor: isCountryColored ? `${hoveredEntry.color}20` : 'action.hover',
                color: hoveredEntry.color,
                fontWeight: 'bold',
                fontSize: '0.7rem'
              }}
            />
            <Chip 
              label={isDashed ? "dashed" : "solid"} 
              size="small" 
              variant="outlined"
              sx={{ fontSize: '0.7rem', height: 20 }}
            />
          </Box>
        </Paper>
      );
    }
    return null;
  };

  const handleDimensionChange = (
    event: React.MouseEvent<HTMLElement>,
    newDimension: 'both' | 'power' | 'moral' | null
  ) => {
    if (newDimension !== null) {
      setSelectedDimension(newDimension);
    }
  };

  const handleSmoothingChange = (
    event: React.MouseEvent<HTMLElement>,
    newSmoothing: boolean | null
  ) => {
    if (newSmoothing !== null) {
      setSmoothing(newSmoothing);
    }
  };

  const handleChartModeChange = (
    event: React.MouseEvent<HTMLElement>,
    newMode: 'sentiment' | 'netsum' | null
  ) => {
    if (newMode !== null) {
      setChartMode(newMode);
    }
  };


  // Get country from source name (handles both "Source (Country)" and "Country" formats)
  const getCountryFromSource = (sourceName: string) => {
    // First try to extract from parentheses format "Source (Country)"
    const match = sourceName.match(/\(([^)]+)\)$/);
    if (match) {
      return match[1];
    }
    
    // If no parentheses, check if the source name itself is a country
    if (COUNTRY_COLORS[sourceName]) {
      return sourceName;
    }
    
    return '';
  };

  // Group sources by country for better visualization
  const sourcesByCountry = sourceNames.reduce((acc, sourceName) => {
    const country = getCountryFromSource(sourceName);
    if (!acc[country]) acc[country] = [];
    acc[country].push(sourceName);
    return acc;
  }, {} as Record<string, string[]>);

  // Assign colors to sources based on country
  const getSourceColor = (sourceName: string) => {
    const country = getCountryFromSource(sourceName);
    const countryPalette = COUNTRY_COLORS[country] || COUNTRY_COLORS['default'];
    const sourceIndexInCountry = sourcesByCountry[country].indexOf(sourceName);
    return countryPalette[sourceIndexInCountry % countryPalette.length];
  };


  return (
    <Box sx={{ width: '100%', height: height }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Typography variant="subtitle1" sx={{ mr: 1 }}>
            {entityName} - Cross-Source {chartMode === 'sentiment' ? 'Sentiment' : 'Net Sentiment Sum'}
          </Typography>
          <MuiTooltip title="Compare how different news sources portray the same entity over time. Each line represents a different newspaper's sentiment."
          >
            <InfoIcon fontSize="small" color="action" />
          </MuiTooltip>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <ToggleButtonGroup
            size="small"
            value={chartMode}
            exclusive
            onChange={handleChartModeChange}
            aria-label="chart mode selector"
          >
            <ToggleButton value="sentiment" aria-label="sentiment mode">
              Sentiment
            </ToggleButton>
            <ToggleButton value="netsum" aria-label="net sum mode">
              <MuiTooltip title="Shows sentiment score × mention count to reveal impact magnitude">
                <span>Net Sum</span>
              </MuiTooltip>
            </ToggleButton>
          </ToggleButtonGroup>
          <ToggleButtonGroup
            size="small"
            value={selectedDimension}
            exclusive
            onChange={handleDimensionChange}
            aria-label="dimension selector"
          >
            <ToggleButton value="both" aria-label="both dimensions">
              Both
            </ToggleButton>
            <ToggleButton value="power" aria-label="power dimension">
              Power
            </ToggleButton>
            <ToggleButton value="moral" aria-label="moral dimension">
              Moral
            </ToggleButton>
          </ToggleButtonGroup>
          <ToggleButtonGroup
            size="small"
            value={smoothing}
            exclusive
            onChange={handleSmoothingChange}
            aria-label="smoothing selector"
          >
            <ToggleButton value={true} aria-label="smoothed line">
              Smooth
            </ToggleButton>
            <ToggleButton value={false} aria-label="exact line">
              Exact
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      {/* Country groupings */}
      {hasData && (
        <Box sx={{ mb: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {Object.entries(sourcesByCountry).map(([country, sources]) => {
            const countryPalette = COUNTRY_COLORS[country] || COUNTRY_COLORS['default'];
            const mainColor = countryPalette[0];
            
            return (
              <Chip 
                key={country} 
                label={`${country} (${sources.length})`} 
                size="small" 
                sx={{
                  backgroundColor: `${mainColor}20`,
                  color: mainColor,
                  borderColor: mainColor,
                  fontWeight: 'bold'
                }}
                variant="outlined"
              />
            );
          })}
        </Box>
      )}

      {!hasData && (
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '80%',
          bgcolor: 'background.paper',
          borderRadius: 1,
          border: '1px dashed',
          borderColor: 'divider',
          p: 3
        }}>
          <Typography variant="body1" color="text.secondary">
            No source-specific trend data available for {entityName}
          </Typography>
        </Box>
      )}

      {hasData && (
        <ResponsiveContainer width="100%" height="85%">
          <LineChart
            key={`${selectedDimension}-${chartMode}`}
            data={combinedData}
            margin={{ top: 20, right: 30, bottom: 20, left: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" opacity={0.4} />
            <XAxis 
              dataKey="date" 
              tickFormatter={formatDate}
              padding={{ left: 20, right: 20 }}
            />
            <YAxis 
              domain={chartMode === 'sentiment' ? [-2, 2] : [-50, 50]}
              tickCount={chartMode === 'sentiment' ? 9 : 11}
            >
              <Label 
                value={chartMode === 'sentiment' ? "Sentiment Score" : "Net Sentiment Sum"}
                angle={-90} 
                position="insideLeft" 
                style={{ textAnchor: 'middle' }} 
              />
            </YAxis>
            <Tooltip 
              content={<CustomTooltip />} 
              cursor={{ stroke: '#666', strokeWidth: 1, strokeDasharray: '3 3' }}
              allowEscapeViewBox={{ x: true, y: true }}
              position={{ x: 'auto', y: 'auto' }}
              animationDuration={0}
              animationEasing="linear"
            />
            <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
            
            {/* Render lines for each source */}
            {sourceNames.map((sourceName, index) => {
              const color = getSourceColor(sourceName);
              const country = getCountryFromSource(sourceName);
              
              return (
                <React.Fragment key={sourceName}>
                  {(selectedDimension === 'both' || selectedDimension === 'power') && (
                    <Line
                      type={smoothing ? "monotone" : "linear"}
                      name={`${sourceName} (Power)`}
                      dataKey={`${sourceName}_power`}
                      stroke={color}
                      strokeWidth={2.5}
                      strokeDasharray="5 5"
                      dot={{ strokeWidth: 2, r: 4, fill: color }}
                      activeDot={{ 
                        r: 6, 
                        strokeWidth: 2, 
                        fill: color,
                        onMouseEnter: () => setHoveredLine(sourceName),
                        onMouseLeave: () => setHoveredLine(null)
                      }}
                      connectNulls={false}
                      onMouseEnter={() => setHoveredLine(sourceName)}
                      onMouseLeave={() => setHoveredLine(null)}
                    />
                  )}
                  {(selectedDimension === 'both' || selectedDimension === 'moral') && (
                    <Line
                      type={smoothing ? "monotone" : "linear"}
                      name={`${sourceName} (Moral)`}
                      dataKey={`${sourceName}_moral`}
                      stroke={color}
                      strokeWidth={2.5}
                      strokeDasharray="0"
                      dot={{ strokeWidth: 2, r: 4, fill: color }}
                      activeDot={{ 
                        r: 6, 
                        strokeWidth: 2, 
                        fill: color,
                        onMouseEnter: () => setHoveredLine(sourceName),
                        onMouseLeave: () => setHoveredLine(null)
                      }}
                      connectNulls={false}
                      onMouseEnter={() => setHoveredLine(sourceName)}
                      onMouseLeave={() => setHoveredLine(null)}
                    />
                  )}
                </React.Fragment>
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      )}
      
      {/* Permanent Legend Below Chart */}
      {hasData && (
        <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
          <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 'bold' }}>
            Legend
          </Typography>
          <Grid container spacing={1}>
            {sourceNames.map((sourceName) => {
              const color = getSourceColor(sourceName);
              const country = getCountryFromSource(sourceName);
              
              return (
                <Grid item xs={12} sm={6} md={4} lg={3} key={sourceName}>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    {/* Power line if shown */}
                    {(selectedDimension === 'both' || selectedDimension === 'power') && (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box 
                          sx={{ 
                            width: 24, 
                            height: 3, 
                            background: `linear-gradient(to right, ${color} 60%, transparent 60%)`,
                            backgroundSize: '8px 3px',
                            backgroundRepeat: 'repeat-x',
                            borderRadius: 1
                          }} 
                        />
                        <Typography variant="caption" sx={{ fontSize: '0.75rem' }}>
                          {sourceName} (Power)
                        </Typography>
                      </Box>
                    )}
                    
                    {/* Moral line if shown */}
                    {(selectedDimension === 'both' || selectedDimension === 'moral') && (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box 
                          sx={{ 
                            width: 24, 
                            height: 3, 
                            bgcolor: color,
                            borderRadius: 1
                          }} 
                        />
                        <Typography variant="caption" sx={{ fontSize: '0.75rem' }}>
                          {sourceName} (Moral)
                        </Typography>
                      </Box>
                    )}
                    
                    {/* Country indicator */}
                    <Box sx={{ ml: 3, mt: 0.5 }}>
                      <Chip 
                        label={country} 
                        size="small" 
                        sx={{
                          backgroundColor: `${color}15`,
                          color: color,
                          fontSize: '0.65rem',
                          height: 16,
                          fontWeight: 'bold'
                        }}
                      />
                    </Box>
                  </Box>
                </Grid>
              );
            })}
          </Grid>
        </Box>
      )}
    </Box>
  );
};

export default MultiSourceTrendChart;