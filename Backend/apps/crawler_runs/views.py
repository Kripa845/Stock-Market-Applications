import logging
import os
import subprocess
from celery.result import AsyncResult
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
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


class CrawlRunListCreateAPIView(
    generics.ListCreateAPIView
):
    permission_classes = [HasViewMethodPermissions]
    serializer_class = CrawlRunSerializer

    def get_required_permissions(self, request):
        return ["view_crawl_runs"] if request.method == "GET" else ["run_crawler"]

    def get_queryset(self):
        qs = (
            CrawlRun.objects
            .select_related(
                # "company",
                "triggered_by",
            )
            .order_by(
                "-created_at",
                "-id",
            )
        )

        crawl_type = self.request.query_params.get(
            "crawl_type"
        )

        crawl_status = self.request.query_params.get(
            "status"
        )

        if crawl_type:
            qs = qs.filter(
                crawl_type=crawl_type
            )

        if crawl_status:
            qs = qs.filter(
                status=crawl_status
            )

        return qs

    def create(
        self,
        request,
        *args,
        **kwargs,
    ):
        serializer = (
            TriggerCrawlRequestSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        data = serializer.validated_data

        crawl_type = data["crawl_type"]
        source = data.get("source", "all")
        company_id = data.get("company")
        spider_args = data.get(
            "spider_args",
            {},
        )

        company = None

        if company_id:
            company = get_object_or_404(
                Company,
                pk=company_id,
                is_active=True,
            )

        if company:
            target = company.symbol
        else:
            target = "All tracked companies"

        sources = self._resolve_sources(
            crawl_type,
            source,
        )

        crawl_run = CrawlRun.objects.create(
            crawl_type=crawl_type,
            target=target,
            company=company,
            status=CrawlRun.Status.PENDING,
            sources=sources,
            triggered_by=request.user,
        )

        try:
            from .tasks import (
                run_crawl,
            )

            if crawl_type == "all":
                task = run_crawl.delay(
                    crawl_run.id
                )

            else:
                spider = sources[0]

                if (
                    crawl_type == "news"
                    and source == "all"
                ):
                    # Multiple news spiders require a dedicated
                    # task instead of pretending there is one.
                    from celery import group

                    tasks = []

                    for spider_name in sources:
                        tasks.append(
                            run_crawl.s(
                                crawl_run.id,
                                spider_name,
                                spider_args,
                            )
                        )

                    task = group(tasks).apply_async()

                else:
                    task = run_crawl.delay(
                        crawl_run.id,
                        spider,
                        spider_args,
                    )

            crawl_run.task_id = task.id
            crawl_run.status = CrawlRun.Status.RUNNING
            crawl_run.started_at = timezone.now()

            crawl_run.save(
                update_fields=[
                    "task_id",
                    "status",
                    "started_at",
                ]
            )

        except Exception as exc:
            logger.exception(
                "Unable to dispatch crawl."
            )

            crawl_run.status = CrawlRun.Status.FAILED
            crawl_run.completed_at = timezone.now()
            crawl_run.errors = [
                str(exc)
            ]

            crawl_run.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "errors",
                ]
            )

            return Response(
                {
                    "detail": (
                        f"Unable to start crawl: {exc}"
                    ),
                    "crawl_run":
                        CrawlRunSerializer(
                            crawl_run
                        ).data,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": "Crawl started.",
                "crawl_run":
                    CrawlRunSerializer(
                        crawl_run
                    ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def _resolve_sources(
        self,
        crawl_type,
        source,
    ):
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
                source.lower().replace(
                    " ",
                    "",
                ),
            )

            return [spider]

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


class CrawlRunDetailAPIView(
    generics.RetrieveAPIView
):
    permission_classes = [HasAppPermission]
    permission_key = "view_crawl_runs"
    serializer_class = CrawlRunSerializer

    queryset = (
        CrawlRun.objects
        .select_related(
            # "company",
            "triggered_by",
        )
        .all()
    )

class CrawlRunCancelAPIView(APIView):

    permission_classes = [HasAppPermission]
    permission_key = "run_crawler"

    def post(self, request, pk):

        crawl_run = get_object_or_404(
            CrawlRun,
            pk=pk,
        )

        # ----------------------------------------------
        # Validate state
        # ----------------------------------------------

        if crawl_run.status not in [
            CrawlRun.Status.PENDING,
            CrawlRun.Status.RUNNING,
        ]:

            return Response(
                {
                    "detail":
                        "This crawl cannot be cancelled."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------
        # Mark cancelled FIRST
        # ----------------------------------------------

        crawl_run.status = (
            CrawlRun.Status.CANCELLED
        )

        crawl_run.completed_at = timezone.now()

        crawl_run.save(
            update_fields=[
                "status",
                "completed_at",
            ]
        )

        # ----------------------------------------------
        # Kill Scrapy process
        # ----------------------------------------------

        if crawl_run.process_id:

            try:

                logger.info(
                    "Stopping Scrapy PID %s",
                    crawl_run.process_id,
                )

                if os.name == "nt":

                    subprocess.run(
                        [
                            "taskkill",
                            "/PID",
                            str(crawl_run.process_id),
                            "/T",
                            "/F",
                        ],
                        capture_output=True,
                        text=True,
                    )

                else:

                    os.kill(
                        crawl_run.process_id,
                        9,
                    )

            except Exception:

                logger.exception(
                    "Unable to terminate Scrapy process."
                )

        # ----------------------------------------------
        # Revoke Celery task
        # ----------------------------------------------

        if crawl_run.task_id:

            try:

                AsyncResult(
                    crawl_run.task_id
                ).revoke(
                    terminate=True
                )

            except Exception:

                logger.exception(
                    "Unable to revoke Celery task."
                )

        # ----------------------------------------------
        # Clear process
        # ----------------------------------------------

        crawl_run.process_id = None

        crawl_run.save(
            update_fields=[
                "process_id",
            ]
        )

        return Response(
            CrawlRunSerializer(
                crawl_run
            ).data
        )
class CrawlRunRetryAPIView(APIView):
    permission_classes = [HasAppPermission]
    permission_key = "retry_failed_crawl"

    def post(self, request, pk):
        crawl_run = get_object_or_404(
            CrawlRun,
            pk=pk,
        )

        if crawl_run.status not in [
            CrawlRun.Status.FAILED,
            CrawlRun.Status.CANCELLED,
        ]:
            return Response(
                {
                    "detail": (
                        "Only failed or cancelled crawls "
                        "can be retried."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .tasks import run_crawl

        task = run_crawl.delay(
            crawl_run.id
        )

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
                    crawl_run
                ).data,
            },
            status=status.HTTP_200_OK,
        )

def dispatch_crawl(crawl_run, crawl_type, sources, spider_args):
    from .tasks import (
        run_crawl,
        run_full_crawl_pipeline,
    )

    if crawl_type == "all":
        return run_full_crawl_pipeline.delay(
            crawl_run.id
        )

    if (
        crawl_type == "news"
        and len(sources) > 1
    ):
        from celery import group

        tasks = [
            run_crawl.s(
                crawl_run.id,
                spider_name,
                spider_args,
            )
            for spider_name in sources
        ]

        return group(tasks).apply_async()

    return run_crawl.delay(
        crawl_run.id,
        sources[0],
        spider_args,
    )
