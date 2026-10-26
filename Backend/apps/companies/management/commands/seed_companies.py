import json
from pathlib import Path


from django.conf import settings
from django.core.management.base import BaseCommand

from apps.companies.models import (
    Company,
    TrackedCompany,
)


COMPANIES = [
    {
        "symbol": "NABIL",
        "name": "Nabil Bank Limited",
        "sector": "Commercial Bank",
        "aliases": [
            "Nabil Bank",
            "Nabil Bank Ltd",
            "Nabil",
        ],
    },
    {
        "symbol": "ADBL",
        "name": "Agricultural Development Bank Limited",
        "sector": "Commercial Bank",
        "aliases": [
            "Agricultural Development Bank",
            "Agricultural Development Bank Ltd",
            "ADBL Bank",
            "ADBL",
        ],
    },
    {
        "symbol": "NICA",
        "name": "NIC Asia Bank Limited",
        "sector": "Commercial Bank",
        "aliases": [
            "NIC Asia Bank",
            "NIC Asia Bank Ltd",
            "NIC Asia",
            "NICA",
        ],
    },
    {
        "symbol": "SCB",
        "name": "Standard Chartered Bank Nepal Limited",
        "sector": "Commercial Bank",
        "aliases": [
            "Standard Chartered Bank Nepal",
            "Standard Chartered Nepal",
            "Standard Chartered Bank",
            "SCB Nepal",
            "SCB",
        ],
    },
    {
        "symbol": "NLIC",
        "name": "Nepal Life Insurance Company Limited",
        "sector": "Life Insurance",
        "aliases": [
            "Nepal Life Insurance",
            "Nepal Life Insurance Company",
            "Nepal Life",
            "NLIC",
        ],
    },
    {
        "symbol": "SHIVM",
        "name": "Shivam Cements Limited",
        "sector": "Manufacturing",
        "aliases": [
            "Shivam Cement",
            "Shivam Cements",
            "Shivam Cements Ltd",
            "Shivam",
            "SHIVM",
        ],
    },
    {
        "symbol": "CHCL",
        "name": "Chilime Hydropower Company Limited",
        "sector": "Hydropower",
        "aliases": [
            "Chilime Hydropower",
            "Chilime Hydro",
            "Chilime",
            "CHCL",
        ],
    },
    {
        "symbol": "UPPER",
        "name": "Upper Tamakoshi Hydropower Limited",
        "sector": "Hydropower",
        "aliases": [
            "Upper Tamakoshi Hydropower",
            "Upper Tamakoshi Hydro",
            "Upper Tamakoshi",
            "UPPER",
        ],
    },
    {
        "symbol": "HDL",
        "name": "Himalayan Distillery Limited",
        "sector": "Manufacturing",
        "aliases": [
            "Himalayan Distillery",
            "Himalayan Distillery Ltd",
            "Himalayan",
            "HDL",
        ],
    },
    {
        "symbol": "SANIMA",
        "name": "Sanima Bank Limited",
        "sector": "Commercial Bank",
        "aliases": [
            "Sanima Bank",
            "Sanima Bank Ltd",
            "Sanima",
            "SANIMA",
        ],
    },
    # ---- Added 2026-10: 10 more tracked companies (verified on ShareSansar first) ----
    {
        "symbol": "MNBBL",
        "name": "Muktinath Bikas Bank Limited",
        "sector": "Development Bank",
        "aliases": ["Muktinath Bikas Bank", "Muktinath Bikas Bank Ltd", "Muktinath Bikas", "MNBBL"],
    },
    {
        "symbol": "GUFL",
        "name": "Gurkhas Finance Limited",
        "sector": "Finance",
        "aliases": ["Gurkhas Finance", "Gurkhas Finance Ltd", "GUFL"],
    },
    {
        "symbol": "CBBL",
        "name": "Chhimek Laghubitta Bittiya Sanstha Ltd",
        "sector": "Microfinance",
        "aliases": ["Chhimek Laghubitta", "Chhimek Laghubitta Bittiya Sanstha", "CBBL"],
    },
    {
        "symbol": "NLG",
        "name": "NLG Insurance Company Limited",
        "sector": "Non Life Insurance",
        "aliases": ["NLG Insurance", "NLG Insurance Company", "NLG Insurance Company Ltd", "NLG"],
    },
    {
        "symbol": "TRH",
        "name": "Taragaon Regency Hotel Limited",
        "sector": "Hotels and Tourism",
        "aliases": ["Taragaon Regency Hotel", "Taragaon Regency", "Hyatt Regency Kathmandu", "TRH"],
    },
    {
        "symbol": "STC",
        "name": "Salt Trading Corporation Limited",
        "sector": "Trading",
        "aliases": ["Salt Trading Corporation", "Salt Trading", "STC"],
    },
    {
        "symbol": "NTC",
        "name": "Nepal Doorsanchar Company Limited",
        "sector": "Others",
        "aliases": ["Nepal Doorsanchar", "Nepal Telecom", "Nepal Doorsanchar Company", "NTC"],
    },
    {
        "symbol": "HIDCL",
        "name": "Hydroelectricity Investment and Development Company Limited",
        "sector": "Investment",
        "aliases": ["Hydroelectricity Investment and Development Company", "HIDCL"],
    },
    {
        "symbol": "AKJCL",
        "name": "Ankhu Khola Jalvidhyut Company Limited",
        "sector": "Hydropower",
        "aliases": ["Ankhu Khola Jalvidhyut", "Ankhu Khola Hydropower", "Ankhu Khola", "AKJCL"],
    },
    {
        "symbol": "LICN",
        "name": "Life Insurance Corporation (Nepal) Limited",
        "sector": "Life Insurance",
        "aliases": [
            "Life Insurance Corporation Nepal",
            "Life Insurance Corporation (Nepal)",
            "LIC Nepal",
            "LICN",
        ],
    },
]


class Command(BaseCommand):
    help = (
        "Create the tracked companies that do not exist yet. Idempotent: a company "
        "that already exists is left exactly as it is (no duplicate, no update)."
    )

    def handle(self, *args, **kwargs):

        # -----------------------------------------
        # 1. Load company logos
        # -----------------------------------------

        logo_path = Path(settings.BASE_DIR) / "data" / "company_logos.json"

        if not logo_path.exists():
            self.stdout.write(
                self.style.ERROR(
                    f"Logo file not found: {logo_path.resolve()}"
                )
            )
            return

        with open(logo_path, "r", encoding="utf-8") as f:
            logo_data = json.load(f)

        # -----------------------------------------
        # 2. Create symbol → logo URL lookup
        # -----------------------------------------

        logo_lookup = {
            item["symbol"].strip().upper(): item["logo_url"]
            for item in logo_data
            if item.get("symbol") and item.get("logo_url")
        }

        # -----------------------------------------
        # 3. Seed the tracked companies
        # -----------------------------------------

        for data in COMPANIES:

            symbol = data["symbol"].upper()

            # Find matching logo
            logo_url = logo_lookup.get(symbol)

            if logo_url:
                self.stdout.write(
                    f"Logo found for {symbol}"
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"No logo found for {symbol}"
                    )
                )

            # Create only; an existing company (and its tracking flag) is never altered.
            company, created = Company.objects.get_or_create(
                symbol=symbol,
                defaults={
                    "name": data["name"],
                    "sector": data["sector"],
                    "aliases": data["aliases"],
                    "is_active": True,
                    "logo_url": logo_url,
                },
            )

            if created:
                TrackedCompany.objects.get_or_create(
                    company=company,
                    defaults={
                        "is_tracked": True,
                    },
                )

            action = "CREATED" if created else "EXISTS (unchanged)"

            self.stdout.write(
                self.style.SUCCESS(
                    f"{action}: {company.symbol} - {company.name}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {len(COMPANIES)} companies."
            )
        )