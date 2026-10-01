import json
from pathlib import Path


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
]


class Command(BaseCommand):
    help = "Create or update the 10-company stock-market watchlist."

    def handle(self, *args, **kwargs):

        # -----------------------------------------
        # 1. Load company logos
        # -----------------------------------------

        logo_path = Path("company_logos.json")

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
        # 3. Seed the 10 companies
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

            # Create/update company
            company, created = Company.objects.update_or_create(
                symbol=symbol,
                defaults={
                    "name": data["name"],
                    "sector": data["sector"],
                    "aliases": data["aliases"],
                    "is_active": True,
                    "logo_url": logo_url,
                },
            )

            # Make company tracked
            TrackedCompany.objects.update_or_create(
                company=company,
                defaults={
                    "is_tracked": True,
                },
            )

            action = "CREATED" if created else "UPDATED"

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