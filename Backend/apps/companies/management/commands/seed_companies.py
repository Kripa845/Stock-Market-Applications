# from django.core.management.base import BaseCommand

# from apps.companies.models import (
#     Company,
#     TrackedCompany,
# )


# COMPANIES = [

#     {
#         "symbol": "NABIL",
#         "name": "Nabil Bank Limited",
#         "sector": "Commercial Bank",
#     },

#     {
#         "symbol": "ADBL",
#         "name": "Agricultural Development Bank Limited",
#         "sector": "Commercial Bank",
#     },

#     {
#         "symbol": "NICA",
#         "name": "NIC Asia Bank Limited",
#         "sector": "Commercial Bank",
#     },

#     {
#         "symbol": "SCB",
#         "name": "Standard Chartered Bank Nepal Limited",
#         "sector": "Commercial Bank",
#     },

#     {
#         "symbol": "NLIC",
#         "name": "Nepal Life Insurance Company Limited",
#         "sector": "Life Insurance",
#     },

#     {
#         "symbol": "SHIVM",
#         "name": "Shivam Cements Limited",
#         "sector": "Manufacturing",
#     },

#     {
#         "symbol": "CHCL",
#         "name": "Chilime Hydropower Company Limited",
#         "sector": "Hydropower",
#     },

#     {
#         "symbol": "UPPER",
#         "name": "Upper Tamakoshi Hydropower Limited",
#         "sector": "Hydropower",
#     },

#     {
#         "symbol": "HDL",
#         "name": "Himalayan Distillery Limited",
#         "sector": "Manufacturing",
#     },

#     {
#         "symbol": "SANIMA",
#         "name": "Sanima Bank Limited",
#         "sector": "Commercial Bank",
#     },
# ]


# class Command(BaseCommand):

#     help = (
#         "Create the 10-company "
#         "stock-market watchlist."
#     )

#     def handle(self, *args, **kwargs):

#         for data in COMPANIES:

#             company, created = (
#                 Company.objects.update_or_create(
#                     symbol=data["symbol"],
#                     defaults={
#                         "name": data["name"],
#                         "sector": data["sector"],
#                         "is_active": True,
#                     },
#                 )
#             )

#             TrackedCompany.objects.update_or_create(
#                 company=company,
#                 defaults={
#                     "is_tracked": True,
#                 },
#             )

#             action = (
#                 "CREATED"
#                 if created
#                 else "UPDATED"
#             )

#             self.stdout.write(
#                 self.style.SUCCESS(
#                     f"{action}: {company.symbol}"
#                 )
#             )


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

        for data in COMPANIES:

            company, created = Company.objects.update_or_create(
                symbol=data["symbol"],
                defaults={
                    "name": data["name"],
                    "sector": data["sector"],
                    "aliases": data["aliases"],
                    "is_active": True,
                },
            )

            TrackedCompany.objects.update_or_create(
                company=company,
                defaults={
                    "is_tracked": True,
                },
            )

            action = "CREATED" if created else "UPDATED"

            self.stdout.write(
                self.style.SUCCESS(
                    f"{action}: {company.symbol} - "
                    f"{company.name}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {len(COMPANIES)} companies."
            )
        )