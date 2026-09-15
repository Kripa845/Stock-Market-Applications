import datetime
import random
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analysis.models import DailyAnalysis
from apps.companies.models import Company, TrackedCompany
from apps.crawler_runs.models import CrawlRun
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.news.models import ArticleCompanyTag, CategorizationCorrection, NewsArticle, RawArticle

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds rich realistic market data, historical prices, floorsheet, news tags, analysis, and users."

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding...")

        # 1. Seed RBAC Users
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@genex.com", "role": User.Role.ADMIN, "first_name": "Edward", "last_name": "Admin"},
        )
        admin_user.set_password("admin123")
        admin_user.role = User.Role.ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        analyst_user, _ = User.objects.get_or_create(
            username="analyst",
            defaults={"email": "analyst@genex.com", "role": User.Role.ANALYST, "first_name": "Sarah", "last_name": "Analyst"},
        )
        analyst_user.set_password("analyst123")
        analyst_user.role = User.Role.ANALYST
        analyst_user.save()

        viewer_user, _ = User.objects.get_or_create(
            username="viewer",
            defaults={"email": "viewer@genex.com", "role": User.Role.VIEWER, "first_name": "John", "last_name": "Viewer"},
        )
        viewer_user.set_password("viewer123")
        viewer_user.role = User.Role.VIEWER
        viewer_user.save()

        self.stdout.write(self.style.SUCCESS("Users seeded: admin, analyst, viewer (passwords: admin123, analyst123, viewer123)"))

        # 2. Seed Companies
        companies_data = [
            {"symbol": "NABIL", "name": "Nabil Bank Limited", "sector": "Commercial Bank", "base_price": 540.0, "aliases": ["NABIL", "Nabil Bank", "Nabil"]},
            {"symbol": "NICA", "name": "NIC Asia Bank Limited", "sector": "Commercial Bank", "base_price": 435.0, "aliases": ["NICA", "NIC Asia", "NIC Asia Bank"]},
            {"symbol": "SCB", "name": "Standard Chartered Bank Nepal Limited", "sector": "Commercial Bank", "base_price": 590.0, "aliases": ["SCB", "Standard Chartered", "Standard Chartered Bank"]},
            {"symbol": "ADBL", "name": "Agricultural Development Bank Limited", "sector": "Commercial Bank", "base_price": 280.0, "aliases": ["ADBL", "Krishi Bikas Bank", "Agricultural Development Bank"]},
            {"symbol": "SANIMA", "name": "Sanima Bank Limited", "sector": "Commercial Bank", "base_price": 310.0, "aliases": ["SANIMA", "Sanima Bank", "Sanima"]},
            {"symbol": "NLIC", "name": "Nepal Life Insurance Company Limited", "sector": "Life Insurance", "base_price": 680.0, "aliases": ["NLIC", "Nepal Life", "Nepal Life Insurance"]},
            {"symbol": "SHIVM", "name": "Shivam Cements Limited", "sector": "Manufacturing", "base_price": 510.0, "aliases": ["SHIVM", "Shivam Cement", "Shivam"]},
            {"symbol": "CHCL", "name": "Chilime Hydropower Company Limited", "sector": "Hydropower", "base_price": 490.0, "aliases": ["CHCL", "Chilime Hydropower", "Chilime"]},
            {"symbol": "UPPER", "name": "Upper Tamakoshi Hydropower Limited", "sector": "Hydropower", "base_price": 230.0, "aliases": ["UPPER", "Upper Tamakoshi", "Tamakoshi"]},
            {"symbol": "HDL", "name": "Himalayan Distillery Limited", "sector": "Manufacturing", "base_price": 1420.0, "aliases": ["HDL", "Himalayan Distillery", "Jawalakhel"]},
        ]

        companies_dict = {}
        for cdata in companies_data:
            c, _ = Company.objects.get_or_create(
                symbol=cdata["symbol"],
                defaults={
                    "name": cdata["name"],
                    "sector": cdata["sector"],
                    "aliases": cdata["aliases"],
                    "is_active": True,
                    "created_by": admin_user,
                },
            )
            TrackedCompany.objects.get_or_create(company=c, defaults={"is_tracked": True})
            companies_dict[c.symbol] = (c, cdata["base_price"])

        self.stdout.write(self.style.SUCCESS(f"Companies configured: {len(companies_dict)}"))

        # 3. Seed 1-Year Historical Prices (Daily OHLCV)
        DailyPrice.objects.all().delete()
        today = datetime.date.today()
        num_days = 250  # ~1 year trading days
        random.seed(42)

        for symbol, (company, base_price) in companies_dict.items():
            current_price = base_price
            price_objects = []

            for day_offset in range(num_days, -1, -1):
                d = today - datetime.timedelta(days=day_offset * 1.4)
                # Skip Saturdays (Nepal weekend is Sat)
                if d.weekday() == 5:
                    continue

                drift = random.gauss(0.0008, 0.02)
                current_price = max(50.0, current_price * (1 + drift))
                high_pct = random.uniform(0.005, 0.035)
                low_pct = random.uniform(0.005, 0.035)

                close_p = round(current_price, 2)
                open_p = round(close_p * (1 + random.uniform(-0.015, 0.015)), 2)
                high_p = round(max(open_p, close_p) * (1 + high_pct), 2)
                low_p = round(min(open_p, close_p) * (1 - low_pct), 2)
                volume = random.randint(15000, 320000)
                turnover = round(Decimal(volume) * Decimal(close_p), 2)

                price_objects.append(
                    DailyPrice(
                        company=company,
                        date=d,
                        open=Decimal(str(open_p)),
                        high=Decimal(str(high_p)),
                        low=Decimal(str(low_p)),
                        close=Decimal(str(close_p)),
                        volume=volume,
                        turnover=turnover,
                    )
                )

            DailyPrice.objects.bulk_create(price_objects, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(f"Daily prices seeded for all companies ({DailyPrice.objects.count()} records)."))

        # 4. Seed Daily Analysis (VWAP, Pressure, Volume Anomaly)
        DailyAnalysis.objects.all().delete()
        analysis_objects = []

        for symbol, (company, _) in companies_dict.items():
            prices = list(DailyPrice.objects.filter(company=company).order_by("date"))
            for i, p in enumerate(prices[-60:]):  # Last 60 days
                # 30-day window for VWAP and avg volume
                window = prices[max(0, i - 30): i + 1]
                tot_vol = sum(int(w.volume) for w in window)
                tot_turnover = sum(float(w.turnover) for w in window)
                vwap = Decimal(str(round(tot_turnover / tot_vol, 4))) if tot_vol > 0 else p.close
                avg_vol = Decimal(str(round(tot_vol / len(window), 2))) if window else Decimal(str(p.volume))

                vol_ratio = float(p.volume) / float(avg_vol) if float(avg_vol) > 0 else 1.0
                vol_anomaly = vol_ratio >= 1.5

                if p.close > vwap:
                    pressure = "buying"
                elif p.close < vwap:
                    pressure = "selling"
                else:
                    pressure = "neutral"

                analysis_objects.append(
                    DailyAnalysis(
                        company=company,
                        date=p.date,
                        vwap=vwap,
                        close_price=p.close,
                        volume=p.volume,
                        volume_average=avg_vol,
                        volume_anomaly=vol_anomaly,
                        pressure=pressure,
                        news_count=random.randint(0, 5),
                    )
                )

        DailyAnalysis.objects.bulk_create(analysis_objects, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f"Daily analysis seeded ({DailyAnalysis.objects.count()} records)."))

        # 5. Seed / Link Floorsheet Transactions if needed
        existing_fs_count = FloorsheetTransaction.objects.count()
        if existing_fs_count < 200:
            fs_objects = []
            brokers = [f"Broker-{i}" for i in [58, 45, 34, 28, 19, 57, 42, 38, 50, 14, 49, 36, 25]]
            for symbol, (company, _) in companies_dict.items():
                recent_prices = DailyPrice.objects.filter(company=company).order_by("-date")[:5]
                for p in recent_prices:
                    for tx_idx in range(25):
                        qty = random.choice([50, 100, 200, 500, 1000, 2500, 5000])
                        rate = round(float(p.close) * random.uniform(0.985, 1.015), 2)
                        b_broker = random.choice(brokers)
                        s_broker = random.choice([b for b in brokers if b != b_broker])
                        fs_objects.append(
                            FloorsheetTransaction(
                                company=company,
                                date=p.date,
                                transaction_id=f"TX-{company.symbol}-{p.date.strftime('%Y%m%d')}-{tx_idx:04d}",
                                buyer_broker=b_broker,
                                seller_broker=s_broker,
                                quantity=qty,
                                rate=Decimal(str(rate)),
                                amount=Decimal(str(round(qty * rate, 2))),
                            )
                        )
            FloorsheetTransaction.objects.bulk_create(fs_objects, ignore_conflicts=True)
            self.stdout.write(self.style.SUCCESS(f"Floorsheet transactions seeded ({FloorsheetTransaction.objects.count()} records)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Existing floorsheet retained ({existing_fs_count} records)."))

        # 6. Seed Crawl Runs
        now = timezone.now()
        main_crawl_run, _ = CrawlRun.objects.get_or_create(
            id=1,
            defaults={
                "started_at": now - datetime.timedelta(hours=4),
                "completed_at": now - datetime.timedelta(hours=3, minutes=45),
                "status": "completed",
                "sources": ["sharesansar", "merolagani", "bizmandu"],
                "articles_found": 35,
                "articles_created": 24,
                "articles_updated": 11,
            },
        )

        runs = [
            CrawlRun(
                started_at=now - datetime.timedelta(minutes=15),
                completed_at=now - datetime.timedelta(minutes=10),
                status="completed",
                sources=["sharesansar", "merolagani", "bizmandu"],
                articles_found=18,
                articles_created=12,
                articles_updated=6,
                errors=[],
            ),
            CrawlRun(
                started_at=now - datetime.timedelta(hours=3),
                completed_at=now - datetime.timedelta(hours=2, minutes=54),
                status="completed",
                sources=["trading_data", "floorsheet"],
                articles_found=250,
                articles_created=250,
                articles_updated=0,
                errors=[],
            ),
            CrawlRun(
                started_at=now - datetime.timedelta(hours=6),
                completed_at=now - datetime.timedelta(hours=5, minutes=50),
                status="completed",
                sources=["nepsealpha", "arthakhabar", "fiscalnepal"],
                articles_found=14,
                articles_created=9,
                articles_updated=5,
                errors=[],
            ),
        ]
        CrawlRun.objects.bulk_create(runs)
        self.stdout.write(self.style.SUCCESS(f"Crawl runs seeded ({CrawlRun.objects.count()} records)."))

        # 7. Seed News Articles, ArticleCompanyTags, and CategorizationCorrections
        sample_news = [
            {
                "headline": "Nabil Bank reports 18.5% rise in net profit for Q3, driven by core banking growth and digital loans",
                "body": "Nabil Bank Limited (NABIL) has posted strong third-quarter financial results, recording an 18.5% year-on-year increase in net profit. The commercial bank's non-performing loan ratio remained stable at 1.2%, outperforming sector averages. CEO highlighted ongoing digital transformation initiatives.",
                "source": "ShareSansar",
                "sentiment": 0.85,
                "sentiment_label": "positive",
                "symbol": "NABIL",
                "confidence": 0.94,
            },
            {
                "headline": "NIC Asia Bank expands retail SME portfolio while maintaining capital adequacy ratio",
                "body": "NIC Asia Bank Limited (NICA) announced aggressive expansion into rural agribusiness and renewable energy SME loans. The bank's credit-to-deposit ratio remains well within regulatory guidelines set by Nepal Rastra Bank.",
                "source": "MeroLagani",
                "sentiment": 0.65,
                "sentiment_label": "positive",
                "symbol": "NICA",
                "confidence": 0.92,
            },
            {
                "headline": "Standard Chartered Bank Nepal declares 19% dividend from fiscal earnings",
                "body": "Standard Chartered Bank Nepal Limited (SCB) proposed a 19% total dividend including 6.5% bonus shares and 12.5% cash payout subject to approval in the upcoming AGM. Investors reacted enthusiastically on the exchange floor.",
                "source": "Bizmandu",
                "sentiment": 0.90,
                "sentiment_label": "positive",
                "symbol": "SCB",
                "confidence": 0.96,
            },
            {
                "headline": "Agricultural Development Bank launches new green loan scheme for commercial farming cooperatives",
                "body": "ADBL introduced subsidized agricultural financing packages aimed at modernizing cold-storage infrastructure and irrigation projects across Terai and Gandaki provinces.",
                "source": "NepseAlpha",
                "sentiment": 0.55,
                "sentiment_label": "positive",
                "symbol": "ADBL",
                "confidence": 0.88,
            },
            {
                "headline": "Nepal Life Insurance Company achieves milestone with record life fund exceeding NPR 180 Billion",
                "body": "Nepal Life Insurance Company Limited (NLIC) has crossed NPR 180 billion in total life fund accumulation, maintaining its market leadership with over 28% total life insurance market share in Nepal.",
                "source": "ShareSansar",
                "sentiment": 0.78,
                "sentiment_label": "positive",
                "symbol": "NLIC",
                "confidence": 0.95,
            },
            {
                "headline": "Shivam Cements announces capacity expansion and clinker export to Indian borders",
                "body": "Shivam Cements Limited (SHIVM) has commenced trial production on its newly upgraded kiln, increasing daily production capacity by 20%. The company expects increased cement demand from post-monsoon infrastructure projects.",
                "source": "ArthaKhabar",
                "sentiment": 0.70,
                "sentiment_label": "positive",
                "symbol": "SHIVM",
                "confidence": 0.89,
            },
            {
                "headline": "Chilime Hydropower completes seasonal reservoir maintenance ahead of peak winter schedule",
                "body": "Chilime Hydropower Company Limited (CHCL) has completed scheduled turbine overhaul and desilting at its Rasuwa power plant. Generation is operating at 100% capacity.",
                "source": "FiscalNepal",
                "sentiment": 0.45,
                "sentiment_label": "neutral",
                "symbol": "CHCL",
                "confidence": 0.91,
            },
            {
                "headline": "Upper Tamakoshi Hydropower resumes full 456 MW commercial generation post transmission link repairs",
                "body": "Upper Tamakoshi Hydropower Limited (UPPER) has restored all six units following routine transmission line upgrade work. The plant supplies critical baseload power to the national grid.",
                "source": "MeroLagani",
                "sentiment": 0.60,
                "sentiment_label": "positive",
                "symbol": "UPPER",
                "confidence": 0.93,
            },
            {
                "headline": "Himalayan Distillery reports record exports in premium spirits category",
                "body": "Himalayan Distillery Limited (HDL) has expanded its international export footprints with shipments of premium malt spirits to regional South Asian markets.",
                "source": "ShareSansar",
                "sentiment": 0.72,
                "sentiment_label": "positive",
                "symbol": "HDL",
                "confidence": 0.90,
            },
            {
                "headline": "Sanima Bank maintains lowest NPA among private commercial banks in Q2 review",
                "body": "Sanima Bank Limited (SANIMA) continues to demonstrate prudent credit underwriting, recording an industry-best NPA of 0.95% alongside solid return on equity.",
                "source": "Bizmandu",
                "sentiment": 0.80,
                "sentiment_label": "positive",
                "symbol": "SANIMA",
                "confidence": 0.91,
            },
            {
                "headline": "Nepal Rastra Bank tightens liquidity requirements amid macroeconomic monitoring",
                "body": "The central bank issued monetary guidelines regarding commercial banking loan-loss provisioning. While banking symbols saw slight caution, leading institutions remain well capitalized.",
                "source": "Bizmandu",
                "sentiment": -0.35,
                "sentiment_label": "negative",
                "symbol": "NABIL",
                "confidence": 0.62,
            },
            {
                "headline": "Hydropower sector faces seasonal discharge reduction during dry winter months",
                "body": "Run-of-river hydropower producers including CHCL and UPPER report reduced seasonal river flow, leading to moderate electricity generation adjustments.",
                "source": "ShareSansar",
                "sentiment": -0.25,
                "sentiment_label": "negative",
                "symbol": "CHCL",
                "confidence": 0.58,
            },
        ]

        for i, item in enumerate(sample_news):
            url = f"https://{item['source'].lower()}.com/news/{2000 + i}"
            raw_art, _ = RawArticle.objects.get_or_create(
                source=item["source"],
                url=url,
                defaults={"crawl_run": main_crawl_run, "http_status": 200, "raw_html": f"<p>{item['body']}</p>"},
            )
            pub_date = timezone.now() - datetime.timedelta(days=i * 2, hours=random.randint(1, 12))
            article, created = NewsArticle.objects.get_or_create(
                url=url,
                defaults={
                    "raw_article": raw_art,
                    "source": item["source"],
                    "headline": item["headline"],
                    "body": item["body"],
                    "published_at": pub_date,
                    "content_hash": f"hash_{i}_{random.randint(10000, 99999)}",
                    "language": "en",
                    "sentiment": item["sentiment"],
                    "sentiment_label": item["sentiment_label"],
                    "is_processed": True,
                },
            )

            # Add tag
            company = companies_dict[item["symbol"]][0]
            tag, _ = ArticleCompanyTag.objects.get_or_create(
                article=article,
                company=company,
                defaults={
                    "confidence": item["confidence"],
                    "method": "keyword_weighted",
                    "evidence": {"keyword": company.symbol, "frequency": 3},
                },
            )

            # Seed sample correction for demo
            if i == 0:
                CategorizationCorrection.objects.get_or_create(
                    article=article,
                    company=company,
                    defaults={
                        "previous_confidence": 0.75,
                        "previous_method": "keyword_weighted",
                        "action": "update",
                        "reason": "Verified headline refers directly to Nabil Bank Q3 results.",
                        "corrected_by": analyst_user,
                    },
                )

        self.stdout.write(self.style.SUCCESS(f"News articles and tags seeded ({NewsArticle.objects.count()} articles, {ArticleCompanyTag.objects.count()} tags)."))


        self.stdout.write(self.style.SUCCESS("All database seed operations completed successfully!"))
