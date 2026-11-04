# companies/management/commands/compute_master_scores.py
class Command(BaseCommand):
    def handle(self, *args, **kw):
        for company in Company.objects.filter(is_tracked=True):
            r = compute_master_score(company.daily_prices.all())
            if r:
                MasterScore.objects.update_or_create(
                    company=company, date=r["date"],
                    defaults={"score": r["score"], "band": r["band"], "components": r["components"]},
                )