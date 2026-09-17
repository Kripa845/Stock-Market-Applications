import { FileText } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';

export default function ReportsComingSoon() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        subtitle="Reports are coming soon."
      />
      <div className="card flex flex-col items-center gap-4 py-20">
        <FileText size={48} className="text-text-muted" />
        <div className="text-center">
          <p className="text-lg font-semibold text-text-primary">Reports are coming soon</p>
          <p className="text-sm text-text-secondary mt-1">
            Report generation features are being prepared. Check back later.
          </p>
        </div>
      </div>
    </div>
  );
}
