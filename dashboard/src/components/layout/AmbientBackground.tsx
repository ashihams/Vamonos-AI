/** Fixed backdrop: base radial gradient, four light pools, a 64px grid, and film noise. */
export function AmbientBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,#0a0a0f_0%,#050506_50%,#020203_100%)]" />

      <div className="absolute -top-[520px] left-1/2 h-[1400px] w-[900px] -translate-x-1/2 animate-float rounded-full bg-accent/25 blur-[150px]" />
      <div className="absolute top-[20%] -left-[260px] h-[800px] w-[600px] animate-float-slow rounded-full bg-[linear-gradient(140deg,rgba(168,85,247,0.15),rgba(236,72,153,0.1))] blur-[120px]" />
      <div className="absolute top-[45%] -right-[200px] h-[700px] w-[500px] animate-float rounded-full bg-[linear-gradient(200deg,rgba(99,102,241,0.12),rgba(59,130,246,0.1))] blur-[100px] [animation-delay:-4s]" />
      <div className="absolute -bottom-[300px] left-1/3 h-[600px] w-[900px] animate-pulse-glow rounded-full bg-accent/10 blur-[140px]" />

      <div className="bg-grid absolute inset-0 opacity-[0.02] [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]" />
      <div className="bg-noise absolute inset-0 opacity-[0.015]" />
    </div>
  );
}
