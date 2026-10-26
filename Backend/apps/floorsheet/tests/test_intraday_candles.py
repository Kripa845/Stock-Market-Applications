"""Intraday candles: bucketing, dedupe, idempotent rebuilds, session boundaries and the API."""

from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.floorsheet.models import FloorsheetTransaction, IntradayCandle
from apps.floorsheet.services import intraday_candles, sharehub_floorsheet
from apps.floorsheet.services.intraday_candles import bucket_start_for, rebuild_day, rebuild_range
from apps.floorsheet.services.sharehub_time import parse_sharehub_time
from apps.users.models import User

NPT = ZoneInfo("Asia/Kathmandu")
DAY = date(2026, 10, 9)


def at(hour, minute, second=0, micro=0, day=DAY):
    return datetime(day.year, day.month, day.day, hour, minute, second, micro, tzinfo=NPT)


class CandleTestCase(TestCase):

    def setUp(self):
        self.company = Company.objects.create(symbol="NABIL", name="Nabil Bank", sector="Banking")
        self.seq = 0

    def trade(self, when, rate, quantity, txn=None, company=None, day=DAY):
        self.seq += 1
        return FloorsheetTransaction.objects.create(
            company=company or self.company,
            date=day,
            trade_time=when,
            transaction_id=txn or f"{day:%Y%m%d}01{self.seq:06d}",
            buyer_broker="1",
            seller_broker="2",
            quantity=quantity,
            rate=Decimal(rate),
            amount=Decimal(rate) * quantity if when is not None else None,
        )

    def candles(self, interval):
        return list(
            IntradayCandle.objects.filter(company=self.company, interval=interval)
            .order_by("bucket_start")
            .values("bucket_start", "open", "high", "low", "close", "volume", "turnover", "trade_count")
        )


class BucketingTests(CandleTestCase):

    def test_ohlcv_on_a_known_trade_set(self):
        self.trade(at(11, 0, 5), "100", 2)
        self.trade(at(11, 0, 45), "103", 3)
        self.trade(at(11, 0, 58), "99", 4)
        self.trade(at(11, 3, 10), "101", 10)
        self.trade(at(11, 7, 0), "104", 1)

        rebuild_day(DAY)

        one = self.candles("1m")
        self.assertEqual([c["bucket_start"] for c in one], [at(11, 0), at(11, 3), at(11, 7)])
        self.assertEqual(
            {k: one[0][k] for k in ("open", "high", "low", "close", "volume", "trade_count")},
            {"open": Decimal("100"), "high": Decimal("103"), "low": Decimal("99"),
             "close": Decimal("99"), "volume": 9, "trade_count": 3},
        )
        self.assertEqual(one[0]["turnover"], Decimal("200") + Decimal("309") + Decimal("396"))

        five = self.candles("5m")
        self.assertEqual([c["bucket_start"] for c in five], [at(11, 0), at(11, 5)])
        self.assertEqual(
            {k: five[0][k] for k in ("open", "high", "low", "close", "volume", "trade_count")},
            {"open": Decimal("100"), "high": Decimal("103"), "low": Decimal("99"),
             "close": Decimal("101"), "volume": 19, "trade_count": 4},
        )
        hour = self.candles("1h")
        self.assertEqual(len(hour), 1)
        self.assertEqual((hour[0]["open"], hour[0]["close"], hour[0]["volume"]), (Decimal("100"), Decimal("104"), 20))

    def test_out_of_order_rows_are_ordered_by_time(self):
        # Inserted newest first, the way ShareHub pages arrive.
        self.trade(at(11, 0, 50), "105", 1)
        self.trade(at(11, 0, 30), "102", 1)
        self.trade(at(11, 0, 10), "100", 1)

        rebuild_day(DAY)

        candle = self.candles("1m")[0]
        self.assertEqual((candle["open"], candle["close"]), (Decimal("100"), Decimal("105")))

    def test_same_timestamp_is_ordered_by_trade_id(self):
        self.trade(at(11, 0, 10), "110", 1, txn="2026100901000002")
        self.trade(at(11, 0, 10), "100", 1, txn="2026100901000001")

        rebuild_day(DAY)

        candle = self.candles("1m")[0]
        self.assertEqual((candle["open"], candle["close"]), (Decimal("100"), Decimal("110")))

    def test_trades_without_time_make_no_candles(self):
        self.trade(None, "100", 5)

        self.assertEqual(rebuild_day(DAY), 0)
        self.assertFalse(IntradayCandle.objects.exists())

    def test_companies_are_kept_apart(self):
        other = Company.objects.create(symbol="NICA", name="NIC Asia", sector="Banking")
        self.trade(at(11, 1), "100", 1)
        self.trade(at(11, 1), "500", 7, company=other)

        rebuild_day(DAY)

        self.assertEqual(self.candles("1m")[0]["volume"], 1)
        self.assertEqual(IntradayCandle.objects.get(company=other, interval="1m").volume, 7)


class SessionBoundaryTests(CandleTestCase):

    def test_bucket_alignment_and_clamping(self):
        self.assertEqual(bucket_start_for(at(10, 58), 5, DAY), at(11, 0))      # pre-open
        self.assertEqual(bucket_start_for(at(11, 4, 59), 5, DAY), at(11, 0))
        self.assertEqual(bucket_start_for(at(11, 5), 5, DAY), at(11, 5))
        self.assertEqual(bucket_start_for(at(14, 59, 59, 998387), 5, DAY), at(14, 55))
        self.assertEqual(bucket_start_for(at(14, 59, 59), 60, DAY), at(14, 0))
        self.assertEqual(bucket_start_for(at(15, 0, 1), 15, DAY), at(14, 45))  # after close
        self.assertEqual(bucket_start_for(at(11, 20), 30, DAY), at(11, 0))

    def test_no_candle_outside_the_session_and_volume_is_kept(self):
        self.trade(at(10, 58), "99", 3)
        self.trade(at(11, 0, 1), "100", 1)
        self.trade(at(14, 59, 59, 998387), "120", 2)
        self.trade(at(15, 0, 2), "121", 4)

        rebuild_day(DAY)

        session_open, session_close = intraday_candles.session_bounds(DAY)
        for candle in IntradayCandle.objects.all():
            self.assertGreaterEqual(candle.bucket_start, session_open)
            self.assertLess(candle.bucket_start, session_close)
        for interval in intraday_candles.INTERVALS:
            self.assertEqual(sum(c["volume"] for c in self.candles(interval)), 10, interval)

        one = self.candles("1m")
        self.assertEqual(one[0]["bucket_start"], at(11, 0))
        self.assertEqual(one[0]["open"], Decimal("99"))       # pre-open trade opens the session
        self.assertEqual(one[-1]["bucket_start"], at(14, 59))
        self.assertEqual(one[-1]["close"], Decimal("121"))


class RebuildTests(CandleTestCase):

    def test_rebuild_is_idempotent(self):
        self.trade(at(11, 0, 5), "100", 2)
        self.trade(at(12, 30), "101", 3)

        first = rebuild_day(DAY)
        snapshot = sorted(IntradayCandle.objects.values_list("interval", "bucket_start", "close", "volume"))
        second = rebuild_day(DAY)

        self.assertEqual(first, second)
        self.assertEqual(IntradayCandle.objects.count(), first)
        self.assertEqual(
            sorted(IntradayCandle.objects.values_list("interval", "bucket_start", "close", "volume")), snapshot,
        )

    def test_late_trade_updates_and_stale_bucket_is_removed(self):
        stale = self.trade(at(11, 10), "90", 1)
        self.trade(at(11, 0, 30), "100", 1)
        rebuild_day(DAY)
        self.assertEqual(len(self.candles("1m")), 2)

        stale.delete()
        self.trade(at(11, 0, 1), "95", 5)   # late row, earlier than the stored open
        rebuild_day(DAY)

        one = self.candles("1m")
        self.assertEqual([c["bucket_start"] for c in one], [at(11, 0)])
        self.assertEqual((one[0]["open"], one[0]["close"], one[0]["volume"]), (Decimal("95"), Decimal("100"), 6))

    def test_rebuild_range_and_command(self):
        other_day = date(2026, 10, 8)
        self.trade(at(11, 0, day=other_day), "100", 1, day=other_day)
        self.trade(at(11, 0), "101", 1)

        written = rebuild_range(other_day, DAY)
        self.assertEqual(set(written), {"2026-10-08", "2026-10-09"})

        out = StringIO()
        call_command("rebuild_intraday_candles", "--from", "2026-10-09", "--symbols", "nabil",
                     "--intervals", "1m,5m", stdout=out)
        self.assertIn("2026-10-09: 2 candles written", out.getvalue())


class ShareHubDedupeTests(CandleTestCase):

    def item(self, contract_id, when, rate="100", qty=10, symbol="NABIL"):
        return {
            "symbol": symbol, "contractId": contract_id, "buyerMemberId": "62", "sellerMemberId": "49",
            "contractQuantity": qty, "contractRate": float(rate), "contractAmount": float(rate) * qty,
            "businessDate": "2026-10-09T00:00:00Z", "tradeTime": when,
        }

    def test_parse_trade_time_reads_the_clock_as_nepal_time(self):
        parsed = parse_sharehub_time("2026-10-09T14:59:59.998387Z")
        self.assertEqual(parsed, at(14, 59, 59, 998387))

    def test_existing_contract_gains_time_and_is_not_duplicated(self):
        # Same contract stored earlier by the ShareSansar spider, without a time.
        self.trade(None, "100", 10, txn="2026100901000022")
        items = [
            self.item(2026100901000022, "2026-10-09T11:00:05.1Z"),
            self.item(2026100901000023, "2026-10-09T11:00:06Z"),
            self.item(2026100901000023, "2026-10-09T11:00:06Z"),   # repeated across pages
            self.item(2026100901000099, "2026-10-09T11:00:07Z", symbol="NICA"),
        ]
        with mock.patch.object(sharehub_floorsheet, "fetch_company_day", return_value=items):
            first = sharehub_floorsheet.sync_company_day(self.company, DAY)
            second = sharehub_floorsheet.sync_company_day(self.company, DAY)

        self.assertEqual((first["found"], first["created"], first["updated"]), (2, 1, 1))
        self.assertEqual((second["created"], second["updated"]), (0, 2))
        self.assertEqual(FloorsheetTransaction.objects.count(), 2)
        self.assertEqual(
            FloorsheetTransaction.objects.get(transaction_id="2026100901000022").trade_time,
            at(11, 0, 5, 100000),
        )

    def test_wrong_business_date_is_rejected(self):
        bad = self.item(1, "2026-10-08T11:00:00Z")
        bad["businessDate"] = "2026-10-08T00:00:00Z"
        with self.assertRaises(sharehub_floorsheet.ShareHubError):
            sharehub_floorsheet.build_transactions(self.company, DAY, [bad])

    def test_changed_format_skips_only_that_company(self):
        nica = Company.objects.create(symbol="NICA", name="NIC Asia", sector="Banking")
        renamed = self.item(1, "2026-10-09T11:00:00Z")
        renamed["contractNo"] = renamed.pop("contractId")      # ShareHub renamed a field
        good = self.item(2, "2026-10-09T11:00:01Z", symbol="NICA")
        by_symbol = {"NABIL": [renamed], "NICA": [good]}
        with mock.patch.object(sharehub_floorsheet, "fetch_company_day",
                               side_effect=lambda day, symbol, known_ids: by_symbol[symbol]), \
                mock.patch.object(sharehub_floorsheet.time, "sleep"):
            summary = sharehub_floorsheet.sync_day(DAY, [self.company, nica])

        self.assertEqual(summary["companies"], 1)
        self.assertEqual(len(summary["errors"]), 1)
        self.assertIn("NABIL", summary["errors"][0])
        self.assertEqual(list(FloorsheetTransaction.objects.values_list("company__symbol", flat=True)), ["NICA"])


class ShareHubRequestTests(SimpleTestCase):

    def response(self, body):
        resp = mock.MagicMock()
        resp.__enter__.return_value = StringIO(body)
        return resp

    def test_request_sends_user_agent_and_timeout(self):
        with mock.patch.object(sharehub_floorsheet.urllib.request, "urlopen",
                               return_value=self.response('{"data": {"content": []}}')) as urlopen:
            data = sharehub_floorsheet.request_floorsheet({"Size": 100})
        request, = urlopen.call_args.args
        self.assertEqual(data, {"content": []})
        self.assertEqual(request.get_header("User-agent"), sharehub_floorsheet.USER_AGENT)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], sharehub_floorsheet.TIMEOUT_SECONDS)

    def test_non_json_response_raises_instead_of_crashing(self):
        with mock.patch.object(sharehub_floorsheet.urllib.request, "urlopen",
                               return_value=self.response("<html>maintenance</html>")):
            with self.assertRaises(sharehub_floorsheet.ShareHubError):
                sharehub_floorsheet.request_floorsheet({"Size": 100})


class FetchPagingTests(SimpleTestCase):

    def page(self, ids, index, has_next):
        return {"pageIndex": index, "hasNext": has_next, "content": [{"contractId": i} for i in ids]}

    def test_incremental_fetch_stops_at_a_fully_known_page(self):
        pages = {1: self.page([5, 4], 1, True), 2: self.page([3, 2], 2, True), 3: self.page([1], 3, False)}
        with mock.patch.object(sharehub_floorsheet, "fetch_page", side_effect=lambda d, s, p: pages[p]), \
                mock.patch.object(sharehub_floorsheet.time, "sleep"):
            items = sharehub_floorsheet.fetch_company_day(DAY, "NABIL", known_ids={"3", "2", "1"})
            full = sharehub_floorsheet.fetch_company_day(DAY, "NABIL")

        self.assertEqual([i["contractId"] for i in items], [5, 4, 3, 2])
        self.assertEqual(len(full), 5)


class IntradayEndpointTests(CandleTestCase):

    def setUp(self):
        super().setUp()
        user = User.objects.create_user(username="intraday-admin", email="intraday@example.test",
                                        password="unused-test-password", role=User.Role.ADMIN)
        self.client = APIClient()
        self.client.force_authenticate(user)

    def url(self, symbol="NABIL"):
        return f"/api/stocks/{symbol}/intraday/"

    def test_defaults_to_latest_day_and_5m(self):
        old_day = date(2026, 10, 8)
        self.trade(at(11, 0, day=old_day), "90", 1, day=old_day)
        self.trade(at(11, 0, 5), "100", 2)
        self.trade(at(11, 6), "102", 3)
        rebuild_range(old_day, DAY)

        response = self.client.get(self.url("nabil"))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body["symbol"], body["interval"], body["date"], body["count"]), ("NABIL", "5m", "2026-10-09", 2))
        first = body["candles"][0]
        self.assertEqual(first["time"], "2026-10-09T11:00:00+05:45")
        self.assertEqual(set(first) >= {"time", "open", "high", "low", "close", "volume"}, True)
        self.assertEqual((Decimal(first["open"]), first["volume"]), (Decimal("100"), 2))

    def test_explicit_date_and_interval(self):
        self.trade(at(11, 0, 5), "100", 2)
        rebuild_day(DAY)

        body = self.client.get(self.url(), {"interval": "1h", "date": "2026-10-09"}).json()
        self.assertEqual((body["interval"], body["count"]), ("1h", 1))

        empty = self.client.get(self.url(), {"date": "2026-10-01"}).json()
        self.assertEqual((empty["date"], empty["count"], empty["candles"]), ("2026-10-01", 0, []))

    def test_no_candles_at_all(self):
        body = self.client.get(self.url()).json()
        self.assertEqual((body["date"], body["candles"]), (None, []))

    def test_validation_errors(self):
        bad_interval = self.client.get(self.url(), {"interval": "7m"})
        self.assertEqual(bad_interval.status_code, 400)
        self.assertIn("interval", bad_interval.json())

        bad_date = self.client.get(self.url(), {"date": "09-10-2026"})
        self.assertEqual(bad_date.status_code, 400)
        self.assertIn("date", bad_date.json())

        self.assertEqual(self.client.get(self.url("NOPE")).status_code, 404)

    def test_requires_authentication(self):
        self.assertIn(APIClient().get(self.url()).status_code, (401, 403))


class NepalTimeTests(CandleTestCase):
    """ShareHub's "Z" is not UTC: times are stored, bucketed and served as Nepal time."""

    def test_sharehub_time_keeps_the_nepal_clock(self):
        parsed = parse_sharehub_time("2026-10-11T14:59:59Z")
        self.assertEqual(parsed, datetime(2026, 10, 11, 14, 59, 59, tzinfo=NPT))
        self.assertEqual(parsed.isoformat(), "2026-10-11T14:59:59+05:45")
        self.assertNotEqual(parsed.astimezone(NPT).hour, 20)   # not 20:44 NPT
        self.assertEqual(parse_sharehub_time("2026-10-11T11:00:00.5Z"), datetime(2026, 10, 11, 11, 0, 0, 500000, tzinfo=NPT))

    def test_trade_at_eleven_lands_in_the_eleven_bucket(self):
        self.trade(parse_sharehub_time("2026-10-09T11:00:00Z"), "100", 1)
        rebuild_day(DAY)
        for interval in intraday_candles.INTERVALS:
            self.assertEqual(self.candles(interval)[0]["bucket_start"], at(11, 0), interval)

    def test_serialized_time_has_nepal_offset(self):
        from django.utils import timezone

        from apps.floorsheet.api.serializers import IntradayCandleSerializer

        self.trade(at(11, 0), "100", 1)
        rebuild_day(DAY)
        with timezone.override("UTC"):   # even with another active time zone
            data = IntradayCandleSerializer(IntradayCandle.objects.filter(interval="5m"), many=True).data
        self.assertEqual(data[0]["time"], "2026-10-09T11:00:00+05:45")
        self.assertIn("+05:45", data[0]["time"])
        self.assertEqual(Decimal(data[0]["turnover"]), Decimal("100"))

    def test_no_candle_outside_the_session_window(self):
        for when in (at(10, 55), at(11, 0), at(12, 31), at(14, 59, 59), at(15, 3)):
            self.trade(when, "100", 1)
        rebuild_day(DAY)
        for candle in IntradayCandle.objects.all():
            local = candle.bucket_start.astimezone(NPT)
            self.assertGreaterEqual(local, at(11, 0))
            self.assertLess(local, at(15, 0))


class FixShareHubTimesCommandTests(CandleTestCase):

    def test_dry_run_reports_and_apply_and_undo_round_trip(self):
        good = self.trade(at(14, 59, 59), "100", 1)
        # 11:00 NPT stored as if the "Z" were UTC -> 16:45 NPT.
        shifted = self.trade(datetime(2026, 10, 9, 11, 0, tzinfo=ZoneInfo("UTC")), "100", 1)
        self.assertEqual(shifted.trade_time, at(16, 45))

        out = StringIO()
        call_command("fix_sharehub_trade_times", "--dry-run", stdout=out)
        self.assertIn("Rows that would change: 1", out.getvalue())
        shifted.refresh_from_db()
        self.assertEqual(shifted.trade_time, at(16, 45))         # dry run wrote nothing

        out = StringIO()
        call_command("fix_sharehub_trade_times", stdout=out)
        shifted.refresh_from_db()
        good.refresh_from_db()
        self.assertEqual(shifted.trade_time, at(11, 0))
        self.assertEqual(good.trade_time, at(14, 59, 59))        # correct rows untouched

        backup = next(line.split(": ", 1)[1] for line in out.getvalue().splitlines() if line.startswith("Backup written"))
        try:
            call_command("fix_sharehub_trade_times", "--undo", backup, stdout=StringIO())
            shifted.refresh_from_db()
            self.assertEqual(shifted.trade_time, at(16, 45))
        finally:
            from pathlib import Path
            Path(backup).unlink(missing_ok=True)
