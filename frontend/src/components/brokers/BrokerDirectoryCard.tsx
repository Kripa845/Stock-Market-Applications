import { Link } from 'react-router-dom';
import { ArrowUpRight, ChevronDown, Globe, Mail, MapPin, MonitorSmartphone, Phone } from 'lucide-react';
import clsx from 'clsx';
import type { BrokerListRow } from '../../api/analysis';
import { formatNprArab } from '../market/format';
import { BrokerLogo } from './BrokerBadge';

const withScheme = (url: string) => (/^https?:\/\//i.test(url) ? url : `https://${url}`);
export const hostOf = (url: string) => url.replace(/^https?:\/\//i, '').replace(/^www\./i, '').replace(/\/.*$/, '');

/** "Trading Cum Self Clearing Member" -> "Self clearing". */
export function membershipLabel(type: string) {
  if (!type) return '';
  if (/self clearing/i.test(type)) return 'Self clearing';
  if (/clearing/i.test(type)) return 'Clearing';
  return type;
}

/**
 * NEPSE lists some names in capitals ("SUN SECURITIES PVT LTD"): show those, and all-lowercase
 * ones, in title case.  Initialisms written with dots ("N.M.B.") stay as they are.
 */
export function displayName(name: string) {
  const letters = name.replace(/[^a-z]/gi, '');
  if (!letters || (letters !== letters.toUpperCase() && letters !== letters.toLowerCase())) return name;
  return name.split(/(\s+)/).map((word) => (
    word.includes('.') ? word.toUpperCase() : word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
  )).join('');
}

function Chip({ tone = 'muted', title, children }: { tone?: 'muted' | 'accent' | 'violet' | 'down'; title?: string; children: React.ReactNode }) {
  const tones = {
    muted: 'bg-bg-border/60 text-text-secondary',
    accent: 'bg-accent/10 text-accent-light',
    violet: 'bg-violet-500/10 text-violet-400',
    down: 'bg-down/10 text-down',
  };
  return <span title={title} className={`rounded px-1.5 py-px text-[10px] font-medium ${tones[tone]}`}>{children}</span>;
}

function ContactLine({ icon: Icon, children }: { icon: typeof Phone; children: React.ReactNode }) {
  return (
    <li className="flex min-w-0 items-start gap-2">
      <Icon size={12} className="mt-0.5 shrink-0 text-text-muted" />
      <span className="min-w-0 break-words">{children}</span>
    </li>
  );
}

/** One broker in the directory: identity, head office, website / TMS links and other offices. */
export default function BrokerDirectoryCard({ row, range }: { row: BrokerListRow; range: string }) {
  const otherOffices = row.branches.slice(1);
  const suspended = !row.is_active;
  const name = displayName(row.name);

  return (
    // .card carries the app's hover glow and light-theme colours.
    <article className={clsx('card flex flex-col !p-0', suspended && '!border-down/50')}>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <header className="flex items-start gap-3">
          <BrokerLogo brokerCode={row.broker_code} name={row.name} shortName={row.short_name} logoUrl={row.logo_url} size={44} />
          <div className="min-w-0 flex-1">
            <Link to={`/broker-analysis/${encodeURIComponent(row.broker_code)}${range}`} title={`${row.name} · open in Broker Explorer`}
              className="line-clamp-2 font-semibold leading-snug text-text-primary hover:text-accent-light">
              {name}
            </Link>
            {row.city && <p className="mt-0.5 text-[11px] text-text-muted">{row.city}</p>}
          </div>
          <span title="NEPSE broker number"
            className="shrink-0 rounded-md border border-bg-border bg-bg-elevated px-2 py-0.5 font-mono text-xs font-semibold text-text-primary">
            #{row.broker_no ?? row.broker_code}
          </span>
        </header>

        <div className="flex flex-wrap gap-1">
          {row.membership_type && <Chip title={row.membership_type}>{membershipLabel(row.membership_type)}</Chip>}
          {row.is_dealer && <Chip tone="violet">Dealer</Chip>}
          {suspended && <Chip tone="down">{row.nepse_status === 'SUSPEND' ? 'Suspended' : 'Inactive'}</Chip>}
          {row.rank && (
            <Chip tone="accent" title={`Turnover Rs ${formatNprArab(row.turnover)} in the selected period`}>
              #{row.rank} by turnover
            </Chip>
          )}
        </div>

        <ul className="space-y-1.5 text-[11px] text-text-secondary">
          {row.address && <ContactLine icon={MapPin}>{row.address}</ContactLine>}
          {row.phone && <ContactLine icon={Phone}>{row.phone}</ContactLine>}
          {row.email && (
            <ContactLine icon={Mail}>
              <a href={`mailto:${row.email}`} className="hover:text-accent-light hover:underline">{row.email}</a>
            </ContactLine>
          )}
        </ul>
      </div>

      <footer className="space-y-2 border-t border-bg-border px-4 py-3">
        <div className="flex gap-2">
          {row.website ? (
            <a href={withScheme(row.website)} target="_blank" rel="noreferrer" title={`Visit ${row.website}`}
              className="flex min-w-0 flex-1 items-center justify-center gap-1.5 rounded-lg bg-accent/15 px-3 py-2 text-xs font-semibold text-accent-light transition-colors hover:bg-accent hover:text-white">
              <Globe size={13} className="shrink-0" />
              <span className="truncate">{hostOf(row.website)}</span>
              <ArrowUpRight size={13} className="shrink-0" />
            </a>
          ) : (
            <span className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-dashed border-bg-border px-3 py-2 text-xs text-text-muted">
              <Globe size={13} /> No website on record
            </span>
          )}
          {row.tms_link && (
            <a href={withScheme(row.tms_link)} target="_blank" rel="noreferrer" title={`NEPSE TMS: ${row.tms_link}`}
              className="flex shrink-0 items-center gap-1.5 rounded-lg border border-bg-border px-3 py-2 text-xs font-semibold text-text-secondary transition-colors hover:border-accent/50 hover:text-text-primary">
              <MonitorSmartphone size={13} /> TMS
            </a>
          )}
        </div>

        {otherOffices.length > 0 ? (
          <details className="group text-[11px]">
            <summary className="flex cursor-pointer list-none items-center gap-1 text-text-muted hover:text-text-primary">
              <span className="truncate">
                +{otherOffices.length} office{otherOffices.length > 1 ? 's' : ''} · {otherOffices.map((b) => b.name).join(', ')}
              </span>
              <ChevronDown size={12} className="ml-auto shrink-0 transition-transform group-open:rotate-180" />
            </summary>
            <ul className="mt-2 space-y-1.5">
              {otherOffices.map((office, index) => (
                <li key={`${office.name}-${index}`} className="rounded-lg bg-bg-elevated px-2.5 py-1.5">
                  <p className="font-medium text-text-primary">{office.name}</p>
                  {office.address && <p className="text-text-secondary">{office.address}</p>}
                  {(office.phone || office.email) && (
                    <p className="text-text-muted">{[office.phone, office.email].filter(Boolean).join(' · ')}</p>
                  )}
                </li>
              ))}
            </ul>
          </details>
        ) : (
          <p className="text-[11px] text-text-muted">Head office only</p>
        )}
      </footer>
    </article>
  );
}
