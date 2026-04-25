from django.core.management.base import BaseCommand
from django.db import transaction

from ledger.models import Credit, Merchant


class Command(BaseCommand):
    help = "Seed 2–3 merchants with credit history for the Playto challenge demo."

    @transaction.atomic
    def handle(self, *args, **options):
        Merchant.objects.all().delete()

        m1 = Merchant.objects.create(name="Alpha Studio", api_token="demo-token-alpha")
        m2 = Merchant.objects.create(name="Beta Freelance", api_token="demo-token-beta")
        m3 = Merchant.objects.create(name="Gamma Agency", api_token="demo-token-gamma")

        # amounts are paise (INR * 100)
        for m, amounts in (
            (m1, (500_000, 500_000, 200_000)),  # ₹10,000 + ₹2,000 credits
            (m2, (2_500_000, 800_000)),
            (m3, (100_000, 200_000, 50_000, 75_000)),
        ):
            for i, paise in enumerate(amounts):
                Credit.objects.create(
                    merchant=m,
                    amount_paise=paise,
                    description=f"Simulated customer payment #{i + 1}",
                )

        self.stdout.write(self.style.SUCCESS("Seeded merchants and credits."))
        self.stdout.write("API tokens (Bearer):")
        self.stdout.write(f"  {m1.name}: {m1.api_token}")
        self.stdout.write(f"  {m2.name}: {m2.api_token}")
        self.stdout.write(f"  {m3.name}: {m3.api_token}")
