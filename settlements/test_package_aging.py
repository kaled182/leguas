from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from settlements.models import CainiaoOperationBatch, CainiaoOperationTask
from settlements.tasks import mark_stale_armazem, roll_forward_active_packages


class PackageAgingTests(TestCase):
    """A idade conta pela última novidade, não pela task_date."""

    def _task(self, waybill, seen_days_ago, date_days_ago=1):
        today = timezone.now().date()
        batch = CainiaoOperationBatch.objects.create(
            filename=f"{waybill}.xlsx", task_date=today,
        )
        CainiaoOperationBatch.objects.filter(pk=batch.pk).update(
            created_at=timezone.now() - timedelta(days=seen_days_ago),
        )
        return CainiaoOperationTask.objects.create(
            waybill_number=waybill,
            task_date=today - timedelta(days=date_days_ago),
            task_status="Driver_received",
            last_import_batch=batch,
        )

    def _status(self, task):
        task.refresh_from_db()
        return task.task_status, task.task_date

    def test_recent_package_moves_to_today(self):
        task = self._task("LF1", seen_days_ago=2)
        roll_forward_active_packages()
        mark_stale_armazem()
        self.assertEqual(self._status(task), ("Driver_received", timezone.now().date()))

    def test_package_without_news_stops_rolling_and_goes_stale(self):
        task = self._task("LF2", seen_days_ago=10)
        date_before = task.task_date
        roll_forward_active_packages()
        self.assertEqual(self._status(task), ("Driver_received", date_before))
        mark_stale_armazem()
        self.assertEqual(self._status(task), ("Stale_Armazem", date_before))

    def test_rolled_package_with_todays_date_still_ages(self):
        """A data de hoje vinha do roll-forward: não é novidade."""
        task = self._task("LF3", seen_days_ago=14, date_days_ago=0)
        mark_stale_armazem()
        self.assertEqual(self._status(task)[0], "Stale_Armazem")

    def test_dry_run_changes_nothing(self):
        task = self._task("LF4", seen_days_ago=10)
        result = mark_stale_armazem(dry_run=True)
        self.assertEqual(result["would_mark"], 1)
        self.assertEqual(self._status(task)[0], "Driver_received")

    def test_delivered_package_is_never_marked(self):
        task = self._task("LF5", seen_days_ago=30)
        CainiaoOperationTask.objects.filter(pk=task.pk).update(task_status="Delivered")
        mark_stale_armazem()
        self.assertEqual(self._status(task)[0], "Delivered")

    def test_old_date_with_recent_news_is_not_marked(self):
        """Pacote com Task Date antiga que continua nos ficheiros."""
        task = self._task("LF6", seen_days_ago=0, date_days_ago=60)
        mark_stale_armazem()
        self.assertEqual(self._status(task)[0], "Driver_received")

