import { useEffect, useState } from 'react';
import { ArrowUpRight, Clock, Newspaper } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import NewsImage from '../common/NewsImage';
import { newsApi, type PublicNewsArticle } from '../../api/news';

// "Latest news" on the public landing page: the newest crawled headlines, each linking to the
// original article on its portal (the in-app article page needs a login). The section hides itself
// when there is no news or the request fails, so visitors never see placeholder stories.

const card = 'group flex h-full flex-col overflow-hidden rounded-2xl border border-[color:var(--l-border)] bg-gradient-to-b from-[var(--l-card-from)] to-[var(--l-card-to)] transition hover:-translate-y-1 hover:border-violet-400/40';

function Thumb({ src }: { src: string }) {
  return (
    <div className="relative aspect-[16/9] overflow-hidden bg-gradient-to-br from-violet-600/25 via-violet-900/10 to-fuchsia-500/20">
      {/* Shown when the article has no picture or it fails to load. */}
      <Newspaper size={28} className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-[color:var(--l-accent)] opacity-60" aria-hidden />
      <NewsImage src={src} className="absolute inset-0 h-full w-full transition duration-300 group-hover:scale-[1.03]" />
    </div>
  );
}

function Meta({ article }: { article: PublicNewsArticle }) {
  return (
    <div className="flex items-center gap-2 text-xs text-[color:var(--l-faint)]">
      <span className="font-medium text-[color:var(--l-accent)]">{article.source}</span>
      <span aria-hidden>·</span>
      <span className="flex items-center gap-1">
        <Clock size={11} />
        {formatDistanceToNow(new Date(article.published_at), { addSuffix: true })}
      </span>
    </div>
  );
}

function NewsCard({ article }: { article: PublicNewsArticle }) {
  return (
    <a href={article.url} target="_blank" rel="noopener noreferrer" className={card}>
      <Thumb src={article.image_url} />
      <div className="flex flex-1 flex-col gap-3 p-5">
        <Meta article={article} />
        <h3 className="line-clamp-2 text-base font-semibold leading-snug text-[color:var(--l-text)]">{article.headline}</h3>
        {article.excerpt && (
          <p className="line-clamp-2 text-sm leading-relaxed text-[color:var(--l-muted)]">{article.excerpt}</p>
        )}
        <span className="mt-auto inline-flex items-center gap-1 pt-1 text-xs font-medium text-[color:var(--l-accent)]">
          Read on {article.source} <ArrowUpRight size={13} className="transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </span>
      </div>
    </a>
  );
}

function Skeleton() {
  return (
    <div className={`${card} animate-pulse`} aria-hidden>
      <div className="aspect-[16/9] bg-[var(--l-surface)]" />
      <div className="space-y-3 p-5">
        <div className="h-3 w-1/3 rounded bg-[var(--l-surface)]" />
        <div className="h-4 w-full rounded bg-[var(--l-surface)]" />
        <div className="h-4 w-2/3 rounded bg-[var(--l-surface)]" />
      </div>
    </div>
  );
}

export default function LandingNews({ heading }: { heading: React.ReactNode }) {
  const [articles, setArticles] = useState<PublicNewsArticle[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    newsApi.getPublicLatest(6)
      .then((rows) => { if (!cancelled) setArticles(rows); })
      .catch(() => { if (!cancelled) setArticles([]); });
    return () => { cancelled = true; };
  }, []);

  if (articles && articles.length === 0) return null;

  return (
    <section id="news" className="scroll-mt-20 px-4 py-20 sm:px-6">
      {heading}
      <div className="mx-auto mt-12 grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {articles
          ? articles.map((a) => <NewsCard key={a.id} article={a} />)
          : Array.from({ length: 6 }, (_, i) => <Skeleton key={i} />)}
      </div>
    </section>
  );
}
