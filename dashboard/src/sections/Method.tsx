import { motion } from "framer-motion";
import { Card } from "../components/ui/Card";
import { Section } from "../components/ui/Section";
import { stagger } from "../lib/motion";

const ITEMS = [
  {
    tag: "measured",
    title: "Model cost",
    body: "Input and output tokens returned by every call, multiplied by the LiteLLM proxy's per-token prices read on 2026-10-12.",
  },
  {
    tag: "modeled",
    title: "Infrastructure cost",
    body: "Wall time times configured Lambda prices, because these runs used the local runner. The Lambda runner would measure it from billed duration.",
  },
  {
    tag: "assumption",
    title: "Data cost",
    body: "Crustdata credits per lookup times a configured price per credit, currently $0 because the hackathon credits were free.",
  },
  {
    tag: "rule-based",
    title: "Success",
    body: "The model's answer must match the ICP rule's label. Held-out tasks are never shown to the optimizer, so a change cannot overfit them.",
  },
];

const TAG_STYLE: Record<string, string> = {
  measured: "text-pass border-pass/30 bg-pass/10",
  modeled: "text-[#c4b5fd] border-[#a78bfa]/30 bg-[#a78bfa]/10",
  assumption: "text-warn border-warn/30 bg-warn/10",
  "rule-based": "text-[#b4bbf5] border-line-accent bg-accent/10",
};

export function Method() {
  return (
    <Section
      id="method"
      label="06 · Method"
      title="What is measured, and what is not"
      description="Small workload, real calls. Differences of a few points are within noise; one held-out miss is a 20-point drop."
    >
      <motion.ul variants={stagger} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {ITEMS.map((item) => (
          <Card as="li" key={item.title} className="p-6">
            <span className={`inline-block rounded-full border px-2.5 py-0.5 font-mono text-[10.5px] tracking-widest uppercase ${TAG_STYLE[item.tag]}`}>
              {item.tag}
            </span>
            <h3 className="mt-4 text-lg font-semibold tracking-tight">{item.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-fg-muted">{item.body}</p>
          </Card>
        ))}
      </motion.ul>
    </Section>
  );
}
