from django.db import transaction

from apps.companies.models import Company

from ..models import DailyPrice


@transaction.atomic
def import_daily_price(data):

    company = Company.objects.get(
        symbol=data["symbol"].upper().strip()
    )

    price, created = (
        DailyPrice.objects.update_or_create(
            company=company,
            date=data["date"],
            defaults={
                "open": data["open"],
                "high": data["high"],
                "low": data["low"],
                "close": data["close"],
                "volume": data["volume"],
                "turnover": data["turnover"],
            },
        )
    )

    return price, created