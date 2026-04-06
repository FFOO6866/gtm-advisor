/**
 * RoadmapCanvas — Gantt-style timeline view of the GTM Roadmap.
 *
 * LAYOUT:
 *   Y-axis: Strategy track swim lanes (rows)
 *   X-axis: Timeline (weeks/months — switchable)
 *   Bars: Campaign tasks positioned by phase timing, width = duration
 *
 * All content is produced by the Campaign Strategist agent.
 * The canvas only VISUALIZES + enables APPROVAL — never generates content.
 */

import { useMemo, useState, useCallback, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { GanttBarNode, type GanttBarData } from './GanttBarNode';
import { TrackLaneNode, type TrackLaneData } from './TrackLaneNode';
import { TimelineHeaderNode, type TimelineHeaderData } from './TimelineHeaderNode';
import { TodayLineNode, type TodayLineData } from './TodayLineNode';
import type { RoadmapResponse, RoadmapCampaign } from '../../api/roadmap';

const nodeTypes: NodeTypes = {
  ganttBar: GanttBarNode as any,
  trackLane: TrackLaneNode as any,
  timelineHeader: TimelineHeaderNode as any,
  todayLine: TodayLineNode as any,
};

// ── Timeline constants ──────────────────────────────────────────────────
export type TimelineScale = 'weeks' | 'months' | 'quarters';

const SCALE_CONFIG: Record<TimelineScale, { unitWidth: number; totalUnits: number; label: string }> = {
  weeks: { unitWidth: 80, totalUnits: 52, label: 'Weeks' },
  months: { unitWidth: 160, totalUnits: 12, label: 'Months' },
  quarters: { unitWidth: 320, totalUnits: 4, label: 'Quarters' },
};

// Map phase → timeline position (in weeks from start)
const PHASE_TIMING: Record<string, { startWeek: number; durationWeeks: number }> = {
  immediate: { startWeek: 0, durationWeeks: 2 },
  short_term: { startWeek: 2, durationWeeks: 10 },   // Week 2-12 (~30-90 days)
  mid_term: { startWeek: 12, durationWeeks: 14 },     // Week 12-26 (~3-6 months)
  long_term: { startWeek: 26, durationWeeks: 26 },    // Week 26-52 (~6-12 months)
};

const TRACK_LABEL_WIDTH = 220;   // Left sidebar width for track labels
const TRACK_HEIGHT = 90;         // Height per campaign bar row within a track
const TRACK_GAP = 16;            // Gap between tracks
const TRACK_HEADER_HEIGHT = 40;  // Track label header
const BAR_HEIGHT = 62;           // Height of each Gantt bar — larger for readability
const BAR_Y_OFFSET = 14;         // Top padding within track row
const HEADER_HEIGHT = 52;        // Timeline header height
const TOP_OFFSET = HEADER_HEIGHT + 20;

interface RoadmapCanvasProps {
  roadmapData: RoadmapResponse;
  onSelectCampaign: (campaignId: string) => void;
  onGenerateCreative: (campaignId: string) => void;
  onLaunchCampaign: (campaignId: string) => void;
}

/**
 * Transform roadmap data into Gantt-style nodes.
 */
function buildGanttElements(
  data: RoadmapResponse,
  scale: TimelineScale,
  callbacks: {
    onSelectCampaign: (id: string) => void;
  },
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  if (!data.roadmap) return { nodes, edges };

  const { unitWidth, totalUnits } = SCALE_CONFIG[scale];
  const totalWidth = TRACK_LABEL_WIDTH + totalUnits * unitWidth;

  // ── Timeline anchoring ────────────────────────────────────────────────
  // Start from the roadmap creation date (or start of current year).
  // Always show a full year so users see the whole picture.
  const roadmapCreated = data.roadmap.created_at
    ? new Date(data.roadmap.created_at)
    : new Date();
  const timelineStart = new Date(roadmapCreated.getFullYear(), roadmapCreated.getMonth(), 1);
  const now = new Date();

  // Weeks elapsed since timeline start → used to compute "today" position
  const msPerWeek = 7 * 24 * 60 * 60 * 1000;
  const weeksFromStart = (now.getTime() - timelineStart.getTime()) / msPerWeek;

  // ── 1. Timeline header markers ────────────────────────────────────────
  const headerLabels: string[] = [];

  for (let i = 0; i < totalUnits; i++) {
    if (scale === 'weeks') {
      const d = new Date(timelineStart);
      d.setDate(d.getDate() + i * 7);
      headerLabels.push(`W${i + 1}`);
    } else if (scale === 'months') {
      const d = new Date(timelineStart.getFullYear(), timelineStart.getMonth() + i, 1);
      headerLabels.push(d.toLocaleString('default', { month: 'short', year: '2-digit' }));
    } else {
      const qMonth = timelineStart.getMonth() + i * 3;
      const qYear = timelineStart.getFullYear() + Math.floor(qMonth / 12);
      headerLabels.push(`Q${(Math.floor(qMonth / 3) % 4) + 1} '${String(qYear).slice(-2)}`);
    }
  }

  nodes.push({
    id: 'timeline-header',
    type: 'timelineHeader',
    position: { x: TRACK_LABEL_WIDTH, y: 0 },
    data: {
      labels: headerLabels,
      unitWidth,
      totalUnits,
      scale,
    } as TimelineHeaderData as unknown as Record<string, unknown>,
    draggable: false,
    selectable: false,
  });

  // ── 2. Group campaigns by strategy track ──────────────────────────────
  const allCampaigns = [
    ...(data.phases?.immediate || []),
    ...(data.phases?.short_term || []),
    ...(data.phases?.mid_term || []),
    ...(data.phases?.long_term || []),
    ...(data.phases?.unphased || []),
  ];

  const trackMap: Record<string, RoadmapCampaign[]> = {};
  allCampaigns.forEach((c) => {
    const track = c.strategy_track || 'General';
    if (!trackMap[track]) trackMap[track] = [];
    trackMap[track].push(c);
  });

  const trackNames = Object.keys(trackMap);

  // ── 3. Swim lane labels + campaign bars ───────────────────────────────
  let currentY = TOP_OFFSET;

  trackNames.forEach((trackName, trackIdx) => {
    const campaigns = trackMap[trackName];
    const trackHeight = TRACK_HEADER_HEIGHT + campaigns.length * TRACK_HEIGHT;

    // Track lane label (left sidebar)
    nodes.push({
      id: `track-${trackIdx}`,
      type: 'trackLane',
      position: { x: 0, y: currentY },
      data: {
        name: trackName,
        campaignCount: campaigns.length,
        activeCount: campaigns.filter((c) => c.status === 'active').length,
        completedCount: campaigns.filter((c) => c.status === 'completed').length,
        height: trackHeight,
        width: totalWidth,
      } as TrackLaneData as unknown as Record<string, unknown>,
      draggable: false,
      selectable: false,
    });

    // Campaign bars within this track
    campaigns.forEach((campaign, campIdx) => {
      const timing = PHASE_TIMING[campaign.phase] || PHASE_TIMING.immediate;

      // Convert week-based timing to pixel position
      let barX: number;
      let barWidth: number;

      if (scale === 'weeks') {
        barX = TRACK_LABEL_WIDTH + timing.startWeek * unitWidth;
        barWidth = timing.durationWeeks * unitWidth;
      } else if (scale === 'months') {
        barX = TRACK_LABEL_WIDTH + (timing.startWeek / 4.33) * unitWidth;
        barWidth = (timing.durationWeeks / 4.33) * unitWidth;
      } else {
        barX = TRACK_LABEL_WIDTH + (timing.startWeek / 13) * unitWidth;
        barWidth = (timing.durationWeeks / 13) * unitWidth;
      }

      // Stagger bars within same phase/track so they don't fully overlap
      const stagger = campIdx * 12;

      const barY = currentY + TRACK_HEADER_HEIGHT + campIdx * TRACK_HEIGHT + BAR_Y_OFFSET;

      // Determine if this task is in the past (end week < today)
      const taskEndWeek = timing.startWeek + timing.durationWeeks;
      const isPast = taskEndWeek < weeksFromStart && campaign.status !== 'active';

      const nodeId = `bar-${campaign.id}`;
      nodes.push({
        id: nodeId,
        type: 'ganttBar',
        position: { x: barX + stagger, y: barY },
        style: { width: Math.max(barWidth - stagger, 100), height: BAR_HEIGHT },
        data: {
          campaign,
          width: Math.max(barWidth - stagger, 100),
          height: BAR_HEIGHT,
          isPast,
          onSelect: callbacks.onSelectCampaign,
        } as GanttBarData as unknown as Record<string, unknown>,
      });

      // ── Dependency edges within same track ──────────────────────────
      if (campIdx > 0) {
        const prevId = `bar-${campaigns[campIdx - 1].id}`;
        edges.push({
          id: `dep-${prevId}-${nodeId}`,
          source: prevId,
          target: nodeId,
          type: 'smoothstep',
          animated: false,
          style: { stroke: '#6b728060', strokeWidth: 1.5 },
        });
      }
    });

    currentY += trackHeight + TRACK_GAP;
  });

  // ── 4. "Today" vertical line ───────────────────────────────────────────
  let todayX: number;
  if (scale === 'weeks') {
    todayX = TRACK_LABEL_WIDTH + weeksFromStart * unitWidth;
  } else if (scale === 'months') {
    todayX = TRACK_LABEL_WIDTH + (weeksFromStart / 4.33) * unitWidth;
  } else {
    todayX = TRACK_LABEL_WIDTH + (weeksFromStart / 13) * unitWidth;
  }

  // Only show if "today" falls within the visible timeline
  if (todayX >= TRACK_LABEL_WIDTH && todayX <= totalWidth) {
    nodes.push({
      id: 'today-line',
      type: 'todayLine',
      position: { x: todayX, y: HEADER_HEIGHT },
      data: {
        height: currentY - HEADER_HEIGHT + 20,
        label: 'Today',
      } as TodayLineData as unknown as Record<string, unknown>,
      draggable: false,
      selectable: false,
      zIndex: 10,
    });
  }

  return { nodes, edges };
}

export function RoadmapCanvas({
  roadmapData,
  onSelectCampaign,
  // onGenerateCreative and onLaunchCampaign are handled in CampaignDetailPanel
  // when user clicks a bar → opens panel → clicks action buttons there.
}: RoadmapCanvasProps) {
  const [scale, setScale] = useState<TimelineScale>('months');

  const { nodes: computedNodes, edges: computedEdges } = useMemo(
    () => buildGanttElements(roadmapData, scale, { onSelectCampaign }),
    [roadmapData, scale, onSelectCampaign],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(computedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(computedEdges);

  // Sync nodes/edges when scale or roadmap data changes
  useEffect(() => {
    setNodes(computedNodes);
    setEdges(computedEdges);
  }, [computedNodes, computedEdges, setNodes, setEdges]);

  const handleScaleChange = useCallback((newScale: TimelineScale) => {
    setScale(newScale);
  }, []);

  return (
    <div className="w-full h-full flex flex-col">
      {/* Fixed header bar — outside React Flow so it doesn't move */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5 flex-shrink-0 bg-surface/40">
        <div>
          <h2 className="text-sm font-semibold text-white">{roadmapData.roadmap?.title}</h2>
          <p className="text-[10px] text-white/40 mt-0.5">
            {roadmapData.roadmap?.gtm_motion?.replace('_', ' ')} · {roadmapData.summary?.total_campaigns || 0} activities
            {roadmapData.roadmap?.executive_summary && (
              <span className="text-white/25"> · {roadmapData.roadmap.executive_summary.slice(0, 80)}…</span>
            )}
          </p>
        </div>
        {/* Scale switcher */}
        <div className="flex items-center bg-white/5 rounded-lg p-0.5">
          {(['weeks', 'months', 'quarters'] as TimelineScale[]).map((s) => (
            <button
              key={s}
              onClick={() => handleScaleChange(s)}
              className={`px-3 py-1.5 rounded-md text-[10px] font-medium transition-colors ${
                scale === s ? 'bg-white/10 text-white' : 'text-white/30 hover:text-white/50'
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Gantt chart — anchored to top-left, scroll to pan */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          defaultViewport={{ x: 0, y: 0, zoom: 0.75 }}
          minZoom={0.3}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
          className="bg-transparent"
          nodesDraggable={true}
          selectNodesOnDrag={false}
          panOnScroll={true}
          panOnDrag={true}
        >
          <Background color="#ffffff06" gap={SCALE_CONFIG[scale].unitWidth} size={1} lineWidth={1} />
          <Controls
            position="bottom-left"
            className="!bg-surface/80 !border-white/10 !rounded-xl [&>button]:!bg-surface/80 [&>button]:!border-white/10 [&>button]:!text-white/60 [&>button:hover]:!bg-white/10"
            showInteractive={false}
          />
        </ReactFlow>
      </div>
    </div>
  );
}
