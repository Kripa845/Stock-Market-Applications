import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, ArrowRight, BarChart3, Building2, Check, ChevronDown, FileSpreadsheet, LineChart, Newspaper,
  Moon, Plus, Search, ShieldCheck, Sun, Users,
} from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import HeroIllustration from '../components/landing/HeroIllustration';
import ParticleWave from '../components/landing/ParticleWave';
import LandingNews from '../components/landing/LandingNews';

// Public landing page with purple glows; follows the app's light / dark theme (colours in index.css .landing).
// Every claim here describes something the app really does; there are no invented reviews or user counts.


const FEATURES = [
  { icon: LineChart, title: 'Technical Indicators', text: '110 indicators — moving averages, oscillators, trend, volatility and volume — calculated from crawled NEPSE prices.' },
  { icon: Newspaper, title: 'News Intelligence', text: 'Financial news from four Nepali portals, tagged to companies automatically and scored for sentiment.' },
  { icon: Building2, title: 'Company Analysis', text: 'Price action, VWAP, volume anomalies and news reaction for every tracked company in one view.' },
  { icon: BarChart3, title: 'Broker Analysis', text: 'Floorsheet-based broker activity: who is buying, who is selling and how concentrated it is.' },
];

const POINTS = [
  'Prices and floorsheets are crawled from public NEPSE sources on a schedule.',
  'Indicators run on the server and are tested against independent reference calculations.',
  'Only crawled market data is charted — nothing is simulated or back-filled.',
];

const STEPS = [
  { icon: Search, title: 'Pick a company', text: 'Search tracked NEPSE companies by symbol, name or sector.' },
  { icon: LineChart, title: 'Read the chart', text: 'Candles, volume and any indicators you choose, on one time axis.' },
  { icon: Newspaper, title: 'Check the news', text: 'See which articles mention the company and how sentiment moved.' },
  { icon: FileSpreadsheet, title: 'Export reports', text: 'Download prices, analysis and broker data as CSV, Excel or PDF.' },
];

const ROLES = [
  { name: 'Viewer', tag: 'Free account', text: 'Explore the market.', perks: ['Market overview and companies', 'News feed', 'Personal watchlist'] },
  { name: 'Analyst', tag: 'Granted by an admin', text: 'Research and correct.', highlight: true,
    perks: ['Everything in Viewer', 'Company and broker analysis', '110 technical indicators', 'Correct news categorisation', 'Report exports'] },
  { name: 'Admin', tag: 'Your organisation', text: 'Run the platform.', perks: ['Everything in Analyst', 'User and role management', 'Crawl scheduling and monitoring'] },
];

const FAQS = [
  { q: 'Where does the data come from?', a: 'StockScope crawls public NEPSE price and floorsheet data from Sharesansar, plus news from Sharesansar, Merolagani, FiscalNepal and Arthakhabar. Only crawled data is shown on charts.' },
  { q: 'How current is the data?', a: 'Daily prices and floorsheets are collected after each trading session, and news is crawled every hour. Every chart shows the exact date range it covers.' },
  { q: 'How are the indicators calculated?', a: 'On the server, from crawled daily prices, using the standard published formulas. Each one is tested against an independent reference calculation, and a line only starts once there are enough trading sessions for its period.' },
  { q: 'Who can see what?', a: 'Access is role-based. Anyone can register as a Viewer; Analyst and Admin access, and access to individual companies, is granted by an administrator.' },
  { q: 'Is this investment advice?', a: 'No. StockScope is a research tool. Indicators and sentiment scores describe historical data and are not recommendations to buy or sell.' },
];

const btnPrimary = 'inline-flex items-center justify-center gap-2 rounded-md bg-[image:var(--l-btn-bg)] px-4 py-2 text-sm font-medium text-[color:var(--l-btn-text)] shadow-[0_1px_0_rgba(255,255,255,0.4)_inset,0_6px_20px_rgba(0,0,0,0.25)] transition hover:brightness-110';
const btnGhost = 'inline-flex items-center justify-center gap-2 rounded-md border border-[color:var(--l-border)] bg-[var(--l-surface-solid)] px-4 py-2 text-sm font-medium text-[color:var(--l-text)] transition hover:border-[color:var(--l-border-strong)] hover:bg-[var(--l-surface-hover)]';

function SectionHeading({ title, text }: { title: string; text?: string }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <h2 className="text-3xl font-semibold tracking-tight text-[color:var(--l-text)] sm:text-4xl">{title}</h2>
      {text && <p className="mt-3 text-sm leading-relaxed text-[color:var(--l-muted)] sm:text-base">{text}</p>}
    </div>
  );
}

function Faq() {
  const [open, setOpen] = useState(0);
  return (
    <div className="mx-auto mt-10 max-w-3xl space-y-3">
      {FAQS.map((item, i) => {
        const isOpen = open === i;
        return (
          <div key={item.q} className={`rounded-xl border transition ${isOpen ? 'border-violet-400/40 bg-violet-500/[0.07]' : 'border-[color:var(--l-border)] bg-[var(--l-surface)] hover:border-[color:var(--l-border-strong)]'}`}>
            <button type="button" onClick={() => setOpen(isOpen ? -1 : i)} aria-expanded={isOpen}
              className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-medium text-[color:var(--l-text)]">
              {item.q}
              <Plus size={16} className={`shrink-0 text-[color:var(--l-accent)] transition-transform ${isOpen ? 'rotate-45' : ''}`} />
            </button>
            <div className={`grid transition-all duration-300 ${isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}>
              <p className="overflow-hidden px-5 text-sm leading-relaxed text-[color:var(--l-muted)]">
                <span className="block pb-4">{item.a}</span>
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [theme, toggleTheme] = useTheme();
  const nav = [['Features', '#features'],['News', '#news'], ['How it works', '#how-it-works'], ['Access', '#access'], ['FAQ', '#faq']];

  return (
    <div className="landing min-h-screen overflow-x-hidden bg-[var(--l-bg)] font-sans text-[color:var(--l-text)] antialiased">
      {/* Navbar */}
      <header className="sticky top-0 z-40 border-b border-[color:var(--l-border)] bg-[var(--l-header)] backdrop-blur-xl">
        <nav className="mx-auto flex h-16 max-w-6xl items-center px-4 sm:px-6">
          <Link to="/" className="flex flex-1 items-center gap-2">
            <Activity size={20} className="text-[color:var(--l-text)]" />
            <span className="text-base font-medium tracking-tight">StockScope</span>
          </Link>
          <div className="hidden items-center gap-7 text-[13px] text-[color:var(--l-text-2)] md:flex">
            {nav.map(([label, href]) => <a key={href} href={href} className="transition hover:text-[color:var(--l-text)]">{label}</a>)}
          </div>
          <div className="flex flex-1 items-center justify-end gap-2">
            <button type="button" onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              className="rounded-md border border-[color:var(--l-border)] p-1.5 text-[color:var(--l-text-2)] transition hover:border-[color:var(--l-border-strong)] hover:text-[color:var(--l-text)]">
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <Link to="/login" className="rounded-md border border-[color:var(--l-border)] px-4 py-1.5 text-[13px] text-[color:var(--l-text-2)] transition hover:border-[color:var(--l-border-strong)] hover:text-[color:var(--l-text)]">Login</Link>
            <Link to="/register" className="rounded-md border border-violet-500/70 bg-violet-950/70 px-4 py-1.5 text-[13px] text-white shadow-[0_0_18px_rgba(124,58,237,0.45)] transition hover:bg-violet-900/80">Register</Link>
            <button type="button" onClick={() => setMenuOpen((o) => !o)} aria-label="Menu" aria-expanded={menuOpen}
              className="rounded-md p-1.5 text-[color:var(--l-text-2)] md:hidden">
              <ChevronDown size={18} className={`transition ${menuOpen ? 'rotate-180' : ''}`} />
            </button>
          </div>
        </nav>
        {menuOpen && (
          <div className="border-t border-[color:var(--l-border)] px-4 py-3 md:hidden">
            {nav.map(([label, href]) => (
              <a key={href} href={href} onClick={() => setMenuOpen(false)} className="block py-2 text-sm text-[color:var(--l-text-2)]">{label}</a>
            ))}
          </div>
        )}
      </header>

      {/* Hero */}
      <section className="relative bg-[var(--l-bg)]">
        <div className="relative mx-auto grid max-w-6xl items-center gap-6 px-4 pt-14 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:pt-20">
          <div className="text-center lg:text-left">
            <h1 className="text-4xl font-medium leading-[1.12] tracking-tight text-[color:var(--l-text)] sm:text-5xl">
              Read the NEPSE Market Through Data, News and Behaviour.
            </h1>
            <p className="mx-auto mt-5 max-w-md text-[15px] leading-relaxed text-[color:var(--l-muted)] lg:mx-0">
              Crawled prices, floorsheets and financial news, with technical indicators and news sentiment
              to help you research Nepali stocks.
            </p>
            <div className="mt-7 flex flex-wrap justify-center gap-3 lg:justify-start">
              <Link to="/register" className={btnPrimary}>Get started</Link>
              <a href="#features" className={btnGhost}>Explore features</a>
            </div>
          </div>
          <HeroIllustration className="mx-auto w-full max-w-[300px] sm:max-w-[420px] lg:max-w-[500px]" />
        </div>

        {/* Dotted wave under the hero */}
        <div className="relative -mt-10 lg:-mt-24">
          <ParticleWave className="h-48 w-full sm:h-64" />
        </div>
      </section>

      {/* Features */}
      <section id="features" className="relative scroll-mt-20 px-4 py-20 sm:px-6">
        <SectionHeading title="Powerful tools for smarter NEPSE research"
          text="From a first look at a company to detailed technical work, everything is built on crawled market data." />
        <div className="mx-auto mt-12 grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="group relative overflow-hidden rounded-2xl border border-[color:var(--l-border)] bg-gradient-to-b from-[var(--l-card-from)] to-[var(--l-card-to)] p-6 transition hover:-translate-y-1 hover:border-violet-400/40">
              <div className="pointer-events-none absolute -top-16 left-1/2 h-32 w-32 -translate-x-1/2 rounded-full bg-violet-600/0 blur-3xl transition group-hover:bg-violet-600/30" aria-hidden />
              <span className="relative flex h-11 w-11 items-center justify-center rounded-xl border border-violet-400/30 bg-violet-500/10 text-[color:var(--l-accent)] shadow-[0_0_20px_rgba(139,92,246,0.25)]">
                <Icon size={20} />
              </span>
              <h3 className="relative mt-5 text-base font-semibold">{title}</h3>
              <p className="relative mt-2 text-sm leading-relaxed text-[color:var(--l-muted)]">{text}</p>
              <Link to="/register" className="relative mt-5 inline-flex items-center gap-1 text-xs font-medium text-[color:var(--l-accent)] transition hover:text-[color:var(--l-accent)]">
                Learn more <ArrowRight size={13} className="transition group-hover:translate-x-0.5" />
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Split: research platform */}
      <section className="px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Research built on real market data</h2>
            <ul className="mt-8 space-y-5">
              {POINTS.map((p) => (
                <li key={p} className="flex gap-3 text-sm leading-relaxed text-[color:var(--l-text-2)]">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-[color:var(--l-accent)]">
                    <Check size={12} />
                  </span>
                  {p}
                </li>
              ))}
            </ul>
            <Link to="/register" className={`${btnPrimary} mt-8`}>Open the analysis tools <ArrowRight size={16} /></Link>
          </div>
        </div>
      </section>

      {/* Latest crawled news (hidden when there is none) */}
      <LandingNews heading={
        <SectionHeading title="What the NEPSE market is talking about"
          text="The newest stories crawled from Nepali financial portals. Each one opens on the site that published it." />
      } />

      {/* How it works */}
      <section id="how-it-works" className="scroll-mt-20 px-4 py-20 sm:px-6">
        <SectionHeading title="From a symbol to a decision in four steps" />
        <div className="relative mx-auto mt-14 grid max-w-6xl gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <div className="pointer-events-none absolute left-[12%] right-[12%] top-7 hidden h-px bg-gradient-to-r from-transparent via-violet-500/50 to-transparent lg:block" aria-hidden />
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <div key={title} className="relative text-center">
              <span className="relative mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-violet-400/40 bg-[var(--l-surface-solid)] text-[color:var(--l-accent)] shadow-[0_0_30px_rgba(139,92,246,0.35)]">
                <Icon size={20} />
              </span>
              <h3 className="mt-5 text-sm font-semibold">{title}</h3>
              <p className="mx-auto mt-2 max-w-[220px] text-sm leading-relaxed text-[color:var(--l-muted)]">{text}</p>
              <span className="mt-4 block text-4xl font-bold text-[color:var(--l-number)]">{String(i + 1).padStart(2, '0')}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Access levels (role-based, in place of pricing) */}
      <section id="access" className="relative scroll-mt-20 px-4 py-20 sm:px-6">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_80%_50%,rgba(124,58,237,0.15),transparent_55%)]" aria-hidden />
        <div className="relative">
          <SectionHeading title="Choose your level of access"
            text="Register for free as a Viewer. Analyst and Admin access is granted by your organisation's administrator." />
          <div className="mx-auto mt-12 grid max-w-5xl gap-5 md:grid-cols-3">
            {ROLES.map((role) => (
              <div key={role.name} className={`relative flex flex-col rounded-2xl border p-6 ${role.highlight
                ? 'border-violet-400/50 bg-gradient-to-b from-violet-600/20 to-[var(--l-card-to)] shadow-[0_0_50px_rgba(124,58,237,0.25)]'
                : 'border-[color:var(--l-border)] bg-[var(--l-surface)]'}`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-[color:var(--l-text-2)]">{role.name}</span>
                  {role.highlight && <span className="rounded-full bg-violet-500/25 px-2.5 py-0.5 text-[11px] font-medium text-[color:var(--l-accent)]">Most used</span>}
                </div>
                <p className="mt-4 text-2xl font-semibold">{role.text}</p>
                <p className="mt-1 text-xs text-[color:var(--l-faint)]">{role.tag}</p>
                <ul className="mt-6 flex-1 space-y-3">
                  {role.perks.map((perk) => (
                    <li key={perk} className="flex items-center gap-2.5 text-sm text-[color:var(--l-text-2)]">
                      <Check size={14} className="shrink-0 text-[color:var(--l-accent)]" /> {perk}
                    </li>
                  ))}
                </ul>
                {role.name === 'Viewer'
                  ? <Link to="/register" className={`${btnPrimary} mt-8 w-full`}>Create free account</Link>
                  : <span className={`${btnGhost} mt-8 w-full cursor-default`}>
                      {role.name === 'Analyst' ? <Users size={15} /> : <ShieldCheck size={15} />} Ask your administrator
                    </span>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="scroll-mt-20 px-4 py-20 sm:px-6">
        <SectionHeading title="Frequently asked questions"
          text="How StockScope gets its data and what it can do for your research." />
        <Faq />
      </section>

      {/* CTA */}
      <section className="px-4 pb-24 pt-10 sm:px-6">
        <div className="relative mx-auto max-w-5xl overflow-hidden rounded-3xl border border-[color:var(--l-border)] bg-[var(--l-cta-bg)] px-6 pb-28 pt-16 text-center">
          <div className="pointer-events-none absolute -bottom-40 left-1/2 h-72 w-[140%] -translate-x-1/2 rounded-[100%] border-t border-violet-300/60 bg-violet-600/40 blur-[2px] shadow-[0_-20px_80px_rgba(139,92,246,0.7)]" aria-hidden />
          <div className="pointer-events-none absolute -bottom-24 left-1/2 h-48 w-[80%] -translate-x-1/2 rounded-full bg-fuchsia-500/30 blur-3xl" aria-hidden />
          <div className="relative">
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Start researching NEPSE today</h2>
            <p className="mx-auto mt-3 max-w-lg text-sm text-[color:var(--l-muted)]">
              Create a free account to explore companies, news and the market overview.
            </p>
            <Link to="/register" className={`${btnPrimary} mt-8`}>Get started <ArrowRight size={16} /></Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[color:var(--l-border)] px-4 py-12 sm:px-6">
        <div className="mx-auto grid max-w-6xl gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <Link to="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-600"><Activity size={16} /></span>
              <span className="font-semibold">StockScope</span>
            </Link>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-[color:var(--l-faint)]">
              A research platform for the Nepal Stock Exchange. Information shown is for research only and is not investment advice.
            </p>
          </div>
          <div>
            <p className="text-sm font-medium">Product</p>
            <ul className="mt-4 space-y-2.5 text-sm text-[color:var(--l-faint)]">
              {nav.map(([label, href]) => <li key={href}><a href={href} className="transition hover:text-[color:var(--l-text)]">{label}</a></li>)}
            </ul>
          </div>
          <div>
            <p className="text-sm font-medium">Account</p>
            <ul className="mt-4 space-y-2.5 text-sm text-[color:var(--l-faint)]">
              <li><Link to="/login" className="transition hover:text-[color:var(--l-text)]">Login</Link></li>
              <li><Link to="/register" className="transition hover:text-[color:var(--l-text)]">Register</Link></li>
            </ul>
          </div>
        </div>
        <p className="mx-auto mt-12 max-w-6xl border-t border-[color:var(--l-border)] pt-6 text-center text-xs text-[color:var(--l-faint)]">
          © {new Date().getFullYear()} StockScope. All rights reserved.
          <span className="mt-1 block">Data from ShareSansar, ShareHub and NEPSE (unofficial sources), for personal research only.</span>
        </p>
      </footer>
    </div>
  );
}
