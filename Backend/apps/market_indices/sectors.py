"""
Sector-name normalisation.

Different sources label the same sector differently ("Commercial Banks" vs
"Banking").  Everything is normalised to the 13 NEPSE sub-index sector names
used in MarketIndex.sector_name.

Check the real strings your sources return, then extend SECTOR_MAP:
    python manage.py shell -c "from apps.companies.models import Company; \
        print(sorted(set(Company.objects.values_list('sector', flat=True))))"
"""

# (code, display name, normalised sector name) for the 13 sub-indices, in the
# order the ShareHub table shows them.
SUB_INDICES = [
    ("BANKING", "Banking SubIndex", "Banking"),
    ("DEVBANK", "Development Bank Index", "Development Bank"),
    ("FINANCE", "Finance Index", "Finance"),
    ("HOTELS", "Hotels And Tourism Index", "Hotels And Tourism"),
    ("HYDROPOWER", "HydroPower Index", "HydroPower"),
    ("INVESTMENT", "Investment Index", "Investment"),
    ("LIFEINSU", "Life Insurance Index", "Life Insurance"),
    ("MANUFACTURE", "Manufacturing And Processing", "Manufacturing And Processing"),
    ("MICROFINANCE", "Microfinance Index", "Microfinance"),
    ("MUTUAL", "Mutual Fund Index", "Mutual Fund"),
    ("NONLIFEINSU", "Non Life Insurance Index", "Non Life Insurance"),
    ("OTHERS", "Others Index", "Others"),
    ("TRADING", "Trading Index", "Trading"),
]

MAIN_INDICES = [
    ("NEPSE", "NEPSE Index"),
    ("SENSITIVE", "Sensitive Index"),
    ("FLOAT", "Float Index"),
    ("SENSITIVE_FLOAT", "Sensitive Float Index"),
]

SECTOR_NAMES = [sector for _, _, sector in SUB_INDICES]

# raw label (lower-cased) -> normalised sector
SECTOR_MAP = {
    "commercial banks": "Banking",
    "commercial bank": "Banking",
    "banking": "Banking",
    "development banks": "Development Bank",
    "development bank": "Development Bank",
    "finance": "Finance",
    "finance companies": "Finance",
    "hotels and tourism": "Hotels And Tourism",
    "hotels & tourism": "Hotels And Tourism",
    "hotel and tourism": "Hotels And Tourism",
    "hydro power": "HydroPower",
    "hydropower": "HydroPower",
    "investment": "Investment",
    "life insurance": "Life Insurance",
    "manufacturing and processing": "Manufacturing And Processing",
    "manufacturing & processing": "Manufacturing And Processing",
    "microfinance": "Microfinance",
    "micro finance": "Microfinance",
    "mutual fund": "Mutual Fund",
    "mutual funds": "Mutual Fund",
    "non life insurance": "Non Life Insurance",
    "non-life insurance": "Non Life Insurance",
    "others": "Others",
    "other": "Others",
    "tradings": "Trading",
    "trading": "Trading",
}


def normalise_sector(raw):
    """Return the normalised sector, or None when the label is unknown.

    Unknown labels are NOT silently put in "Others": the caller decides (the
    crawler pipeline stores "Unclassified" and logs a warning) so a mapping gap
    is visible instead of corrupting the "Others" sub-index.
    """
    return SECTOR_MAP.get((raw or "").strip().lower())
