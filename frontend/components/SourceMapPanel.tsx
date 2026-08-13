import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as echarts from 'echarts/core';
import { ScatterChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  DataZoomComponent,
} from 'echarts/components';
import { LabelLayout } from 'echarts/features';
import { CanvasRenderer } from 'echarts/renderers';
import { Card, CardHeader, CardContent, Box, Typography, Chip } from '@mui/material';
import { tokens, categoricalColor, monoNumber, fontSans } from '../theme';
import { narrativeApi } from '../services/api';

// The SVD source map (server/routers/narrative_endpoints.py::get_source_map,
// kernel analyzer/narrative_metrics.py::svd_source_map): sources as points in
// the plane the DATA defines - the two directions of greatest disagreement in
// how sources score the same entities. "Beyond left-right" made literal: the
// axes are empirical, unnamed, and re-derived from the corpus every load.
//
// ECharts rather than recharts: similar sources land in clusters by design, so
// the map needs collision-aware labels (labelLayout.hideOverlap) and zoom/pan
// to spread clusters apart - neither of which recharts provides.

echarts.use([
  ScatterChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  DataZoomComponent,
  LabelLayout,
  CanvasRenderer,
]);

interface SourceMapPoint {
  source_id: number;
  source_name: string;
  country: string | null;
  x: number;
  y: number;
}

interface SourceMapResponse {
  weeks: number;
  explained_variance: number[];
  sources: SourceMapPoint[];
}

const SourceMapPanel: React.FC = () => {
  const [data, setData] = useState<SourceMapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    narrativeApi
      .getSourceMap({ weeks: 12 })
      .then((d: SourceMapResponse) => setData(d))
      .catch((err) => setError((err as Error).message));
  }, []);

  const countryOrder = useMemo(() => {
    const order: string[] = [];
    (data?.sources ?? []).forEach((s) => {
      const c = s.country ?? 'Unknown';
      if (!order.includes(c)) order.push(c);
    });
    return order;
  }, [data]);

  const padded = useMemo(() => {
    const pts = data?.sources ?? [];
    if (!pts.length) return { xDomain: [-1, 1] as [number, number], yDomain: [-1, 1] as [number, number] };
    const xs = pts.map((p) => p.x);
    const ys = pts.map((p) => p.y);
    const pad = (lo: number, hi: number): [number, number] => {
      const m = Math.max((hi - lo) * 0.15, 0.1);
      return [lo - m, hi + m];
    };
    return {
      xDomain: pad(Math.min(...xs), Math.max(...xs)),
      yDomain: pad(Math.min(...ys), Math.max(...ys)),
    };
  }, [data]);

  const hasChart = !!data && data.sources.length >= 3;

  useEffect(() => {
    if (!hasChart || !chartRef.current) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
      // Inside-type dataZoom has no built-in reset; double-click restores it.
      chartInstance.current.getZr().on('dblclick', () => {
        chartInstance.current?.dispatchAction({
          type: 'dataZoom',
          batch: [
            { dataZoomIndex: 0, start: 0, end: 100 },
            { dataZoomIndex: 1, start: 0, end: 100 },
          ],
        });
      });
    }
    const chart = chartInstance.current;

    chart.setOption({
      animation: false,
      grid: { top: 12, right: 24, bottom: 30, left: 30 },
      xAxis: {
        type: 'value',
        min: padded.xDomain[0],
        max: padded.xDomain[1],
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { show: false },
        splitLine: { show: true, lineStyle: { color: tokens.border, type: 'dashed' } },
        name: 'Empirical axis 1',
        nameLocation: 'middle',
        nameGap: 14,
        nameTextStyle: { fontSize: 11, color: tokens.inkMuted, fontFamily: fontSans },
      },
      yAxis: {
        type: 'value',
        min: padded.yDomain[0],
        max: padded.yDomain[1],
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { show: false },
        splitLine: { show: true, lineStyle: { color: tokens.border, type: 'dashed' } },
        name: 'Empirical axis 2',
        nameLocation: 'middle',
        nameGap: 14,
        nameTextStyle: { fontSize: 11, color: tokens.inkMuted, fontFamily: fontSans },
      },
      dataZoom: [
        { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
        { type: 'inside', yAxisIndex: 0, filterMode: 'none' },
      ],
      tooltip: {
        trigger: 'item',
        backgroundColor: tokens.surface,
        borderColor: tokens.border,
        textStyle: { color: tokens.ink, fontSize: 12, fontFamily: fontSans },
        extraCssText: 'border-radius: 6px; box-shadow: none;',
        formatter: (params: any) =>
          `${params.name}<br/><span style="color:${tokens.inkMuted};font-size:11px">${
            params.data.country
          }</span>`,
      },
      series: [
        {
          type: 'scatter',
          data: (data?.sources ?? []).map((s) => ({
            name: s.source_name,
            value: [s.x, s.y],
            country: s.country ?? 'Unknown',
            itemStyle: { color: categoricalColor(s.country ?? 'Unknown', countryOrder) },
          })),
          symbolSize: 10,
          itemStyle: { opacity: 0.85, borderColor: tokens.surface, borderWidth: 1 },
          label: {
            show: true,
            position: 'right',
            distance: 6,
            fontSize: 10,
            color: tokens.inkMuted,
            fontFamily: fontSans,
            formatter: (p: any) => p.name,
          },
          // The point of the migration: labels that would collide are hidden,
          // and re-evaluated on every zoom level as clusters spread apart.
          labelLayout: { hideOverlap: true },
          emphasis: {
            label: { show: true, color: tokens.ink, fontWeight: 600 },
            itemStyle: { opacity: 1 },
          },
          markLine: {
            silent: true,
            symbol: 'none',
            animation: false,
            lineStyle: { color: tokens.border, width: 1, type: 'solid' },
            label: { show: false },
            data: [{ xAxis: 0 }, { yAxis: 0 }],
          },
        },
      ],
    });

    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(chartRef.current);
    return () => observer.disconnect();
  }, [hasChart, data, countryOrder, padded]);

  useEffect(
    () => () => {
      chartInstance.current?.dispose();
      chartInstance.current = null;
    },
    []
  );

  return (
    <Card>
      <CardHeader
        title="The source map"
        subheader="Every source placed by the two directions of greatest disagreement the data itself contains (last 12 weeks)"
      />
      <CardContent sx={{ pt: 0 }}>
        {error && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            {error}
          </Typography>
        )}
        {data && data.sources.length < 3 && !error && (
          <Typography variant="body2" sx={{ color: tokens.inkMuted, py: 2 }}>
            Not enough overlapping coverage to place sources yet.
          </Typography>
        )}
        {hasChart && (
          <>
            <Box ref={chartRef} sx={{ width: '100%', height: 420 }} />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mt: 0.5, flexWrap: 'wrap', gap: 1 }}>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {countryOrder.slice(0, 10).map((c) => (
                  <Chip
                    key={c}
                    label={c}
                    size="small"
                    variant="outlined"
                    sx={{
                      borderColor: categoricalColor(c, countryOrder),
                      color: tokens.inkMuted,
                      height: 20,
                      fontSize: 10,
                    }}
                  />
                ))}
              </Box>
              <Typography variant="caption" sx={{ ...monoNumber, color: tokens.inkMuted }}>
                axes explain {data!.explained_variance.map((v) => `${Math.round(v * 100)}%`).join(' + ')} of variance
              </Typography>
            </Box>
            <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.inkMuted }}>
              The axes have no assigned meaning — they are the strongest patterns of disagreement
              in the scores themselves. Sources that land close score the same entities alike.
              Scroll to zoom, drag to pan, double-click to reset; hidden labels appear on hover
              and as clusters spread.
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default SourceMapPanel;
