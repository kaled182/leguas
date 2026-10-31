from datetime import date

from django.test import SimpleTestCase

from settlements.cainiao_views import (
    _apply_status_aliases, _is_new_task, _keeps_failure_row, _pick_current_row,
)


class DriverPickUpStatusTests(SimpleTestCase):
    """Aveiro exporta "Driver pick up": 784 envios ficavam fora da base."""

    def test_driver_pick_up_becomes_in_distribution(self):
        rows = [("Waybill", "Task Status"), ("LF1", "Driver pick up"), ("LF2", "Delivered")]
        _apply_status_aliases(rows, 0, 1)
        self.assertEqual(rows[1][1], "Driver_received")
        self.assertEqual(rows[2], ("LF2", "Delivered"))

    def test_aveiro_incidence_uses_viana_name(self):
        """"Recebido anormal" não conta como em distribuição."""
        rows = [("Waybill", "Task Status"), ("LF1", "Driver received incidence"), ("LF2", "Driver_received_incidence")]
        _apply_status_aliases(rows, 0, 1)
        self.assertEqual(rows[1][1], "Driver_received_incidence")
        self.assertEqual(rows[2][1], "Driver_received_incidence")

    def test_header_stays_untouched(self):
        rows = [("Waybill", "Driver pick up"), ("LF1", "Assigned")]
        _apply_status_aliases(rows, 0, 1)
        self.assertEqual(rows[0][1], "Driver pick up")

    def test_missing_status_column_is_ignored(self):
        rows = [("Waybill",), ("LF1",)]
        _apply_status_aliases(rows, 0, None)
        self.assertEqual(rows[1], ("LF1",))


class LatestTaskRuleTests(SimpleTestCase):
    """O estado do pacote é o da tarefa mais recente."""

    D1, D2 = date(2026, 10, 30), date(2026, 10, 31)

    def test_retry_after_failure_opens_new_day(self):
        self.assertTrue(_is_new_task("Attempt Failure", self.D1, "Driver_received", self.D2))
        self.assertTrue(_keeps_failure_row("Attempt Failure", self.D1, self.D2))

    def test_delivered_later_keeps_failure_day(self):
        self.assertTrue(_keeps_failure_row("Attempt Failure", self.D1, self.D2))
        self.assertFalse(_keeps_failure_row("Driver_received", self.D1, self.D2))
        self.assertFalse(_keeps_failure_row("Attempt Failure", self.D2, self.D1))

    def test_same_day_pick_does_not_erase_failure(self):
        self.assertFalse(_is_new_task("Attempt Failure", self.D1, "Driver_received", self.D1))

    def test_cancel_takes_open_package_out_of_route(self):
        self.assertTrue(_is_new_task("Driver_received", self.D2, "Cancel", self.D2))
        self.assertTrue(_is_new_task("Assigned", self.D1, "Cancel", self.D2))

    def test_older_cancel_does_not_touch_newer_task(self):
        self.assertFalse(_is_new_task("Driver_received", self.D2, "Cancel", self.D1))

    def test_delivered_never_goes_back(self):
        for status in ("Cancel", "Attempt Failure", "Driver_received"):
            self.assertFalse(_is_new_task("Delivered", self.D1, status, self.D2))

    def test_current_row_ignores_old_failure(self):
        fail = {"task_status": "Attempt Failure", "task_date": self.D1}
        open_row = {"task_status": "Driver_received", "task_date": self.D2}
        priority = {"Attempt Failure": 3, "Driver_received": 2}
        self.assertIs(_pick_current_row(fail, open_row, priority), open_row)
        self.assertIs(_pick_current_row(open_row, fail, priority), open_row)

    def test_delivered_stays_current_row(self):
        done = {"task_status": "Delivered", "task_date": self.D1}
        fail = {"task_status": "Attempt Failure", "task_date": self.D2}
        self.assertIs(_pick_current_row(fail, done, {"Delivered": 4, "Attempt Failure": 3}), done)
