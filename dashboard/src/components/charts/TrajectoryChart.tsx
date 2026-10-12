import { motion, useReducedMotion } from "framer-motion";
import { useRef } from "react";
import { num, pct, usd } from "../../lib/format";
import { EXPO_OUT } from "../../lib/motion";
import type { VersionStats } from "../../lib/types";
import { useElementSize } from "../../lib/useElementSize";

const PAD = { top: 30, right: 36, bottom: 46, left: 62 };
const HEADROOM = 1.18;

const STATUS_STYLE: Record<VersionStats["status"], { fill: string; stroke: string; label: string }> = {
  baseline: { fill: "#5e6ad2", stroke: "#a5acf0", label: "baseline" },
  kept: { fill: "#4cc38a", stroke: "#4cc38a", label: "kept" },
  "rolled back": { fill: "#050506", stroke: "#e5484d", label: "rolled back" },
};

/** Cost per successful task for every evaluated version, in evaluation order, drawn at the container's pixel size. */
export function TrajectoryChart({ versions }: { versions: VersionStats[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const { width, height } = useElementSize(ref);
  return (
    <div ref={ref} className="h-full w-full">
      {width > 0 && height > 0 && <Plot versions={versions} width={width} height={height} />}
    </div>
  );
}

function Plot({ versions, width: W, height: H }: { versions: VersionStats[]; width: number; height: number }) {
  const reduce = useReducedMotion();
  const values = versions.map((v) => num(v.cost_per_successful_task));
  const top = Math.max(...values.filter(Number.isFinite)) * HEADROOM;
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (versions.length === 1 ? innerW / 2 : (i / (versions.length - 1)) * innerW);
  const yOf = (value: number) => PAD.top + innerH - (value / top) * innerH;
  const points = values.map((value, i) => ({ x: x(i), y: yOf(value), value, stats: versions[i]! }));
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const floor = PAD.top + innerH;
  const area = `${path} L${points.at(-1)!.x},${floor} L${points[0]!.x},${floor} Z`;
  const baselineY = yOf(values[0] ?? 0);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => top * f);
  const summary = points.map((p) => `v${p.stats.version} ${p.stats.status}: ${usd(p.value, 4)} per successful task`).join("; ");

  return (
    <svg width={W} height={H} role="img" aria-label={`Cost per successful task by version. ${summary}`} className="overflow-visible">
      <defs>
        <linearGradient id="traj-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#5e6ad2" stopOpacity="0.3" />
          <stop offset="1" stopColor="#5e6ad2" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="traj-line" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#a5acf0" />
          <stop offset="1" stopColor="#5e6ad2" />
        </linearGradient>
        <filter id="traj-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
      </defs>

      {ticks.map((tick) => (
        <g key={tick}>
          <line x1={PAD.left} x2={W - PAD.right} y1={yOf(tick)} y2={yOf(tick)} stroke="rgba(255,255,255,0.05)" />
          <text x={PAD.left - 12} y={yOf(tick) + 4} textAnchor="end" className="fill-fg-muted font-mono text-[11px]">
            ${tick.toFixed(3)}
          </text>
        </g>
      ))}

      <line x1={PAD.left} x2={W - PAD.right} y1={baselineY} y2={baselineY} stroke="#5e6ad2" strokeOpacity="0.55" strokeDasharray="4 6" />

      <motion.path
        d={area}
        fill="url(#traj-area)"
        initial={reduce ? false : { opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.8, delay: 0.3, ease: EXPO_OUT }}
      />
      <path d={path} fill="none" stroke="url(#traj-line)" strokeWidth="6" strokeOpacity="0.45" filter="url(#traj-glow)" />
      <motion.path
        d={path}
        fill="none"
        stroke="url(#traj-line)"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={reduce ? false : { pathLength: 0 }}
        whileInView={{ pathLength: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 1.1, ease: EXPO_OUT }}
      />

      {points.map((p, i) => {
        const style = STATUS_STYLE[p.stats.status];
        const anchor = i === 0 && points.length > 1 ? "start" : i === points.length - 1 && points.length > 1 ? "end" : "middle";
        const labelX = anchor === "start" ? p.x - 6 : anchor === "end" ? p.x + 6 : p.x;
        return (
          <motion.g
            key={p.stats.version}
            initial={reduce ? false : { opacity: 0, y: 6 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.25 + i * 0.12, ease: EXPO_OUT }}
          >
            <circle cx={p.x} cy={p.y} r="14" fill={style.stroke} opacity="0.14" />
            <circle cx={p.x} cy={p.y} r="6" fill={style.fill} stroke={style.stroke} strokeWidth="2" />
            <text x={labelX} y={p.y - 18} textAnchor={anchor} className="fill-fg font-mono text-[12px] font-medium">
              {usd(p.value, 4)}
            </text>
            <text x={labelX} y={H - 24} textAnchor={anchor} className="fill-fg font-mono text-[12px]">
              v{p.stats.version}
            </text>
            <text x={labelX} y={H - 8} textAnchor={anchor} className="fill-fg-muted text-[10.5px]">
              {style.label} · held-out {pct(p.stats.heldout_success_rate, 0)}
            </text>
          </motion.g>
        );
      })}
    </svg>
  );
}
