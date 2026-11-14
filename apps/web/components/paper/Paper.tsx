"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

export function useInView<T extends Element>(threshold = 0.35) {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (typeof IntersectionObserver === "undefined") { setSeen(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect(); } }, { threshold });
    io.observe(el);
    return () => io.disconnect();
  }, [seen, threshold]);
  return [ref, seen] as const;
}

export function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(m.matches);
  }, []);
  return reduced;
}

/** Counts 0..n on a fixed mechanical beat once `run` is true. */
export function useTicker(n: number, run: boolean, beatMs = 140, delayMs = 0) {
  const [count, setCount] = useState(0);
  const reduced = useReducedMotion();
  useEffect(() => {
    if (!run) return;
    if (reduced) { setCount(n); return; }
    setCount(0);
    let i = 0;
    let timer: ReturnType<typeof setTimeout>;
    const step = () => { i += 1; setCount(i); if (i < n) timer = setTimeout(step, beatMs); };
    timer = setTimeout(step, delayMs);
    return () => clearTimeout(timer);
  }, [n, run, beatMs, delayMs, reduced]);
  return count;
}

/** Rough-ink filter for stamps. Render once per page. */
export function InkFilter() {
  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
      <filter id="p-ink">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="n" />
        <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.5 1.55" result="speck" />
        <feComposite in="SourceGraphic" in2="speck" operator="in" result="inked" />
        <feTurbulence type="turbulence" baseFrequency="0.04" numOctaves="1" seed="3" result="w" />
        <feDisplacementMap in="inked" in2="w" scale="2.4" />
      </filter>
    </svg>
  );
}

export function PaperNav() {
  const path = usePathname();
  const links: [string, string, string?][] = [["/judge", "Judge"], ["/proof", "Proof"], ["/evaluation", "Results"], ["/terminal?scenario=momentum-breakdown&autorun=1", "Terminal", "hide-sm"]];
  return (
    <header className="p-wrap p-nav">
      <Link href="/" className="p-mark" aria-label="Aptura home">aptura<i>.</i></Link>
      <nav aria-label="Main">
        {links.map(([href, label, cls]) => (
          <Link key={href} href={href} className={cls} aria-current={path === href.split("?")[0] ? "page" : undefined}>{label}</Link>
        ))}
      </nav>
    </header>
  );
}

export type Line =
  | { k: string; v: ReactNode; tone?: "strong" | "hit" }
  | { rule: true }
  | { quote: ReactNode }
  | { title: ReactNode };

export function Receipt({
  head, lines, stamp, stampNote, holes = 0, run, beatMs = 150, onDone,
}: {
  head: [ReactNode, ReactNode];
  lines: Line[];
  stamp?: "BLOCKED" | "SHIP" | "REVIEW";
  stampNote?: string;
  holes?: number;
  run: boolean;
  beatMs?: number;
  onDone?: () => void;
}) {
  const shown = useTicker(lines.length + 4, run, beatMs);
  const stamped = shown >= lines.length + 4;
  const [shake, setShake] = useState(false);
  useEffect(() => {
    if (!stamped) return;
    setShake(true);
    const t = setTimeout(() => { setShake(false); onDone?.(); }, 1600);
    return () => clearTimeout(t);
  }, [stamped]); // eslint-disable-line react-hooks/exhaustive-deps
  const holesOn = Math.min(holes, Math.floor((shown / Math.max(1, lines.length)) * holes));
  return (
    <div className={`p-receipt ${stamp ? "has-stamp" : ""} ${shake ? "shake" : ""}`}>
      <header><span>{head[0]}</span><span>{head[1]}</span></header>
      {lines.slice(0, shown).map((l, i) => {
        const on = " on";
        if ("rule" in l) return <div key={i} className={`p-line rule p-print-line${on}`} />;
        if ("quote" in l) return <p key={i} className={`p-quote p-print-line${on}`}>{l.quote}</p>;
        if ("title" in l) return <h3 key={i} className={`p-print-line${on}`}>{l.title}</h3>;
        return (
          <div key={i} className={`p-line ${l.tone ?? ""} p-print-line${on}`}>
            <span>{l.k}</span><span>{l.v}</span>
          </div>
        );
      })}
      {holes > 0 && <div className="holes" aria-hidden>{Array.from({ length: holes }, (_, i) => <i key={i} className={`p-hole ${i < holesOn ? "on" : ""}`} />)}</div>}
      {stamp && (
        <div className={`p-stamp ${stamp === "SHIP" ? "ship" : ""} ${stamped ? "on" : ""}`} role="status">
          {stamp}{stampNote && <small>{stampNote}</small>}
        </div>
      )}
    </div>
  );
}

/** Mechanical odometer: each digit rolls on a stepped track. */
export function Odometer({ value, run, className = "" }: { value: string; run: boolean; className?: string }) {
  return (
    <span className={`p-odo ${className}`} aria-label={value}>
      {value.split("").map((ch, i) =>
        /\d/.test(ch) ? (
          <span key={i} className="p-odo-col" aria-hidden style={{ transform: `translateY(-${run ? Number(ch) : 0}em)`, transitionDelay: `${i * 90}ms` }}>
            {Array.from({ length: 10 }, (_, d) => <span key={d}>{d}</span>)}
          </span>
        ) : (
          <span key={i} className="p-odo-static" aria-hidden>{ch}</span>
        ),
      )}
    </span>
  );
}

export function PaperFoot() {
  return (
    <footer className="p-wrap p-foot">
      <div className="p-fine">
        <div>Paper trading only. No wallet, no exchange keys, no real orders.</div>
        <div>Reppo scores reasoning, not profit.</div>
        <div>3 real markets × 199 hourly candles + 1 synthetic. Too few to claim an edge.</div>
        <div>Market data: GeckoTerminal. Reasoning: OpenServ SERV. Review: Reppo.</div>
        <div>OpenServ Hackathon 02 · Reppo track</div>
        <div><Link href="/llms.txt">llms.txt</Link> · <Link href="/api/agent/manifest">manifest</Link></div>
      </div>
      <Link href="/" className="p-mark">aptura<i>.</i></Link>
    </footer>
  );
}
