import React, { useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts/core';
import { TreeChart } from 'echarts/charts';
import { TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { Card, CardHeader, CardContent, Box, Typography } from '@mui/material';
import { tokens, categoricalColor, fontSans } from '../theme';

// The hierarchy the flat cluster list throws away: the full average-linkage
// merge tree, leaf to root. Constellations are what you get by cutting this
// tree at weighted r = 0.5; the tree also shows everything the cut discards -
// how tight each group is, which groups merge next, and the order in which
// the whole source space folds together. Depth spacing is uniform (a
// cladogram, not a height-true dendrogram); each junction's tooltip carries
// the weighted correlation it merged at.

echarts.use([TreeChart, TooltipComponent, CanvasRenderer]);

interface TreeNode {
  source_id?: number;
  name?: string;
  country?: string | null;
  r?: number;
  children?: TreeNode[];
}

const SourceTreePanel: React.FC<{
  tree: TreeNode | null;
  countryOrder: string[];
}> = ({ tree, countryOrder }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  const { data, leaves } = useMemo(() => {
    if (!tree) return { data: null, leaves: 0 };
    let count = 0;
    const convert = (node: TreeNode): any => {
      if (node.children?.length) {
        return {
          name: '',
          r: node.r,
          symbolSize: 3,
          itemStyle: { color: tokens.border },
          children: node.children.map(convert),
        };
      }
      count += 1;
      const color = categoricalColor(node.country ?? 'Unknown', countryOrder);
      return {
        name: node.name ?? String(node.source_id),
        country: node.country ?? 'Unknown',
        symbolSize: 7,
        itemStyle: { color },
        label: { color: tokens.ink },
      };
    };
    const converted = convert(tree);
    return { data: converted, leaves: count };
  }, [tree, countryOrder]);

  useEffect(() => {
    if (!data || !chartRef.current) return;
    if (!chartInstance.current) chartInstance.current = echarts.init(chartRef.current);
    const chart = chartInstance.current;

    chart.setOption({
      animation: false,
      tooltip: {
        backgroundColor: tokens.surface,
        borderColor: tokens.border,
        textStyle: { color: tokens.ink, fontSize: 12, fontFamily: fontSans },
        extraCssText: 'border-radius: 6px; box-shadow: none;',
        formatter: (p: any) => {
          if (p.data.name) {
            return `${p.data.name}<br/><span style="color:${tokens.inkMuted};font-size:11px">${p.data.country}</span>`;
          }
          const r = p.data.r;
          return r == null
            ? 'merge'
            : `merged at weighted r = ${r >= 0 ? '+' : ''}${r.toFixed(2)}`;
        },
      },
      series: [{
        type: 'tree',
        data: [data],
        layout: 'orthogonal',
        orient: 'LR',
        left: 12,
        right: 170,
        top: 6,
        bottom: 6,
        symbol: 'circle',
        edgeShape: 'polyline',
        lineStyle: { color: tokens.border, width: 1 },
        label: {
          position: 'right',
          distance: 6,
          fontSize: 10,
          fontFamily: fontSans,
          color: tokens.ink,
        },
        expandAndCollapse: false,
        initialTreeDepth: -1,
        roam: true,
        emphasis: { focus: 'ancestor' },
      }],
    });

    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(chartRef.current);
    return () => observer.disconnect();
  }, [data]);

  useEffect(
    () => () => {
      chartInstance.current?.dispose();
      chartInstance.current = null;
    },
    []
  );

  if (!data) return null;

  return (
    <Card>
      <CardHeader
        title="The family tree"
        subheader="How the whole source space folds together — the merge hierarchy the constellations are cut from"
      />
      <CardContent sx={{ pt: 0 }}>
        <Box ref={chartRef} sx={{ width: '100%', height: Math.max(420, leaves * 15) }} />
        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: tokens.inkMuted }}>
          Leaves are sources, colored by country; each junction merges the two most-alike
          branches remaining, and hovering a junction shows the weighted correlation it
          merged at. Constellations above are this tree cut at r = 0.5 — the tree keeps
          what the cut throws away: how tight each group is and what would join next.
          Depth spacing is uniform, not to scale. Drag to pan, scroll to zoom.
        </Typography>
      </CardContent>
    </Card>
  );
};

export default SourceTreePanel;
