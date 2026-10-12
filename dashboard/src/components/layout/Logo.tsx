export function Logo({ className = "size-7" }: { className?: string }) {
  return (
    <span className={`grid place-items-center rounded-lg bg-bg-elevated shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_0_20px_rgba(94,106,210,0.35),inset_0_1px_0_0_rgba(255,255,255,0.1)] ${className}`}>
      <svg viewBox="0 0 32 32" aria-hidden className="size-[70%]">
        <defs>
          <linearGradient id="logo-g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#a5acf0" />
            <stop offset="1" stopColor="#5e6ad2" />
          </linearGradient>
        </defs>
        <path d="M6 22 12.5 14l5 4.5L26 8" fill="none" stroke="url(#logo-g)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}
