import json
from datetime import date
from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.models import DailyAnalysis
from apps.companies.models import Company
from apps.market_data.models import DailyPrice, FloorsheetTransaction
from apps.users.company_access import require_company_access
from apps.users.permissions import HasAppPermission
from apps.market_intelligence.models import (
    CompanyTechnicalSnapshot,
    MarketBreadthSnapshot,
    ProxyIndexSnapshot,
    SectorRotationSnapshot,
)
from apps.market_intelligence.indicators import REGISTRY as INDICATOR_REGISTRY
from apps.market_intelligence.indicators import compute as compute_indicator
from apps.market_intelligence.indicators import registry_payload
from apps.market_intelligence.services.sector_rotation import PERIODS
from apps.market_intelligence.services.snapshots import (
    PROXY_METHODOLOGY_VERSION,
    _corporate_action_flags,
    _configured_excluded_dates,
    _decimal,
    _trading_calendar,
)


def _market_context():
    prices = list(DailyPrice.objects.filter(source="crawled").select_related("company").order_by("date", "company_id", "pk"))
    sessions, excluded = _trading_calendar(prices, _configured_excluded_dates())
    analyses = {
        (row.company_id, row.date): row
        for row in DailyAnalysis.objects.filter(date__in=sessions).only(
            "company_id", "date", "previous_close", "daily_return_pct", "volume_ratio"
        )
    }
    flags = _corporate_action_flags(prices, sessions, analyses)
    lookup = {(row.date, row.company_id): row for row in prices}
    return prices, sessions, excluded, analyses, flags, lookup


def _resolve_date(request, sessions):
    requested = request.query_params.get("date")
    if not requested:
        return sessions[-1] if sessions else None
    try:
        day = date.fromisoformat(requested)
    except ValueError:
        return False
    return day if day in sessions else None


class MarketBreadthAPIView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        _, sessions, _, _, _, _ = _market_context()
        day = _resolve_date(request, sessions)
        if day is False:
            return Response({"detail": "date must use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if day is None:
            return Response({"detail": "No market breadth snapshot is available."}, status=status.HTTP_404_NOT_FOUND)
        snapshot = MarketBreadthSnapshot.objects.filter(date=day).first()
        if not snapshot:
            return Response({"detail": "Market breadth has not been computed for this date."}, status=404)
        proxy = ProxyIndexSnapshot.objects.filter(date=day).first()
        return Response({
            "date": snapshot.date,
            "market_session_count": snapshot.market_session_count,
            "universe_label": "tracked stocks",
            "advances": snapshot.advances,
            "declines": snapshot.declines,
            "unchanged": snapshot.unchanged,
            "return_eligible_count": snapshot.return_eligible_count,
            "above_50_dma_count": snapshot.above_50_dma_count,
            "valid_50_dma_count": snapshot.valid_50_dma_count,
            "above_50_dma_pct": snapshot.above_50_dma_pct,
            "above_200_dma_count": snapshot.above_200_dma_count,
            "valid_200_dma_count": snapshot.valid_200_dma_count,
            "above_200_dma_pct": snapshot.above_200_dma_pct,
            "corporate_action_excluded_count": snapshot.corporate_action_excluded_count,
            "proxy_index": {
                "level": proxy.level if proxy else None,
                "methodology_version": proxy.methodology_version if proxy else PROXY_METHODOLOGY_VERSION,
                "computed_at": proxy.computed_at if proxy else None,
            },
            "computed_at": snapshot.computed_at,
        })


class MarketHeatmapAPIView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        prices, sessions, _, analyses, flags, lookup = _market_context()
        group = request.query_params.get("group", "company")
        if group not in ("company", "sector"):
            return Response({"detail": "group must be 'company' or 'sector'."}, status=400)
        day = _resolve_date(request, sessions)
        if day is False:
            return Response({"detail": "date must use YYYY-MM-DD."}, status=400)
        if day is None:
            return Response({"date": None, "group": group, "tiles": [], "universe_label": "tracked stocks"})
        index = sessions.index(day)
        prior_day = sessions[index - 1] if index else None
        breadth_snapshot = MarketBreadthSnapshot.objects.filter(date=day).first()
        day_rows = [row for row in prices if row.date == day]
        company_tiles = []
        for row in day_rows:
            previous = lookup.get((prior_day, row.company_id)) if prior_day else None
            flagged = (row.company_id, day) in flags or (prior_day and (row.company_id, prior_day) in flags)
            close, previous_close = _decimal(row.close), _decimal(previous.close) if previous else None
            change = None
            if not flagged and close is not None and previous_close:
                change = (close - previous_close) / previous_close * 100
            company_tiles.append({
                "id": row.company_id, "symbol": row.company.symbol, "name": row.company.name,
                "sector": row.company.sector, "close": row.close, "change_pct": change,
                "turnover": row.turnover, "possible_corporate_action": flagged,
            })
        if group == "company":
            tiles = company_tiles
        else:
            sectors = {}
            for tile in company_tiles:
                sector = tile["sector"]
                entry = sectors.setdefault(sector, {
                    "sector": sector, "turnover": Decimal("0"), "weighted_change": Decimal("0"),
                    "change_weight": Decimal("0"), "company_count": 0, "excluded_count": 0,
                })
                turnover = _decimal(tile["turnover"]) or Decimal("0")
                entry["turnover"] += turnover
                entry["company_count"] += 1
                if tile["possible_corporate_action"]:
                    entry["excluded_count"] += 1
                elif tile["change_pct"] is not None and turnover > 0:
                    entry["weighted_change"] += Decimal(str(tile["change_pct"])) * turnover
                    entry["change_weight"] += turnover
            tiles = []
            for entry in sectors.values():
                change_weight = entry.pop("change_weight")
                weighted_change = entry.pop("weighted_change")
                entry["change_pct"] = weighted_change / change_weight if change_weight else None
                tiles.append(entry)
        tiles.sort(key=lambda item: item.get("turnover", 0), reverse=True)
        return Response({
            "date": day, "group": group, "size_metric": "turnover",
            "color_metric": "daily change percent", "tiles": tiles,
            "universe_label": "tracked stocks",
            "computed_at": breadth_snapshot.computed_at if breadth_snapshot else None,
        })


class MarketRankingsAPIView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        prices, sessions, _, analyses, flags, lookup = _market_context()
        metric = request.query_params.get("metric", "gainers")
        if metric not in ("gainers", "losers", "volume", "turnover"):
            return Response({"detail": "metric must be gainers, losers, volume, or turnover."}, status=400)
        try:
            limit = min(max(int(request.query_params.get("limit", 20)), 1), 100)
        except (TypeError, ValueError):
            return Response({"detail": "limit must be an integer from 1 to 100."}, status=400)
        day = _resolve_date(request, sessions)
        if day is False:
            return Response({"detail": "date must use YYYY-MM-DD."}, status=400)
        if day is None:
            return Response({"date": None, "metric": metric, "results": [], "universe_label": "tracked stocks"})
        breadth_snapshot = MarketBreadthSnapshot.objects.filter(date=day).first()
        index = sessions.index(day)
        previous_day = sessions[index - 1] if index else None
        rows = []
        for price in prices:
            if price.date != day:
                continue
            analysis = analyses.get((price.company_id, day))
            prior_price = lookup.get((previous_day, price.company_id)) if previous_day else None
            action = (price.company_id, day) in flags or (previous_day and (price.company_id, previous_day) in flags)
            previous_close = _decimal(prior_price.close) if prior_price else None
            close = _decimal(price.close)
            change = ((close - previous_close) / previous_close * 100) if close is not None and previous_close else None
            if metric in ("gainers", "losers") and (change is None or action):
                continue
            rows.append({
                "company_id": price.company_id, "symbol": price.company.symbol,
                "name": price.company.name, "sector": price.company.sector,
                "close": price.close, "change_pct": None if action else change,
                "volume": price.volume, "turnover": price.turnover,
                "volume_ratio": analysis.volume_ratio if analysis else None,
                "possible_corporate_action": bool(action),
            })
        sort_fields = {
            "gainers": lambda row: row["change_pct"],
            "losers": lambda row: row["change_pct"],
            "volume": lambda row: row["volume"],
            "turnover": lambda row: row["turnover"],
        }
        rows.sort(key=sort_fields[metric], reverse=metric != "losers")
        return Response({
            "date": day, "metric": metric, "results": rows[:limit],
            "universe_label": "tracked stocks",
            "computed_at": breadth_snapshot.computed_at if breadth_snapshot else None,
        })


class SectorRotationAPIView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_market_data"

    def get(self, request):
        period = request.query_params.get("period", "1w")
        if period not in PERIODS:
            return Response({"detail": "period must be 1w, 1m, or 3m."}, status=400)
        field = f"return_{period}"
        rank_field = f"rank_{period}"
        previous_field = f"previous_rank_{period}"
        qs = SectorRotationSnapshot.objects.all()
        requested = request.query_params.get("date")
        if requested:
            try:
                qs = qs.filter(date=date.fromisoformat(requested))
            except ValueError:
                return Response({"detail": "date must use YYYY-MM-DD."}, status=400)
        else:
            latest = qs.order_by("-date").values_list("date", flat=True).first()
            qs = qs.filter(date=latest) if latest else qs.none()
        rows = qs.order_by(rank_field, "sector")
        return Response({
            "date": rows.values_list("date", flat=True).first(), "period": period,
            "methodology": "Turnover-weighted sector return using observed valid sessions.",
            "results": [{
                "sector": row.sector, "return_pct": getattr(row, field),
                "rank": getattr(row, rank_field), "previous_rank": getattr(row, previous_field),
                "rank_change": (getattr(row, previous_field) - getattr(row, rank_field))
                    if getattr(row, previous_field) and getattr(row, rank_field) else None,
                "turnover": row.turnover, "company_count": row.company_count,
                "computed_at": row.computed_at,
            } for row in rows],
            "universe_label": "tracked stocks",
        })


class RelativeStrengthAPIView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    def get(self, request):
        try:
            company_id = int(request.query_params["company_id"])
        except (KeyError, TypeError, ValueError):
            return Response({"detail": "company_id is required and must be an integer."}, status=400)
        company = get_object_or_404(Company, pk=company_id, is_active=True)
        require_company_access(request.user, company.pk)
        period = request.query_params.get("period", "1m")
        if period not in PERIODS:
            return Response({"detail": "period must be 1w, 1m, or 3m."}, status=400)
        _, sessions, _, _, flags, lookup = _market_context()
        if not sessions:
            return Response({"detail": "Insufficient history."}, status=404)
        count = PERIODS[period]
        end_index = len(sessions) - 1
        start_index = end_index - count
        if start_index < 0:
            return Response({"status": "insufficient_history", "period": period})
        start_day, end_day = sessions[start_index], sessions[end_index]
        start = lookup.get((start_day, company.pk))
        end = lookup.get((end_day, company.pk))
        if not start or not end:
            return Response({"status": "insufficient_history", "period": period})
        observed = sum(
            1 for session in sessions[start_index:end_index + 1]
            if (session, company.pk) in lookup and (company.pk, session) not in flags
        )
        required = (len(sessions[start_index:end_index + 1]) * 95 + 99) // 100
        if observed < required:
            return Response({"status": "insufficient_history", "period": period})
        if any((company.pk, sessions[i]) in flags for i in range(start_index, end_index + 1)):
            return Response({"status": "possible_corporate_action", "period": period})
        company_return = (Decimal(end.close) - Decimal(start.close)) / Decimal(start.close) * 100
        proxy_start = ProxyIndexSnapshot.objects.filter(date=start_day).first()
        proxy_end = ProxyIndexSnapshot.objects.filter(date=end_day).first()
        if not proxy_start or not proxy_end or not proxy_start.level or not proxy_end.level:
            return Response({"status": "proxy_history_unavailable", "period": period})
        proxy_return = (proxy_end.level - proxy_start.level) / proxy_start.level * 100
        return Response({
            "status": "ok", "company_id": company.pk, "symbol": company.symbol,
            "period": period, "start_date": start_day, "end_date": end_day,
            "company_return_pct": company_return, "proxy_return_pct": proxy_return,
            "relative_strength_pct": company_return - proxy_return,
            "proxy_label": "Turnover-weighted market proxy (not official NEPSE index)",
            "methodology_version": proxy_end.methodology_version,
            "computed_at": proxy_end.computed_at,
        })


class CompanyTechnicalsAPIView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    def get(self, request, company_id):
        company = get_object_or_404(Company, pk=company_id, is_active=True)
        require_company_access(request.user, company.pk)
        snapshot = CompanyTechnicalSnapshot.objects.filter(company=company).first()
        if not snapshot:
            return Response({"status": "insufficient_history", "detail": "Technical snapshots are not computed yet."}, status=404)
        return Response({
            "company_id": company.pk, "symbol": company.symbol, "date": snapshot.date,
            "support_20": snapshot.support_20, "resistance_20": snapshot.resistance_20,
            "support_60": snapshot.support_60, "resistance_60": snapshot.resistance_60,
            "breakout_20_up": snapshot.breakout_20_up, "breakout_20_down": snapshot.breakout_20_down,
            "breakout_55_up": snapshot.breakout_55_up, "breakout_55_down": snapshot.breakout_55_down,
            "patterns": snapshot.patterns, "dma_50": snapshot.dma_50, "dma_200": snapshot.dma_200,
            "signal": snapshot.signal, "signal_score": snapshot.signal_score,
            "history_sessions": snapshot.history_sessions,
            "sufficient_history": snapshot.sufficient_history,
            "status": snapshot.signal if snapshot.signal in ("insufficient_history", "possible_corporate_action") else "ok",
            "possible_corporate_action": snapshot.possible_corporate_action,
            "disclaimer": "Technical signals are computed from historical prices and are not investment advice.",
            "computed_at": snapshot.computed_at,
        })


MAX_INDICATORS_PER_REQUEST = 20
# Only crawled prices are used. Rows marked "unverified" predate source tracking and are largely
# synthetic demo data (Friday sessions, daily moves far beyond the 10% circuit), so they never feed indicators.
PRICE_SOURCES = ("crawled",)


class IndicatorRegistryAPIView(APIView):
    """Every available indicator with its parameters, outputs and display hints; drives the chart picker."""

    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    def get(self, request):
        return Response(registry_payload())


class CompanyIndicatorSeriesAPIView(APIView):
    """Compute one or more registry indicators for a company.

    Query: ``specs`` = JSON list of {"id": ..., "params": {...}}; optional ``start_date`` /
    ``end_date`` (YYYY-MM-DD); ``benchmark`` = proxy (default, the market proxy index) | a company id.

    Indicators run over the full history up to end_date and are then cut to start_date, so the
    range never restarts a warm-up. Range-scoped indicators (anchored VWAP, volume profile) run on
    the selected range only.
    """

    permission_classes = [HasAppPermission]
    permission_key = "view_analysis"

    def get(self, request, company_id):
        company = get_object_or_404(Company, pk=company_id, is_active=True)
        require_company_access(request.user, company.pk)

        try:
            specs = json.loads(request.query_params.get("specs", "[]"))
            if not isinstance(specs, list) or not all(isinstance(s, dict) and "id" in s for s in specs):
                raise ValueError
        except ValueError:
            return Response({"detail": 'specs must be a JSON list like [{"id": "rsi", "params": {"period": 14}}].'},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(specs) > MAX_INDICATORS_PER_REQUEST:
            return Response({"detail": f"At most {MAX_INDICATORS_PER_REQUEST} indicators per request."},
                            status=status.HTTP_400_BAD_REQUEST)
        unknown = [str(s["id"]) for s in specs if s["id"] not in INDICATOR_REGISTRY]
        if unknown:
            return Response({"detail": f"Unknown indicator(s): {', '.join(unknown)}."},
                            status=status.HTTP_400_BAD_REQUEST)

        bounds = {}
        for name in ("start_date", "end_date"):
            raw = request.query_params.get(name)
            try:
                bounds[name] = date.fromisoformat(raw) if raw else None
            except ValueError:
                return Response({"detail": f"{name} must use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        start, end = bounds["start_date"], bounds["end_date"]
        sources = PRICE_SOURCES

        prices = DailyPrice.objects.filter(company=company, source__in=sources).order_by("date")
        if end:
            prices = prices.filter(date__lte=end)
        rows = list(prices.values_list("date", "open", "high", "low", "close", "volume"))
        dates = [r[0] for r in rows]
        data = {
            "date": dates,
            "open": [float(r[1]) for r in rows], "high": [float(r[2]) for r in rows],
            "low": [float(r[3]) for r in rows], "close": [float(r[4]) for r in rows],
            "volume": [int(r[5] or 0) for r in rows],
        }
        scopes = {INDICATOR_REGISTRY[s["id"]].scope for s in specs}
        benchmark_label = None
        if "market" in scopes:
            data["universe"] = self._universe(sources, end)
        if "benchmark" in scopes:
            data["benchmark"], benchmark_label = self._benchmark(request, dates, sources)
            if data["benchmark"] is None:
                return Response({"detail": benchmark_label}, status=status.HTTP_400_BAD_REQUEST)
        if "floorsheet" in scopes:
            data["trades"] = [
                (d, seq, float(rate), float(qty))
                for d, seq, rate, qty in FloorsheetTransaction.objects.filter(company=company)
                .order_by("date", "transaction_id").values_list("date", "transaction_id", "rate", "quantity")
            ]

        # Bars before start_date are warm-up only. Range-scoped indicators get just the selected bars.
        first = next((i for i, d in enumerate(dates) if start is None or d >= start), len(dates))
        per_bar = ("date", "open", "high", "low", "close", "volume", "benchmark")
        ranged = {key: (values[first:] if key in per_bar else values) for key, values in data.items()}

        results = []
        for spec in specs:
            indicator = INDICATOR_REGISTRY[spec["id"]]
            try:
                if indicator.scope == "range":
                    result = compute_indicator(indicator.id, ranged, spec.get("params"))
                else:
                    result = compute_indicator(indicator.id, data, spec.get("params"))
                    result["outputs"] = {k: v[first:] for k, v in result["outputs"].items()}
            except ValueError as exc:
                results.append({"id": indicator.id, "error": str(exc)})
                continue
            result["outputs"] = {
                key: [round(v, 6) if isinstance(v, float) else v for v in values]
                for key, values in result["outputs"].items()
            }
            results.append({"id": indicator.id, **result})

        return Response({
            "company_id": company.pk, "symbol": company.symbol,
            "benchmark": benchmark_label, "dates": dates[first:], "results": results,
            "disclaimer": "Technical indicators are computed from historical prices and are not investment advice.",
        })

    @staticmethod
    def _universe(sources, end):
        prices = DailyPrice.objects.filter(company__is_active=True, source__in=sources)
        if end:
            prices = prices.filter(date__lte=end)
        universe = {}
        for company_id, day, close, volume, high, low in prices.values_list(
            "company_id", "date", "close", "volume", "high", "low"
        ):
            universe.setdefault(company_id, {})[day] = (float(close), float(volume or 0), float(high), float(low))
        return list(universe.values())

    @staticmethod
    def _benchmark(request, dates, sources):
        choice = request.query_params.get("benchmark", "proxy")
        if choice == "proxy":
            levels = dict(ProxyIndexSnapshot.objects.exclude(level=None).values_list("date", "level"))
            return [float(levels[d]) if d in levels else None for d in dates], "Market proxy index (not official NEPSE)"
        try:
            other = Company.objects.get(pk=int(choice), is_active=True)
        except (ValueError, Company.DoesNotExist):
            return None, "benchmark must be proxy or an active company id."
        require_company_access(request.user, other.pk)
        closes = dict(DailyPrice.objects.filter(company=other, source__in=sources).values_list("date", "close"))
        return [float(closes[d]) if d in closes else None for d in dates], other.symbol
