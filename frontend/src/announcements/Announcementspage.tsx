import { useCallback, useEffect, useState } from "react";

/* ───────────── types ───────────── */
type Announcement = {
  id: number;
  symbol: string;
  company_name: string;
  logo_url: string;
  title: string;
  type: string;
  category: string;
  source: string;
  details_url: string;
  published_at: string;
};
type Opt = { value: string; label: string };
type Options = {
  is_event: Opt[]; type: Opt[]; source: Opt[]; category: Opt[]; symbols: string[];
};
type Filters = {
  symbol: string; is_event: string; type: string; source: string; category: string;
  date_from: string; date_to: string;
};

const EMPTY: Filters = {
  symbol: "", is_event: "", type: "", source: "", category: "", date_from: "", date_to: "",
};

/* ───────────── helpers ───────────── */
// Sends your login token and never uses a cached answer.
const authFetch = (url: string) =>
  fetch(url, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` },
  });

// Some APIs wrap the answer like { success: true, data: {...} }. Handle both.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (d: any) => (d && d.data && !d.results && !d.symbols ? d.data : d);

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// "04 Nov 2026, 09:46 AM" in Nepal time
const fmt = (iso: string) => {
  const p = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kathmandu", day: "2-digit", month: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: true,
  }).formatToParts(new Date(iso));
  const g = (t: string) => p.find((x) => x.type === t)?.value ?? "";
  return `${g("day")} ${MONTHS[Number(g("month")) - 1]} ${g("year")}, ${g("hour")}:${g("minute")} ${g("dayPeriod").toUpperCase()}`;
};

const AVATARS = [
  "bg-sky-500/15 text-sky-600", "bg-emerald-500/15 text-emerald-600",
  "bg-violet-500/15 text-violet-600", "bg-amber-500/15 text-amber-600",
  "bg-rose-500/15 text-rose-600", "bg-teal-500/15 text-teal-600",
  "bg-indigo-500/15 text-indigo-600", "bg-orange-500/15 text-orange-600",
];
const avatarCls = (s: string) =>
  AVATARS[[...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) % AVATARS.length];

const TYPE_PILL: Record<string, { label: string; cls: string }> = {
  Announcement: { label: "Announcement", cls: "bg-sky-500/15 text-sky-600" },
  AnnouncementAndEvent: { label: "Announcement & Event", cls: "bg-violet-500/15 text-violet-600" },
  Event: { label: "Event", cls: "bg-amber-500/15 text-amber-600" },
  NewsAndAlert: { label: "News & Alert", cls: "bg-emerald-500/15 text-emerald-600" },
};

/* ───────────── tiny icons (no extra package needed) ───────────── */
const Icon = ({ d, className = "h-4 w-4" }: { d: string; className?: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
    <path d={d} />
  </svg>
);
const CLOCK = "M12 6v6l4 2M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z";
const RESET = "M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5";
const CHEVRON = "M6 9l6 6 6-6";
const ARROW = "M9 6l6 6-6 6";

/* ───────────── small components ───────────── */
const controlCls =
  "h-10 w-full appearance-none rounded-lg border border-bg-border bg-bg-elevated pl-3 pr-9 text-sm text-text-primary outline-none transition focus:border-accent";

function Select({ label, value, onChange, options, className = "" }: {
  label: string; value: string; onChange: (v: string) => void; options: Opt[]; className?: string;
}) {
  return (
    <div className={`relative ${className}`}>
      <select className={`${controlCls} ${value ? "border-accent/50" : ""}`}
        value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>
        <option value="">{label}: All</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <Icon d={CHEVRON} className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-text-muted" />
    </div>
  );
}

function Avatar({ a }: { a: Announcement }) {
  const [bad, setBad] = useState(false);
  if (a.logo_url && !bad) {
    return <img src={a.logo_url} alt="" onError={() => setBad(true)}
      className="h-11 w-11 shrink-0 rounded-lg bg-white/90 object-contain p-1" />;
  }
  const label = (a.symbol || "NEPSE").slice(0, 3);
  return (
    <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${avatarCls(a.symbol || "NEPSE")}`}>
      {label}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="card h-[190px]">
      <div className="flex gap-3">
        <div className="skeleton h-11 w-11" />
        <div className="flex-1 space-y-2">
          <div className="skeleton h-3 w-16" />
          <div className="skeleton h-3 w-3/4" />
        </div>
      </div>
      <div className="skeleton mt-5 h-3 w-1/2" />
      <div className="skeleton mt-3 h-4 w-full" />
      <div className="skeleton mt-2 h-4 w-2/3" />
    </div>
  );
}

function Card({ a }: { a: Announcement }) {
  const pill = TYPE_PILL[a.type];
  return (
    <article className="card group flex flex-col">
      <div className="flex items-center gap-3">
        <Avatar a={a} />
        <div className="min-w-0">
          <span className="inline-block rounded-md bg-bg-elevated px-2 py-0.5 text-xs font-bold tracking-wide text-text-primary">
            {a.symbol || "NEPSE"}
          </span>
          <p className="mt-1 truncate text-[13px] text-text-secondary" title={a.company_name}>
            {a.company_name || "Nepal Stock Exchange"}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1">
        {pill && (
          <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${pill.cls}`}>{pill.label}</span>
        )}
        <span className="text-[10.5px] font-semibold uppercase tracking-wide text-accent">
          {[a.source, a.category].filter(Boolean).join(" • ")}
        </span>
      </div>

      <h2 className="mt-2 line-clamp-3 flex-1 text-[15px] font-semibold leading-snug text-text-primary" title={a.title}>
        {a.title}
      </h2>

      <div className="mt-4 flex items-center justify-between border-t border-bg-border pt-3 text-xs">
        <span className="flex items-center gap-1.5 text-text-secondary">
          <Icon d={CLOCK} className="h-3.5 w-3.5" /> {fmt(a.published_at)}
        </span>
        {a.details_url ? (
          <a href={a.details_url} target="_blank" rel="noreferrer"
            className="flex items-center gap-0.5 font-semibold uppercase tracking-wide text-accent-light">
            View details <Icon d={ARROW} className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
          </a>
        ) : (
          <span className="text-text-muted">No attachment</span>
        )}
      </div>
    </article>
  );
}

/* ───────────── page ───────────── */
export default function AnnouncementsPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [options, setOptions] = useState<Options | null>(null);
  const [items, setItems] = useState<Announcement[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const size = 12;

  useEffect(() => {
    authFetch("/api/announcements/filters/")
      .then((r) => { if (!r.ok) throw new Error(`filters ${r.status}`); return r.json(); })
      .then((d) => setOptions(unwrap(d)))
      .catch((e) => setError(`Could not load filters (${e.message})`));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const qs = new URLSearchParams({ page: String(page), size: String(size) });
    Object.entries(filters).forEach(([k, v]) => v && qs.set(k, v));
    try {
      const r = await authFetch(`/api/announcements/?${qs}`);
      if (!r.ok) throw new Error(`status ${r.status}`);
      const d = unwrap(await r.json());
      setItems(d.results ?? d.content ?? []);
      setTotal(d.count ?? d.totalItems ?? 0);
    } catch (e) {
      setError(`Could not load announcements (${(e as Error).message})`);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => { load(); }, [load]);

  const set = (k: keyof Filters) => (v: string) => { setPage(1); setFilters((f) => ({ ...f, [k]: v })); };
  const reset = () => { setPage(1); setFilters(EMPTY); };
  const hasFilters = Object.values(filters).some(Boolean);
  const pages = Math.max(1, Math.ceil(total / size));

  return (
    <div className="rounded-2xl border border-bg-border bg-bg-card p-5 text-text-primary sm:p-6">
      {/* header */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="rounded-lg bg-bg-elevated px-4 py-2 text-lg font-bold">Announcements</h1>
          {!loading && !error && (
            <span className="text-sm text-text-muted">{total.toLocaleString()} result{total === 1 ? "" : "s"}</span>
          )}
        </div>
        <div className="relative w-full sm:w-64">
          <select className={`${controlCls} ${filters.symbol ? "border-accent/50" : ""}`}
            value={filters.symbol} onChange={(e) => set("symbol")(e.target.value)} aria-label="Stock">
            <option value="">All tracked stocks</option>
            {(options?.symbols ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <Icon d={CHEVRON} className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-text-muted" />
        </div>
      </div>

      {/* filters */}
      <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:flex lg:flex-wrap lg:justify-end">
        {options && (<>
          <Select className="lg:w-40" label="Is Event" value={filters.is_event} onChange={set("is_event")} options={options.is_event ?? []} />
          <Select className="lg:w-52" label="Type" value={filters.type} onChange={set("type")} options={options.type ?? []} />
          <Select className="lg:w-40" label="Source" value={filters.source} onChange={set("source")} options={options.source ?? []} />
          <Select className="lg:w-56" label="Category" value={filters.category} onChange={set("category")} options={options.category ?? []} />
        </>)}
        <div className="col-span-2 flex h-10 items-center gap-1 rounded-lg border border-bg-border bg-bg-elevated px-2 sm:col-span-1">
          <input type="date" value={filters.date_from} max={filters.date_to || undefined}
            onChange={(e) => set("date_from")(e.target.value)}
            className="h-9 w-full min-w-0 bg-transparent text-sm text-text-primary outline-none" aria-label="From date" />
          <span className="text-text-muted">–</span>
          <input type="date" value={filters.date_to} min={filters.date_from || undefined}
            onChange={(e) => set("date_to")(e.target.value)}
            className="h-9 w-full min-w-0 bg-transparent text-sm text-text-primary outline-none" aria-label="To date" />
        </div>
        <button onClick={reset} disabled={!hasFilters}
          className="btn-primary flex h-10 items-center justify-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-40">
          <Icon d={RESET} /> Reset
        </button>
      </div>

      {/* states */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-6 text-center text-sm text-red-400">
          {error}
          <button onClick={load} className="ml-3 underline">Retry</button>
        </div>
      )}
      {!error && !loading && items.length === 0 && (
        <div className="py-16 text-center">
          <p className="text-base font-medium text-text-primary">No announcements found</p>
          <p className="mt-1 text-sm text-text-muted">Try changing or clearing your filters.</p>
          {hasFilters && (
            <button onClick={reset} className="btn-ghost mt-4">
              Clear filters
            </button>
          )}
        </div>
      )}

      {/* grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {loading && !error
          ? Array.from({ length: 8 }, (_, i) => <Skeleton key={i} />)
          : items.map((a) => <Card key={a.id} a={a} />)}
      </div>

      {/* pagination */}
      {!error && total > size && (
        <div className="mt-8 flex flex-wrap items-center justify-center gap-1.5 text-sm">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page"
            className="h-9 w-9 rounded-lg bg-bg-elevated text-text-secondary hover:text-text-primary disabled:opacity-30">‹</button>
          {Array.from({ length: pages }, (_, i) => i + 1)
            .filter((n) => n === 1 || n === pages || Math.abs(n - page) <= 2)
            .map((n, i, arr) => (
              <span key={n} className="flex items-center gap-1.5">
                {i > 0 && n - arr[i - 1] > 1 && <span className="px-1 text-text-muted">…</span>}
                <button onClick={() => setPage(n)}
                  className={`h-9 min-w-9 rounded-lg px-3 ${n === page ? "bg-accent font-semibold text-white" : "bg-bg-elevated text-text-secondary hover:text-text-primary"}`}>
                  {n}
                </button>
              </span>
            ))}
          <button disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"
            className="h-9 w-9 rounded-lg bg-bg-elevated text-text-secondary hover:text-text-primary disabled:opacity-30">›</button>
        </div>
      )}
    </div>
  );
}