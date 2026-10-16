from django.core.management.base import BaseCommand, CommandError

from apps.market_data.services import broker_directory


class Command(BaseCommand):
    help = "Refresh the broker directory from NEPSE's member list and ShareHub's broker pages (websites, offices)."

    def add_arguments(self, parser):
        parser.add_argument("--skip-sharehub", action="store_true",
                            help="NEPSE fields only; keeps no website or office details for this run.")

    def handle(self, *args, **options):
        try:
            members = broker_directory.fetch_nepse_members()
        except Exception as exc:  # noqa: BLE001 - network / NEPSE auth failures
            raise CommandError(f"NEPSE member list failed: {exc}") from exc
        if not members:
            raise CommandError("NEPSE returned no members; nothing changed.")
        self.stdout.write(f"NEPSE: {len(members)} members")

        profiles = {}
        if not options["skip_sharehub"]:
            profiles = broker_directory.fetch_sharehub_profiles(log=lambda line: self.stderr.write(line))
            self.stdout.write(f"ShareHub: {len(profiles)} broker profiles")

        counts = broker_directory.sync_broker_directory(members, profiles)
        self.stdout.write(self.style.SUCCESS(
            f"Brokers: {counts['created']} created, {counts['updated']} updated, "
            f"{counts['with_website']} with a website, {counts['delisted']} no longer listed by NEPSE."
        ))
