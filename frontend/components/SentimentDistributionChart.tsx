import React, { useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Label,
  ReferenceLine
} from 'recharts';
import { Box, Typography, ToggleButtonGroup, ToggleButton, Chip } from '@mui/material';
import { Distribution, SentimentDistributions } from '../types';

interface SentimentDistributionChartProps {
  title?: string;
  distributions: SentimentDistributions;
  entityName: string;
  height?: number;
  showGlobal?: boolean;
  showNational?: boolean;
  showSource?: boolean;
}

interface DistributionDataPoint {
  x: number;
  global?: number;
  national?: number;
  source?: number;
}

const SentimentDistributionChart: React.FC<SentimentDistributionChartProps> = ({
  title = 'Sentiment Distribution',
  distributions,
  entityName,
  height = 400,
  showGlobal = true,
  showNational = true,
  showSource = true
}) => {
  const [dimension, setDimension] = useState<'power' | 'moral'>('power');
  
  // Get the selected distribution data
  const getDistributionData = (): DistributionDataPoint[] => {
    // Check which distributions are available
    const hasGlobal = distributions.global?.pdf?.x && distributions.global?.pdf?.y;
    const hasNational = distributions.national?.pdf?.x && distributions.national?.pdf?.y;
    const hasSource = distributions.source?.pdf?.x && distributions.source?.pdf?.y;
    
    if (!hasGlobal && !hasNational && !hasSource) {
      return []; // No distribution data available
    }
    
    // Get the pdf data for the selected dimension
    const globalPdf = dimension === 'power' ? 
      (distributions.global?.pdf || { x: [], y: [] }) : 
      (distributions.global?.pdf || { x: [], y: [] });
      
    const nationalPdf = dimension === 'power' ? 
      (distributions.national?.pdf || { x: [], y: [] }) : 
      (distributions.national?.pdf || { x: [], y: [] });
    
    const sourcePdf = dimension === 'power' ? 
      (distributions.source?.pdf || { x: [], y: [] }) : 
      (distributions.source?.pdf || { x: [], y: [] });
    
    // Create data points for chart
    return globalPdf.x.map((value, index) => {
      const point: DistributionDataPoint = { x: value };
      
      if (hasGlobal && showGlobal) {
        point.global = globalPdf.y[index];
      }
      
      if (hasNational && showNational) {
        // Find the closest x value in national data
        const nationalIndex = nationalPdf.x.findIndex(x => x >= value);
        if (nationalIndex >= 0) {
          point.national = nationalPdf.y[nationalIndex];
        }
      }
      
      if (hasSource && showSource) {
        // Find the closest x value in source data
        const sourceIndex = sourcePdf.x.findIndex(x => x >= value);
        if (sourceIndex >= 0) {
          point.source = sourcePdf.y[sourceIndex];
        }
      }
      
      return point;
    });
  };
  
  // Handle dimension toggle
  const handleDimensionChange = (
    event: React.MouseEvent<HTMLElement>,
    newDimension: 'power' | 'moral' | null
  ) => {
    if (newDimension !== null) {
      setDimension(newDimension);
    }
  };
  
  // Get the means for reference lines
  const getMeans = () => {
    const means = {
      global: dimension === 'power' 
        ? distributions.global?.power.mean 
        : distributions.global?.moral.mean,
      national: dimension === 'power' 
        ? distributions.national?.power.mean 
        : distributions.national?.moral.mean,
      source: dimension === 'power' 
        ? distributions.source?.power.mean 
        : distributions.source?.moral.mean
    };
    
    return means;
  };
  
  // Get the data points for the chart
  const distributionData = getDistributionData();
  const means = getMeans();

  // Check if we have enough data for meaningful visualization
  const hasEnoughData = distributionData.length >= 20; // Minimum data points for statistical relevance
  
  // Get legend items with counts
  const getLegendItems = () => {
    const items = [];
    
    if (distributions.global && showGlobal) {
      const count = dimension === 'power' 
        ? distributions.global.power.count 
        : distributions.global.moral.count;
      items.push(`Global (n=${count})`);
    }
    
    if (distributions.national && showNational) {
      const count = dimension === 'power' 
        ? distributions.national.power.count 
        : distributions.national.moral.count;
      items.push(`${distributions.national.country} (n=${count})`);
    }
    
    if (distributions.source && showSource) {
      const count = dimension === 'power' 
        ? distributions.source.power.count 
        : distributions.source.moral.count;
      items.push(`${distributions.source.source_name} (n=${count})`);
    }
    
    return items;
  };

  return (
    <Box sx={{ width: '100%', height: height, padding: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h6">
            {title}: {entityName}
          </Typography>
          <Typography variant="subtitle2" color="text.secondary">
            {dimension === 'power' ? 'Power Dimension' : 'Moral Dimension'} Distribution
          </Typography>
          {!hasEnoughData && (
            <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1 }}>
              Insufficient data for reliable statistical analysis. More data points needed.
            </Typography>
          )}
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* Toggle which distributions to show */}
          <Box>
            {distributions.global && (
              <Chip 
                label="Global" 
                color={showGlobal ? "primary" : "default"} 
                sx={{ mx: 0.5 }}
                onClick={() => showGlobal} 
              />
            )}
            {distributions.national && (
              <Chip 
                label={distributions.national.country} 
                color={showNational ? "secondary" : "default"} 
                sx={{ mx: 0.5 }}
                onClick={() => showNational} 
              />
            )}
            {distributions.source && (
              <Chip 
                label={distributions.source.source_name} 
                color={showSource ? "success" : "default"} 
                sx={{ mx: 0.5 }}
                onClick={() => showSource} 
              />
            )}
          </Box>
          
          {/* Dimension toggle */}
          <ToggleButtonGroup
            value={dimension}
            exclusive
            onChange={handleDimensionChange}
            aria-label="sentiment dimension"
            size="small"
          >
            <ToggleButton value="power" aria-label="power dimension">
              Power
            </ToggleButton>
            <ToggleButton value="moral" aria-label="moral dimension">
              Moral
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>
      
      {!hasEnoughData && (
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          height: '80%',
          bgcolor: 'rgba(0,0,0,0.03)',
          borderRadius: 1,
          p: 3
        }}>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
            Not enough data available for meaningful statistical visualization
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Additional entity mentions are required for reliable distribution analysis
          </Typography>
        </Box>
      )}

      {hasEnoughData && (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={distributionData}
            margin={{ top: 20, right: 30, bottom: 30, left: 30 }}
          >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="x" domain={[-2, 2]} tickCount={11}>
            <Label 
              value={dimension === 'power' ? 'Power Score' : 'Moral Score'} 
              position="bottom" 
              offset={10} 
            />
          </XAxis>
          <YAxis>
            <Label value="Probability Density" position="left" angle={-90} offset={10} />
          </YAxis>
          <Tooltip 
            formatter={(value: number) => [value.toFixed(4), 'Probability Density']}
            labelFormatter={(label) => `Score: ${label}`}
          />
          <Legend formatter={(value) => getLegendItems().shift() || value} />
          
          {/* Reference lines for means */}
          {showGlobal && means.global !== undefined && (
            <ReferenceLine 
              x={means.global} 
              stroke="#8884d8" 
              strokeDasharray="3 3" 
              label={{ value: 'Global Mean', position: 'top' }}
            />
          )}
          
          {showNational && means.national !== undefined && (
            <ReferenceLine 
              x={means.national} 
              stroke="#82ca9d" 
              strokeDasharray="3 3" 
              label={{ value: 'National Mean', position: 'top' }}
            />
          )}
          
          {showSource && means.source !== undefined && (
            <ReferenceLine 
              x={means.source} 
              stroke="#ffc658" 
              strokeDasharray="3 3" 
              label={{ value: 'Source Mean', position: 'top' }}
            />
          )}
          
          {/* Distribution areas */}
          {showGlobal && (
            <Area 
              type="monotone" 
              dataKey="global" 
              fill="#8884d8" 
              stroke="#8884d8" 
              fillOpacity={0.3}
            />
          )}
          
          {showNational && (
            <Area 
              type="monotone" 
              dataKey="national" 
              fill="#82ca9d" 
              stroke="#82ca9d" 
              fillOpacity={0.3}
            />
          )}
          
          {showSource && (
            <Area 
              type="monotone" 
              dataKey="source" 
              fill="#ffc658" 
              stroke="#ffc658" 
              fillOpacity={0.3}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
      )}
    </Box>
  );
};

export default SentimentDistributionChart;