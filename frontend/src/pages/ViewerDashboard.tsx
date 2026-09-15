import { useEffect, useState } from 'react';
import { Activity, BarChart3, Newspaper, TrendingUp } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import SummaryCard from '../components/dashboard/SummaryCard';
import { dashboardApi } from '../api/dashboard';

export default function ViewerDashboard() {
  const [summary, setSummary] = useState<{ tracked_companies: number; total_news: number } | null>(null);

  useEffect(() => {
    dashboardApi.viewer().then(setSummary).catch(() => setSummary(null));
  }, []);

  return <div className="space-y-6">
    <PageHeader title="Viewer Dashboard" subtitle="Live market information from the application database." />
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      <SummaryCard title="Tracked Companies" value={summary ? String(summary.tracked_companies) : '—'} change="Live database total" icon={TrendingUp} iconColor="text-accent-light" />
      <SummaryCard title="News Articles" value={summary ? String(summary.total_news) : '—'} change="Live database total" icon={Newspaper} iconColor="text-blue-400" />
      <SummaryCard title="Market Overview" value="Live" change="Open from sidebar" icon={BarChart3} iconColor="text-up" />
      <SummaryCard title="Trading Data" value="Live" change="Open from sidebar" icon={Activity} iconColor="text-yellow-400" />
    </div>
  </div>;
}
