"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { BarChart3, Check, Code2, GitPullRequest, Minus, Monitor, Moon, Play, ShieldCheck, Sun, TerminalSquare, Wand2, X } from "lucide-react";
import { requests, type Check as Chk, type CheckState, type Mix } from "@/lib/requests";

export function Logo() {
  return (
    <span className="x-logo" aria-hidden>
      <svg viewBox="16 16 32 32">
        <path d="M18 44L32 18L46 44H38.5L32 31.5L25.5 44H18Z" fill="currentColor" />
        <circle cx="32" cy="43" r="4" fill="var(--green)" />
      </svg>
    </span>
  );
}

export function Brand() {
  return <Link href="/" className="x-brand"><Logo /><span>Aptura</span></Link>;
}

type Theme = "light" | "dark" | "system";
export function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>("system");
  useEffect(() => { try { setTheme((localStorage.getItem("aptura-theme") as Theme) || "system"); } catch {} }, []);
  const apply = (t: Theme) => {
    setTheme(t);
    try { localStorage.setItem("aptura-theme", t); } catch {}
    if (t === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
  };
  const opts: [Theme, ReactNode, string][] = [["light", <Sun key="s" />, "Light theme"], ["dark", <Moon key="m" />, "Dark theme"], ["system", <Monitor key="c" />, "Match system theme"]];
  return (
    <div className="x-theme" role="group" aria-label="Theme">
      {opts.map(([t, icon, label]) => <button key={t} aria-label={label} aria-pressed={theme === t} onClick={() => apply(t)}>{icon}</button>)}
    </div>
  );
}

export function Odometer({ value, run = true }: { value: string; run?: boolean }) {
  const [go, setGo] = useState(false);
  useEffect(() => { if (!run) return; const t = setTimeout(() => setGo(true), 250); return () => clearTimeout(t); }, [run]);
  return (
    <span className="x-odo num" aria-label={value}>
      {value.split("").map((ch, i) =>
        /\d/.test(ch) ? (
          <span key={i} className="x-odo-col" aria-hidden style={{ transform: `translateY(-${go ? Number(ch) : 0}em)`, transitionDelay: `${i * 160}ms` }}>
            {Array.from({ length: 10 }, (_, d) => <span key={d}>{d}</span>)}
          </span>
        ) : <span key={i} aria-hidden>{ch}</span>,
      )}
    </span>
  );
}

/** Sparkline from real values. */
export function Spark({ values, red = false }: { values: number[]; red?: boolean }) {
  if (values.length < 2) return null;
  const w = 96, h = 34, min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, h - 3 - ((v - min) / span) * (h - 6)]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  let len = 0;
  for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  const last = pts[pts.length - 1];
  return (
    <svg className="x-spark" viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <path className={`l ${red ? "red" : ""}`} d={d} style={{ ["--len" as string]: Math.ceil(len) }} />
      <circle className={red ? "red" : ""} cx={last[0]} cy={last[1]} r="2.6" />
    </svg>
  );
}

/** The "diff" of a request: momentum share in ink, reversal share in grey, limits dashed at 15% and 85%. */
export function MixBar({ mix, label, large = false, animate = true }: { mix: Mix; label?: string; large?: boolean; animate?: boolean }) {
  const [go, setGo] = useState(!animate);
  useEffect(() => { if (!animate) return; const t = setTimeout(() => setGo(true), 300); return () => clearTimeout(t); }, [animate]);
  const m = Math.round(mix.momentum * 100);
  const bad = mix.momentum < 0.15 || mix.momentum > 0.85;
  const bar = (
    <div className={`a-mixbar ${large ? "lg" : ""} ${bad ? "bad" : ""}`} role="img" aria-label={`${m}% momentum, ${100 - m}% reversal`}>
      <i className="m" style={{ flexBasis: `${go ? m : 50}%` }}>{m >= 12 ? `${m}%` : ""}</i>
      <i className="r">{100 - m >= 12 ? `${100 - m}%` : ""}</i>
      <span className="lim" style={{ left: "15%" }} /><span className="lim" style={{ left: "85%" }} />
    </div>
  );
  if (!label) return bar;
  return <div className="a-mix-row"><span>{label}</span>{bar}</div>;
}

export function StatusIcon({ tone }: { tone: "ok" | "no" | "warn" | "idle" }) {
  return <span className={`a-status ${tone}`}>{tone === "ok" ? <Check /> : tone === "no" ? <X /> : tone === "warn" ? <Minus /> : null}</span>;
}

export function CheckDots({ checks }: { checks: Chk[] }) {
  const cls: Record<CheckState, string> = { pass: "pass", fail: "fail", warn: "warn", skip: "skip" };
  return <div className="a-dots">{checks.map((c) => <span key={c.gate} className={`a-dot ${cls[c.state]}`} title={`${c.name}: ${c.detail}`}>{c.gate}</span>)}</div>;
}

const TABS: [string, string, ReactNode, number?][] = [
  ["/requests", "Requests", <GitPullRequest key="q" />, requests.length],
  ["/judge", "Try it", <Wand2 key="t" />],
  ["/evaluation", "Replays", <BarChart3 key="r" />],
  ["/proof", "Verify", <ShieldCheck key="v" />],
  ["/terminal?scenario=momentum-breakdown&autorun=1", "Terminal", <TerminalSquare key="x" />],
  ["/developers", "API", <Code2 key="a" />],
];

export function TopBar() {
  const path = usePathname();
  const active = (href: string) => {
    const p = href.split("?")[0];
    return path === p || (p !== "/" && path.startsWith(p + "/"));
  };
  return (
    <header className="a-bar">
      <div className="a-bar-in">
        <Brand />
        <nav className="a-tabs" aria-label="Main">
          {TABS.map(([href, label, icon, count]) => (
            <Link key={href} href={href} className="a-tab" aria-current={active(href) ? "page" : undefined}>
              {icon}{label}{count ? <span className="count">{count}</span> : null}
            </Link>
          ))}
        </nav>
        <div className="a-bar-end">
          <ThemeSwitch />
          <Link href="/terminal?scenario=momentum-breakdown&autorun=1" className="x-btn sm"><Play size={14} />Run demo</Link>
        </div>
      </div>
    </header>
  );
}

export function Page({ children }: { children: ReactNode }) {
  return (
    <div className="x-root">
      <TopBar />
      <main className="a-wrap">{children}</main>
      <Foot />
    </div>
  );
}

export function Foot() {
  return (
    <footer className="a-foot">
      <span>Paper trading only</span>
      <span style={{ display: "flex", gap: 18 }}><Link href="/developers">API</Link><span>OpenServ SERV · Reppo</span></span>
    </footer>
  );
}
