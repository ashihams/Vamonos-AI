import { AnimatePresence, motion } from "framer-motion";
import { FolderGit2, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { REPO_URL } from "../../lib/links";
import { quick } from "../../lib/motion";
import { Button } from "../ui/Button";
import { Segmented } from "../ui/Segmented";
import { Logo } from "./Logo";

const LINKS = [
  { href: "#overview", label: "Overview" },
  { href: "#iterations", label: "Iterations" },
  { href: "#replay", label: "Approve" },
  { href: "#versions", label: "Versions" },
  { href: "#quality", label: "Quality" },
  { href: "#tasks", label: "Tasks" },
  { href: "#stack", label: "Stack" },
  { href: "#method", label: "Method" },
];

interface NavProps {
  runIds: string[];
  runId: string;
  onRunChange: (runId: string) => void;
}

export function Nav({ runIds, runId, onRunChange }: NavProps) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const runSwitch = (
    <Segmented
      label="Recorded run"
      size="sm"
      value={runId}
      onChange={onRunChange}
      options={runIds.map((id) => ({ value: id, label: id, hint: `Show run ${id}` }))}
    />
  );

  return (
    <header
      className={`sticky top-0 z-50 transition-[background-color,box-shadow,backdrop-filter] duration-300 ease-expo ${
        scrolled || open
          ? "bg-bg-base/70 shadow-[0_1px_0_0_rgba(255,255,255,0.06),0_8px_32px_rgba(0,0,0,0.4)] backdrop-blur-xl"
          : "bg-transparent"
      }`}
    >
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:rounded-md focus:bg-bg-elevated focus:px-3 focus:py-2">
        Skip to content
      </a>
      <nav aria-label="Primary" className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-5 md:px-8">
        <a href="#top" className="flex items-center gap-2.5 rounded-md">
          <Logo />
          <span className="text-[15px] font-semibold tracking-tight">costwise</span>
        </a>

        <ul className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="rounded-md px-3 py-1.5 text-sm text-fg-muted transition-colors duration-200 ease-expo hover:bg-white/[0.05] hover:text-fg"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="ml-auto hidden items-center gap-3 md:flex">
          {runSwitch}
          <Button href={REPO_URL} variant="secondary" icon={FolderGit2} external className="px-3 py-2">
            Source
          </Button>
        </div>

        <button
          type="button"
          className="ml-auto grid size-10 place-items-center rounded-lg text-fg-muted transition-colors hover:bg-white/[0.05] hover:text-fg md:hidden"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </nav>

      <AnimatePresence>
        {open && (
          <motion.div
            id="mobile-menu"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={quick}
            className="border-t border-line bg-bg-base/95 px-5 pb-6 pt-4 backdrop-blur-xl md:hidden"
          >
            <ul className="flex flex-col gap-1">
              {LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className="block rounded-lg px-3 py-2.5 text-base text-fg-muted transition-colors hover:bg-white/[0.05] hover:text-fg"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex flex-col gap-3">
              {runSwitch}
              <Button href={REPO_URL} icon={FolderGit2} external className="w-full">
                View source on FolderGit2
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
