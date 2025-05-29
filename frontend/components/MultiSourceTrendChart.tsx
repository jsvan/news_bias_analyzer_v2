import React, { useState } from 'react';
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
  Chip
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

// Line style patterns
const LINE_STYLES = ['0', '5 5', '10 5', '10 5 5 5', '15 5 15 5'];

const MultiSourceTrendChart: React.FC<MultiSourceTrendChartProps> = ({
  entityName,
  sourcesTrends,
  height = 400,
  dimension = 'both'
}) => {
  const [selectedDimension, setSelectedDimension] = useState<'both' | 'power' | 'moral'>(dimension);
  const [smoothing, setSmoothing] = useState<boolean>(true);

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
          dataPoint[`${sourceName}_power`] = point.power_score;
          dataPoint[`${sourceName}_moral`] = point.moral_score;
          dataPoint[`${sourceName}_mentions`] = point.mention_count;
        }
      });
      
      return dataPoint;
    });
  };

  const combinedData = combineSourceData();
  const sourceNames = Object.keys(sourcesTrends);
  const hasData = sourceNames.length > 0 && combinedData.length > 0;

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
      
      // Get line style info
      const lineStyle = getSourceLineStyle(sourceName);
      const isDashed = lineStyle !== '0';
      
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
              {dimension}: {hoveredEntry.value.toFixed(2)}
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
            {isDashed && (
              <Chip 
                label="dashed" 
                size="small" 
                variant="outlined"
                sx={{ fontSize: '0.7rem', height: 20 }}
              />
            )}
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

  // Get country from source name (assumes format "Source (Country)")
  const getCountryFromSource = (sourceName: string) => {
    const match = sourceName.match(/\(([^)]+)\)$/);
    return match ? match[1] : '';
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

  // Get line style for source
  const getSourceLineStyle = (sourceName: string) => {
    const sourceIndex = sourceNames.indexOf(sourceName);
    return LINE_STYLES[sourceIndex % LINE_STYLES.length];
  };

  return (
    <Box sx={{ width: '100%', height: height }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Typography variant="subtitle1" sx={{ mr: 1 }}>
            {entityName} - Cross-Source Sentiment
          </Typography>
          <MuiTooltip title="Compare how different news sources portray the same entity over time. Each line represents a different newspaper's sentiment.">
            <InfoIcon fontSize="small" color="action" />
          </MuiTooltip>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
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
              domain={[-2, 2]} 
              tickCount={9} 
            >
              <Label 
                value="Sentiment Score" 
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
            />
            <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
            
            {/* Render lines for each source */}
            {sourceNames.map((sourceName, index) => {
              const color = getSourceColor(sourceName);
              const lineStyle = getSourceLineStyle(sourceName);
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
                      strokeDasharray={selectedDimension === 'both' ? lineStyle : "0"}
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
                      strokeDasharray={selectedDimension === 'both' ? "0" : lineStyle}
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
    </Box>
  );
};

export default MultiSourceTrendChart;