import { motion } from "framer-motion";
import { ArrowUpRight, Bot, Calculator, Cloud, Cpu, Database, GitCommitHorizontal, type LucideIcon } from "lucide-react";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Section } from "../components/ui/Section";
import { CFO_URL, ENTIRE_URL, NEATLOGS_URL } from "../lib/links";
import { stagger } from "../lib/motion";

const TRACE = [
  { depth: 0, kind: "workflow", name: "qualify_company", note: "session = run id · user = company domain" },
  { depth: 1, kind: "tool", name: "fetch_company_data", note: "cache hit, credits, data cost" },
  { depth: 1, kind: "llm", name: "chat claude-sonnet-4.6", note: "tokens · cost_usd" },
  { depth: 1, kind: "evaluator", name: "score_against_label", note: "success, difficulty" },
  { depth: 0, kind: "agent", name: "optimizer_iteration", note: "input = proposal · output = decision" },
  { depth: 1, kind: "guardrail", name: "human_approval", note: "passed / blocked" },
  { depth: 1, kind: "evaluator", name: "evaluate_candidate", note: "success rate, unit cost, p95" },
  { depth: 1, kind: "guardrail", name: "guardrail heldout_success", note: "passed / blocked" },
] as const;

const KIND_COLOR: Record<(typeof TRACE)[number]["kind"], string> = {
  workflow: "text-[#b4bbf5] border-line-accent bg-accent/10",
  agent: "text-[#b4bbf5] border-line-accent bg-accent/10",
  tool: "text-[#7dd3fc] border-[#38bdf8]/30 bg-[#38bdf8]/10",
  llm: "text-[#c4b5fd] border-[#a78bfa]/30 bg-[#a78bfa]/10",
  evaluator: "text-pass border-pass/30 bg-pass/10",
  guardrail: "text-warn border-warn/30 bg-warn/10",
};

export function Stack() {
  return (
    <Section
      id="stack"
      label="05 · Stack"
      title="Observed, versioned, and costed"
      description="Every task and every optimizer decision is traced in neatlogs. The build itself is checkpointed in Entire, and the economics are modeled in cfo.ai from the measured run."
    >
      <motion.div variants={stagger} className="grid grid-cols-1 gap-4 md:grid-cols-6 md:auto-rows-[minmax(180px,auto)]">
        <Card variant="gradient" className="md:col-span-4 md:row-span-2">
          <div className="flex h-full flex-col p-6 md:p-8">
            <Header icon={Bot} label="neatlogs" title="Every task and decision is a trace" href={NEATLOGS_URL} />
            <p className="mt-3 max-w-xl text-sm leading-relaxed text-fg-muted">
              Spans use the attribute names from the neatlogs SDK's attribute map, so the dashboard shows each span's kind, its JSON input
              and output, token counts, per-call cost, and passed or blocked guardrails.
            </p>
            <ul className="mt-6 flex flex-col gap-1.5 rounded-xl border border-line bg-bg-elevated/80 p-4 font-mono text-[12px] shadow-inner-hi">
              {TRACE.map((span, index) => (
                <li key={index} className="flex flex-wrap items-center gap-x-3 gap-y-1" style={{ paddingLeft: span.depth * 22 }}>
                  {span.depth > 0 && <span aria-hidden className="text-white/20">└</span>}
                  <span className={`rounded border px-1.5 py-px text-[10px] tracking-wider uppercase ${KIND_COLOR[span.kind]}`}>{span.kind}</span>
                  <span className="text-fg">{span.name}</span>
                  <span className="text-fg-muted">{span.note}</span>
                </li>
              ))}
            </ul>
          </div>
        </Card>

        <Card className="md:col-span-2">
          <Tile
            icon={GitCommitHorizontal}
            label="Entire"
            title="Build checkpoints"
            body="One build-notes commit per stage PR, each carrying the chat that wrote it as an Entire checkpoint."
            href={ENTIRE_URL}
            cta="Open checkpoint"
          />
        </Card>
        <Card className="md:col-span-2">
          <Tile
            icon={Calculator}
            label="cfo.ai"
            title="Unit economics"
            body="Built from this project's measured costs. Price per task and volume are labeled assumptions."
            href={CFO_URL}
            cta="Open the model"
          />
        </Card>

        <Card className="md:col-span-2">
          <Tile icon={Cpu} label="LiteLLM" title="Two model tiers" body="claude-haiku as the cheap tier, claude-sonnet-4.6 as the strong tier, priced at the proxy's own rates." />
        </Card>
        <Card className="md:col-span-2">
          <Tile icon={Database} label="Crustdata" title="Company data" body="Company enrich at 2 credits per lookup, frozen as fixtures so every version sees the same data." />
        </Card>
        <Card className="md:col-span-2">
          <Tile
            icon={Cloud}
            label="AWS Lambda"
            title="Smoke-tested on AWS"
            body="A 3-task run on the deployed function measured infra from billed duration; the function was torn down after. The runs shown here used the local runner, so their infra is modeled."
          />
        </Card>
      </motion.div>
    </Section>
  );
}

function Header({ icon: Icon, label, title, href }: { icon: LucideIcon; label: string; title: string; href?: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="label-mono flex items-center gap-2">
          <Icon aria-hidden className="size-3.5 text-[#a5acf0]" />
          {label}
        </p>
        <h3 className="mt-3 text-xl font-semibold tracking-tight md:text-2xl">{title}</h3>
      </div>
      {href && (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          aria-label={`Open ${label} (opens in a new tab)`}
          className="grid size-9 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-fg-muted transition-[color,background-color,transform] duration-200 ease-expo hover:-translate-y-0.5 hover:bg-white/[0.08] hover:text-fg"
        >
          <ArrowUpRight className="size-4" />
        </a>
      )}
    </div>
  );
}

interface TileProps {
  icon: LucideIcon;
  label: string;
  title: string;
  body: string;
  href?: string;
  cta?: string;
  badge?: string;
}

function Tile({ icon, label, title, body, href, cta, badge }: TileProps) {
  return (
    <div className="flex h-full flex-col p-6">
      <Header icon={icon} label={label} title={title} href={href} />
      <p className="mt-3 text-sm leading-relaxed text-fg-muted">{body}</p>
      <div className="mt-auto pt-4">
        {badge && <Badge tone="warn">{badge}</Badge>}
        {href && cta && (
          <a href={href} target="_blank" rel="noreferrer" className="text-sm font-medium text-[#b4bbf5] underline-offset-4 hover:underline">
            {cta} →<span className="sr-only"> (opens in a new tab)</span>
          </a>
        )}
      </div>
    </div>
  );
}
