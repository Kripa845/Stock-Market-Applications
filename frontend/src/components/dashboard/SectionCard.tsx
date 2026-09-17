import DashboardCard from './DashboardCard';
import type { DashboardSectionData } from './dashboardConfig';

interface SectionCardProps {
  section: DashboardSectionData;
}

export default function SectionCard({ section }: SectionCardProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-text-primary">{section.title}</h2>
          {section.description && (
            <p className="text-sm text-text-secondary mt-0.5">{section.description}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {section.cards.map((card) => (
          <DashboardCard key={card.id} card={card} />
        ))}
      </div>
    </div>
  );
}
