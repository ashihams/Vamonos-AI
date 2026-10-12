import { CFO_URL, ENTIRE_URL, NEATLOGS_URL, REPO_URL } from "../../lib/links";
import { Logo } from "./Logo";

const LINKS = [
  { href: REPO_URL, label: "GitHub" },
  { href: NEATLOGS_URL, label: "neatlogs" },
  { href: ENTIRE_URL, label: "Entire checkpoint" },
  { href: CFO_URL, label: "cfo.ai model" },
];

export function Footer() {
  return (
    <footer className="relative border-t border-line bg-bg-deep">
      <div aria-hidden className="hairline absolute inset-x-0 -top-px h-px" />
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-5 py-12 md:flex-row md:items-center md:justify-between md:px-8">
        <div className="flex items-center gap-3">
          <Logo className="size-8" />
          <div>
            <p className="font-semibold tracking-tight">costwise</p>
            <p className="text-sm text-fg-muted">Built for neatHack 2026. Data: recorded runs, exported with <code className="font-mono text-xs">costwise dashboard</code>.</p>
          </div>
        </div>
        <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          {LINKS.map((link) => (
            <li key={link.label}>
              <a href={link.href} target="_blank" rel="noreferrer" className="text-fg-muted transition-colors duration-200 hover:text-fg">
                {link.label}
                <span className="sr-only"> (opens in a new tab)</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </footer>
  );
}
