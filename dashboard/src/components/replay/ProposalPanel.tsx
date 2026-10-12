import { Check, X } from "lucide-react";
import { Badge, type Tone } from "../ui/Badge";
import { ActionButton } from "../ui/Button";
import { humanize, signedPct } from "../../lib/format";
import type { IterationRecord } from "../../lib/types";

const RISK: Record<IterationRecord["proposal"]["risk"], Tone> = { low: "pass", medium: "warn", high: "block" };

interface ProposalPanelProps {
  record: IterationRecord;
  decided: boolean;
  onChoose: (choice: "approve" | "reject") => void;
}

/** The proposal as the approver sees it at the terminal, with the y/n decision. */
export function ProposalPanel({ record, decided, onChoose }: ProposalPanelProps) {
  const { proposal } = record;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="accent">{humanize(proposal.lever)}</Badge>
        <Badge tone={RISK[proposal.risk]}>{proposal.risk} risk</Badge>
        <Badge>predicted {signedPct(proposal.predicted_cost_change_pct)} cost</Badge>
      </div>

      <p className="label-mono mt-6 mb-2">Proposed value</p>
      <pre className="scrollbar-thin overflow-x-auto rounded-lg border border-white/10 bg-bg-input px-4 py-3 font-mono text-[13px] text-[#c7ccf7]">
        {JSON.stringify(proposal.new_value, null, 2)}
      </pre>

      <p className="label-mono mt-6 mb-2">The optimizer's reasoning</p>
      <p className="leading-relaxed text-fg-muted">{proposal.rationale}</p>

      <div className="mt-6 rounded-xl border border-line bg-bg-deep/70 p-4 font-mono text-[13px]">
        <p className="text-fg-muted">
          <span className="text-accent-bright">$</span> costwise optimize
        </p>
        <p className="mt-1 text-fg">apply this change? [y/n]</p>
        <div className="mt-4 flex flex-wrap gap-3 font-sans">
          <ActionButton icon={Check} onClick={() => onChoose("approve")} disabled={decided}>
            y · Approve
          </ActionButton>
          <ActionButton icon={X} variant="secondary" onClick={() => onChoose("reject")} disabled={decided}>
            n · Reject
          </ActionButton>
        </div>
        <p className="mt-3 font-sans text-xs text-fg-subtle">
          In the recording: {record.decision.approved ? "approved" : "declined"}
          {record.decision.note ? ` (“${record.decision.note}”)` : ""}.
        </p>
      </div>
    </div>
  );
}
