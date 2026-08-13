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
import { tokens, monoNumber } from '../theme';

// Fixed 3-way comparison (global baseline / national / source) — not a rotating
// first-appearance palette, since these three roles are always the same slots.
const GLOBAL_COLOR = tokens.accent;
const NATIONAL_COLOR = tokens.categorical[1];
const SOURCE_COLOR = tokens.categorical[2];

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
  // Layer visibility is real state: the chips are working toggles, initialized from props.
  const [visible, setVisible] = useState({ global: showGlobal, national: showNational, source: showSource });
  const toggleLayer = (layer: 'global' | 'national' | 'source') =>
    setVisible((v) => ({ ...v, [layer]: !v[layer] }));

  // Get the selected distribution data
  const getDistributionData = (): DistributionDataPoint[] => {
    // Check which distributions are available
    const hasGlobal = distributions.global?.[dimension]?.pdf?.x && distributions.global?.[dimension]?.pdf?.y;
    const hasNational = distributions.national?.[dimension]?.pdf?.x && distributions.national?.[dimension]?.pdf?.y;
    const hasSource = distributions.source?.[dimension]?.pdf?.x && distributions.source?.[dimension]?.pdf?.y;
    
    if (!hasGlobal && !hasNational && !hasSource) {
      return []; // No distribution data available
    }
    
    // Get the pdf data for the selected dimension
    const globalPdf = distributions.global?.[dimension]?.pdf || { x: [], y: [] };
    const nationalPdf = distributions.national?.[dimension]?.pdf || { x: [], y: [] };
    const sourcePdf = distributions.source?.[dimension]?.pdf || { x: [], y: [] };
    
    // Create data points for chart
    return globalPdf.x.map((value, index) => {
      const point: DistributionDataPoint = { x: value };
      
      if (hasGlobal && visible.global) {
        point.global = globalPdf.y[index];
      }
      
      if (hasNational && visible.national) {
        // Find the closest x value in national data
        const nationalIndex = nationalPdf.x.findIndex(x => x >= value);
        if (nationalIndex >= 0) {
          point.national = nationalPdf.y[nationalIndex];
        }
      }
      
      if (hasSource && visible.source) {
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
  
  // Per-layer legend names with real sample sizes (n from the selected dimension)
  const layerName = (layer: 'global' | 'national' | 'source'): string => {
    const dist = distributions[layer];
    if (!dist) return layer;
    const count = dimension === 'power' ? dist.power.count : dist.moral.count;
    const label = layer === 'global' ? 'Global' : layer === 'national' ? distributions.national!.country : distributions.source!.source_name;
    return `${label} (n=${count})`;
  };

  return (
    <Box sx={{ width: '100%', height: height, padding: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ color: tokens.ink }}>
            {title}: {entityName}
          </Typography>
          <Typography variant="subtitle2" sx={{ color: tokens.inkMuted }}>
            {dimension === 'power' ? 'Power Dimension' : 'Moral Dimension'} Distribution
          </Typography>
          {!hasEnoughData && (
            <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.villain }}>
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
                sx={{
                  mx: 0.5,
                  bgcolor: visible.global ? GLOBAL_COLOR : 'transparent',
                  color: visible.global ? '#FFFFFF' : tokens.inkMuted,
                  border: `1px solid ${visible.global ? GLOBAL_COLOR : tokens.border}`,
                }}
                onClick={() => toggleLayer('global')}
              />
            )}
            {distributions.national && (
              <Chip
                label={distributions.national.country}
                sx={{
                  mx: 0.5,
                  bgcolor: visible.national ? NATIONAL_COLOR : 'transparent',
                  color: visible.national ? '#FFFFFF' : tokens.inkMuted,
                  border: `1px solid ${visible.national ? NATIONAL_COLOR : tokens.border}`,
                }}
                onClick={() => toggleLayer('national')}
              />
            )}
            {distributions.source && (
              <Chip
                label={distributions.source.source_name}
                sx={{
                  mx: 0.5,
                  bgcolor: visible.source ? SOURCE_COLOR : 'transparent',
                  color: visible.source ? '#FFFFFF' : tokens.inkMuted,
                  border: `1px solid ${visible.source ? SOURCE_COLOR : tokens.border}`,
                }}
                onClick={() => toggleLayer('source')}
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
          bgcolor: tokens.surfaceSunken,
          borderRadius: 1,
          border: `1px solid ${tokens.border}`,
          p: 3
        }}>
          <Typography variant="body1" sx={{ mb: 2, color: tokens.inkMuted }}>
            Not enough data available for meaningful statistical visualization
          </Typography>
          <Typography variant="body2" sx={{ color: tokens.inkMuted }}>
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
          <CartesianGrid strokeDasharray="3 3" stroke={tokens.border} />
          <XAxis
            dataKey="x"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickCount={9}
            tickFormatter={(v: number) => v.toFixed(1)}
            tick={{ fill: tokens.inkMuted, fontSize: 11, fontFamily: 'monospace' }}
          >
            <Label
              value={dimension === 'power' ? 'Power Score' : 'Moral Score'}
              position="bottom"
              offset={10}
              style={{ fill: tokens.inkMuted, fontSize: 12 }}
            />
          </XAxis>
          <YAxis tick={{ fill: tokens.inkMuted, fontSize: 11, fontFamily: 'monospace' }}>
            <Label value="Probability Density" position="left" angle={-90} offset={10} style={{ fill: tokens.inkMuted, fontSize: 12 }} />
          </YAxis>
          <Tooltip
            formatter={(value: number) => [value.toFixed(4), 'Probability Density']}
            labelFormatter={(label) => `Score: ${Number(label).toFixed(2)}`}
            contentStyle={{ border: `1px solid ${tokens.border}`, borderRadius: 8, backgroundColor: tokens.surface }}
            labelStyle={{ color: tokens.ink }}
            itemStyle={{ color: tokens.ink, ...monoNumber }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: tokens.inkMuted }} />

          {/* Neutral is the anchor of the whole scale - always visible. */}
          <ReferenceLine
            x={0}
            stroke={tokens.ink}
            strokeWidth={1.25}
            label={{ value: 'neutral', position: 'insideTopLeft', fill: tokens.inkMuted, fontSize: 11 }}
          />

          {/* Reference lines for means */}
          {visible.global && means.global !== undefined && (
            <ReferenceLine
              x={means.global}
              stroke={GLOBAL_COLOR}
              strokeDasharray="3 3"
              label={{ value: 'Global Mean', position: 'top', fill: tokens.inkMuted, fontSize: 12 }}
            />
          )}

          {visible.national && means.national !== undefined && (
            <ReferenceLine
              x={means.national}
              stroke={NATIONAL_COLOR}
              strokeDasharray="3 3"
              label={{ value: 'National Mean', position: 'top', fill: tokens.inkMuted, fontSize: 12 }}
            />
          )}

          {visible.source && means.source !== undefined && (
            <ReferenceLine
              x={means.source}
              stroke={SOURCE_COLOR}
              strokeDasharray="3 3"
              label={{ value: 'Source Mean', position: 'top', fill: tokens.inkMuted, fontSize: 12 }}
            />
          )}

          {/* Distribution areas */}
          {visible.global && distributions.global && (
            <Area
              type="monotone"
              dataKey="global"
              name={layerName('global')}
              fill={GLOBAL_COLOR}
              stroke={GLOBAL_COLOR}
              fillOpacity={0.3}
            />
          )}

          {visible.national && distributions.national && (
            <Area
              type="monotone"
              dataKey="national"
              name={layerName('national')}
              fill={NATIONAL_COLOR}
              stroke={NATIONAL_COLOR}
              fillOpacity={0.3}
            />
          )}

          {visible.source && distributions.source && (
            <Area
              type="monotone"
              dataKey="source"
              name={layerName('source')}
              fill={SOURCE_COLOR}
              stroke={SOURCE_COLOR}
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