
import { Link } from 'react-router-dom';
import {
  Newspaper,
  Building2,
  Activity,
  Database,
} from 'lucide-react';
import ThemeToggle from '../components/ThemeToggle';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-bg-primary">

      {/* Navbar */}
      <nav className="h-16 border-b border-bg-border
        flex items-center justify-between px-8">

        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-lg bg-accent
            flex items-center justify-center">
            <Activity size={18} />
          </div>

          <span className="font-bold text-lg">
            StockScope
          </span>
        </div>

        <div className="flex items-center gap-3">
          <ThemeToggle />

          <Link
            to="/login"
            className="btn-ghost"
          >
            Login
          </Link>

          <Link
            to="/register"
            className="btn-primary"
          >
            Register
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto
        px-6 py-24 text-center">

        <p className="text-accent-light text-sm
          font-semibold mb-4">
          NEPSE MARKET INTELLIGENCE
        </p>

        <h1 className="text-5xl font-bold
          text-text-primary max-w-4xl mx-auto">
          Understand the market through
          <span className="text-accent-light">
            {' '}data, news and behaviour.
          </span>
        </h1>

        <p className="mt-6 text-text-secondary
          max-w-2xl mx-auto">
          Track companies, monitor market data,
          analyze news sentiment and observe
          trading behaviour from one platform.
        </p>

        <div className="flex justify-center
          gap-3 mt-8">

          <Link
            to="/register"
            className="btn-primary"
          >
            Get Started
          </Link>

          <Link
            to="/login"
            className="btn-ghost"
          >
            Sign In
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto
        px-6 pb-20">

        <div className="grid md:grid-cols-4 gap-4">

          {[
            {
              icon: Building2,
              title: 'Companies',
              text: 'Monitor tracked companies and market information.',
            },
            {
              icon: Newspaper,
              title: 'News Intelligence',
              text: 'Analyze crawled news and company sentiment.',
            },
            {
              icon: Activity,
              title: 'Trading Behaviour',
              text: 'Study VWAP, pressure and volume anomalies.',
            },
            {
              icon: Database,
              title: 'Crawling',
              text: 'Monitor market and news data collection.',
            },
          ].map((feature) => {
            const Icon = feature.icon;

            return (
              <div
                key={feature.title}
                className="card"
              >
                <Icon
                  size={22}
                  className="text-accent-light mb-4"
                />

                <h3 className="font-semibold">
                  {feature.title}
                </h3>

                <p className="text-xs
                  text-text-secondary mt-2">
                  {feature.text}
                </p>
              </div>
            );
          })}

        </div>
      </section>

    </div>
  );
}

