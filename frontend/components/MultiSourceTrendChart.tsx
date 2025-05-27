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

// Predefined colors for different sources
const COLORS = [
  '#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#0088fe',
  '#00c49f', '#ffbb28', '#ff8042', '#8dd1e1', '#d084d0',
  '#87d068', '#f56565', '#4fd1c7', '#63b3ed', '#fbd38d'
];

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

  // Custom tooltip for the chart
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const relevantPayload = payload.filter((p: any) => p.value !== undefined);
      
      if (relevantPayload.length === 0) return null;
      
      return (
        <Paper elevation={3} sx={{ p: 2, bgcolor: 'background.paper', maxWidth: 300 }}>
          <Typography variant="subtitle2">{formatDate(label)}</Typography>
          {relevantPayload.map((entry: any, index: number) => {
            const sourceName = entry.dataKey.replace(/_power|_moral/, '');
            const dimension = entry.dataKey.includes('_power') ? 'Power' : 'Moral';
            
            return (
              <Box key={`item-${index}`} sx={{ color: entry.color, mt: 1 }}>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  {sourceName} - {dimension}: {entry.value.toFixed(2)}
                </Typography>
              </Box>
            );
          })}
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
          {Object.entries(sourcesByCountry).map(([country, sources]) => (
            <Chip 
              key={country} 
              label={`${country} (${sources.length})`} 
              size="small" 
              variant="outlined"
            />
          ))}
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
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
            
            {/* Render lines for each source */}
            {sourceNames.map((sourceName, index) => {
              const color = COLORS[index % COLORS.length];
              const country = getCountryFromSource(sourceName);
              
              return (
                <React.Fragment key={sourceName}>
                  {(selectedDimension === 'both' || selectedDimension === 'power') && (
                    <Line
                      type={smoothing ? "monotone" : "linear"}
                      name={`${sourceName} (Power)`}
                      dataKey={`${sourceName}_power`}
                      stroke={color}
                      strokeWidth={2}
                      strokeDasharray={selectedDimension === 'both' ? "5 5" : "0"}
                      dot={{ strokeWidth: 2, r: 3 }}
                      connectNulls={false}
                    />
                  )}
                  {(selectedDimension === 'both' || selectedDimension === 'moral') && (
                    <Line
                      type={smoothing ? "monotone" : "linear"}
                      name={`${sourceName} (Moral)`}
                      dataKey={`${sourceName}_moral`}
                      stroke={color}
                      strokeWidth={2}
                      strokeDasharray={selectedDimension === 'both' ? "0" : "0"}
                      dot={{ strokeWidth: 2, r: 3 }}
                      connectNulls={false}
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