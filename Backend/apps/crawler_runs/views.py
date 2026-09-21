import logging
import os
import subprocess

from celery.result import AsyncResult
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from apps.users.permissions import HasAppPermission, HasViewMethodPermissions

from .models import CrawlRun
from .serializers import (
    CrawlRunSerializer,
    TriggerCrawlRequestSerializer,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source resolution helpers
# ---------------------------------------------------------------------------

NEWS_SOURCE_MAP = {
    "sharesansar": "sharesansar",
    "arthaKhabar": "arthakhabar",
    "arthakhabar": "arthakhabar",
    "fiscal Nepal": "fiscalnepal",
    "fiscalnepal": "fiscalnepal",
    "merolagani": "merolagani",
    "nepali paisa": "nepalipaisa",
    "nepalipaisa": "nepalipaisa",
}

# Crawl types that should not run concurrently with themselves.
# Two NEWS crawls at the same time make no sense; but NEWS and TRADING
# can coexist safely because they hit different spiders/databases.
_EXCLUSIVE_TYPES = {
    CrawlRun.CrawlType.NEWS,
    CrawlRun.CrawlType.TRADING,
    CrawlRun.CrawlType.FLOORSHEET,
    CrawlRun.CrawlType.FLOORSHEET_SAMPLE,
}


def _resolve_sources(crawl_type, source):
    """Return the list of spider names for the given crawl type + source."""
    if crawl_type == "trading":
        return ["trading_data"]

    if crawl_type == "floorsheet":
        return ["floorsheet"]

    if crawl_type == "news":
        if source == "all":
            return [
                "sharesansar",
                "arthakhabar",
                "fiscalnepal",
                "merolagani",
                "nepsealpha",
                "bizmandu",
            ]
        spider = NEWS_SOURCE_MAP.get(
            source,
            source.lower().replace(" ", ""),
        )
        return [spider]

    # "all"
    return [
        "sharesansar",
        "merolagani",
        "bizmandu",
        "nepsealpha",
        "arthakhabar",
        "fiscalnepal",
        "trading_data",
        "floorsheet",
    ]


# ---------------------------------------------------------------------------
# Duplicate-run guard (race-condition safe)
# ---------------------------------------------------------------------------

def _check_active_crawl(crawl_type):
    """
    Return an existing active CrawlRun of the same type, or None.

    Uses SELECT FOR UPDATE so two concurrent requests cannot both pass
    the check and both create a duplicate.  Must be called inside an
    atomic block.
    """
    if crawl_type not in _EXCLUSIVE_TYPES:
        return None

    return (
        CrawlRun.objects
        .select_for_update(skip_locked=True)
        .filter(
            crawl_type=crawl_type,
            status__in=[
                CrawlRun.Status.PENDING,
                CrawlRun.Status.RUNNING,
            ],
        )
        .first()
    )


# ---------------------------------------------------------------------------
# List / Create
# ---------------------------------------------------------------------------

class CrawlRunListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [HasViewMethodPermissions]
    serializer_class = CrawlRunSerializer

    def get_required_permissions(self, request):
        return ["view_crawl_runs"] if request.method == "GET" else ["run_crawler"]

    def get_queryset(self):
        qs = (
            CrawlRun.objects
            .select_related("triggered_by")
            .order_by("-created_at", "-id")
        )

        crawl_type = self.request.query_params.get("crawl_type")
        crawl_status = self.request.query_params.get("status")

        if crawl_type:
            qs = qs.filter(crawl_type=crawl_type)
        if crawl_status:
            qs = qs.filter(status=crawl_status)

        return qs

    def create(self, request, *args, **kwargs):
        serializer = TriggerCrawlRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        crawl_type = data["crawl_type"]
        source = data.get("source", "all")
        company_id = data.get("company")
        spider_args = data.get("spider_args", {})

        company = None
        if company_id:
            company = get_object_or_404(Company, pk=company_id, is_active=True)

        target = company.symbol if company else "All tracked companies"
        sources = _resolve_sources(crawl_type, source)

        # ------------------------------------------------------------------
        # Duplicate-run guard — inside a transaction with SELECT FOR UPDATE
        # so two simultaneous requests cannot both create the same crawl.
        # ------------------------------------------------------------------
        with transaction.atomic():
            existing = _check_active_crawl(crawl_type)
            if existing:
                return Response(
                    {
                        "detail": (
                            f"A {crawl_type} crawl is already active "
                            f"(CrawlRun #{existing.pk}, status={existing.status}). "
                            "Cancel it before starting a new one."
                        ),
                        "active_crawl_run": CrawlRunSerializer(
                            existing, context={"request": request}
                        ).data,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            crawl_run = CrawlRun.objects.create(
                crawl_type=crawl_type,
                target=target,
                company=company,
                status=CrawlRun.Status.PENDING,
                sources=sources,
                triggered_by=request.user,
            )

        # ------------------------------------------------------------------
        # Dispatch ONE Celery task that owns the entire crawl lifecycle.
        #
        # IMPORTANT: we deliberately do NOT use celery.group() for news.
        # Dispatching 6 independent tasks that all write to the same
        # CrawlRun record causes races on status/completed_at/task_id.
        # Instead, run_crawl() iterates all spiders sequentially inside
        # a single task — giving us one authoritative owner.
        # ------------------------------------------------------------------
        try:
            from .tasks import run_crawl

            task = run_crawl.apply_async(
                args=[crawl_run.id],
                kwargs={"spider_args": spider_args},
            )

            crawl_run.task_id = task.id
            crawl_run.status = CrawlRun.Status.RUNNING
            crawl_run.started_at = timezone.now()
            crawl_run.save(
                update_fields=["task_id", "status", "started_at"]
            )

        except Exception as exc:
            logger.exception("Unable to dispatch crawl %s.", crawl_run.id)
            crawl_run.status = CrawlRun.Status.FAILED
            crawl_run.completed_at = timezone.now()
            crawl_run.errors = [str(exc)]
            crawl_run.save(
                update_fields=["status", "completed_at", "errors"]
            )
            return Response(
                {
                    "detail": f"Unable to start crawl: {exc}",
                    "crawl_run": CrawlRunSerializer(
                        crawl_run, context={"request": request}
                    ).data,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": "Crawl started.",
                "crawl_run": CrawlRunSerializer(
                    crawl_run, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

class CrawlRunDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [HasAppPermission]
    permission_key = "view_crawl_runs"
    serializer_class = CrawlRunSerializer
    queryset = CrawlRun.objects.select_related("triggered_by").all()


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

class CrawlRunCancelAPIView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "run_crawler"

    def post(self, request, pk):
        crawl_run = get_object_or_404(CrawlRun, pk=pk)

        if crawl_run.status not in [
            CrawlRun.Status.PENDING,
            CrawlRun.Status.RUNNING,
        ]:
            return Response(
                {"detail": "This crawl cannot be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark cancelled FIRST so the running task sees it on next check.
        crawl_run.status = CrawlRun.Status.CANCELLED
        crawl_run.completed_at = timezone.now()
        crawl_run.save(update_fields=["status", "completed_at"])

        # Revoke the Celery task (best-effort).
        if crawl_run.task_id:
            try:
                AsyncResult(crawl_run.task_id).revoke(terminate=True)
                logger.info(
                    "Revoked Celery task %s for CrawlRun #%s.",
                    crawl_run.task_id,
                    crawl_run.pk,
                )
            except Exception:
                logger.exception(
                    "Unable to revoke Celery task %s.", crawl_run.task_id
                )

        # Kill the Scrapy subprocess (best-effort, platform-aware).
        if crawl_run.process_id:
            _kill_process(crawl_run.process_id)

        crawl_run.process_id = None
        crawl_run.save(update_fields=["process_id"])

        return Response(CrawlRunSerializer(crawl_run, context={"request": request}).data)


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------

class CrawlRunRetryAPIView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "retry_failed_crawl"

    def post(self, request, pk):
        crawl_run = get_object_or_404(CrawlRun, pk=pk)

        if crawl_run.status not in [
            CrawlRun.Status.FAILED,
            CrawlRun.Status.CANCELLED,
        ]:
            return Response(
                {
                    "detail": (
                        "Only failed or cancelled crawls can be retried."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Guard: don't retry if the same type is already running.
        with transaction.atomic():
            existing = _check_active_crawl(crawl_run.crawl_type)
            if existing and existing.pk != crawl_run.pk:
                return Response(
                    {
                        "detail": (
                            f"A {crawl_run.crawl_type} crawl is already active "
                            f"(CrawlRun #{existing.pk}). Cancel it first."
                        ),
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        from .tasks import run_crawl

        task = run_crawl.apply_async(args=[crawl_run.id])

        crawl_run.status = CrawlRun.Status.RUNNING
        crawl_run.started_at = timezone.now()
        crawl_run.completed_at = None
        crawl_run.task_id = task.id
        crawl_run.process_id = None
        crawl_run.errors = []
        crawl_run.save(
            update_fields=[
                "status",
                "started_at",
                "completed_at",
                "task_id",
                "process_id",
                "errors",
            ]
        )

        return Response(
            {
                "message": "Crawl retry started.",
                "crawl_run": CrawlRunSerializer(
                    crawl_run, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Platform-aware process kill helper
# ---------------------------------------------------------------------------

def _kill_process(pid: int) -> None:
    """
    Terminate a process tree.

    Windows:  taskkill /PID <pid> /T /F  (kills the whole tree)
    Linux:    SIGKILL via os.kill        (single PID; Scrapy has no children)
    """
    try:
        logger.info("Killing Scrapy PID %s.", pid)
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
        else:
            os.kill(pid, 9)
    except ProcessLookupError:
        logger.info("PID %s already gone.", pid)
    except Exception:
        logger.exception("Unable to terminate PID %s.", pid)
