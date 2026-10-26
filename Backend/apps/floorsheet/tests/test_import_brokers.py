# Broker directory import and response fallback coverage.
import csv
import json
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.analysis.api.serializers import BrokerActivitySerializer
from apps.floorsheet.models import Broker
from crawlers.crawlers.pipelines import BrokerPipeline
from crawlers.crawlers.spiders.brokers import BrokersSpider
from scrapy import Request
from scrapy.http import TextResponse


class BrokerDirectoryTests(TestCase):
    def test_import_brokers_is_idempotent_and_updates_rows(self):
        csv_path = Path(__file__).parent / "_brokers_test.csv"
        try:
            with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=["broker_code", "name", "short_name", "logo_filename"])
                writer.writeheader()
                writer.writerow({"broker_code": "58", "name": "Alpha Securities", "short_name": "Alpha", "logo_filename": "alpha.svg"})
            call_command("import_brokers", str(csv_path), stdout=None)
            call_command("import_brokers", str(csv_path), stdout=None)
        finally:
            csv_path.unlink(missing_ok=True)

        self.assertEqual(Broker.objects.count(), 1)
        broker = Broker.objects.get(broker_code="58")
        self.assertEqual(broker.name, "Alpha Securities")
        self.assertEqual(broker.logo, "alpha.svg")

    def test_missing_directory_row_uses_broker_code_fallback(self):
        payload = BrokerActivitySerializer([{
            "broker": "999",
            "buy_quantity": 0,
            "sell_quantity": 0,
            "net_quantity": 0,
            "buy_value": 0,
            "sell_value": 0,
            "net_value": 0,
            "total_quantity": 0,
            "total_value": 0,
            "buy_trades": 0,
            "sell_trades": 0,
            "trades": 0,
        }], many=True).data[0]
        self.assertEqual(payload["broker_code"], "999")
        self.assertEqual(payload["name"], "Broker 999")
        self.assertEqual(payload["short_name"], "Broker 999")
        self.assertIsNone(payload["logo_url"])

    def test_spider_parses_sample_and_requests_more_pages_if_api_caps_limit(self):
        payload = {
            "success": True,
            "data": {
                "total": 91,
                "page": 1,
                "limit": 20,
                "brokers": [{
                    "id": 158,
                    "member_code": 58,
                    "member_name": "Naasa Securities Co. Ltd.",
                    "tms_link": "tms58.nepsetms.com.np",
                    "total_transactions": 10462,
                    "total_turnover": 733387361.58,
                    "total_buy_turnover": 436584730.2,
                    "total_sell_turnover": 296802631.38,
                    "rank": 1,
                    "date": "2026-09-30",
                }],
            },
        }
        url = "https://nepseportfoliotracker.app/api/brokers?page=1&limit=100"
        response = TextResponse(
            url=url,
            request=Request(url),
            body=json.dumps(payload).encode("utf-8"),
            encoding="utf-8",
        )

        output = list(BrokersSpider().parse(response))

        self.assertEqual(output[0], {
            "broker_no": 58,
            "name": "Naasa Securities Co. Ltd.",
            "tms_link": "tms58.nepsetms.com.np",
        })
        self.assertEqual(output[1].meta["page"], 2)
        self.assertIn("limit=100", output[1].url)

    def test_broker_pipeline_is_idempotent(self):
        pipeline = BrokerPipeline()
        item = {
            "broker_no": 58,
            "name": "Naasa Securities Co. Ltd.",
            "tms_link": "tms58.nepsetms.com.np",
        }

        pipeline.process_item(item, spider=None)
        pipeline.process_item(item, spider=None)

        self.assertEqual(Broker.objects.filter(broker_no=58).count(), 1)
        broker = Broker.objects.get(broker_no=58)
        self.assertEqual(broker.name, item["name"])
