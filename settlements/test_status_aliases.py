from django.test import SimpleTestCase

from settlements.cainiao_views import _apply_status_aliases


class DriverPickUpStatusTests(SimpleTestCase):
    """Aveiro exporta "Driver pick up": 784 envios ficavam fora da base."""

    def test_driver_pick_up_becomes_in_distribution(self):
        rows = [("Waybill", "Task Status"), ("LF1", "Driver pick up"), ("LF2", "Delivered")]
        _apply_status_aliases(rows, 0, 1)
        self.assertEqual(rows[1][1], "Driver_received")
        self.assertEqual(rows[2], ("LF2", "Delivered"))

    def test_incidence_stays_in_distribution(self):
        rows = [("Waybill", "Task Status"), ("LF1", "Driver_received_incidence")]
        _apply_status_aliases(rows, 0, 1)
        self.assertEqual(rows[1][1], "Driver_received")

    def test_header_stays_untouched(self):
        rows = [("Waybill", "Driver pick up"), ("LF1", "Assigned")]
        _apply_status_aliases(rows, 0, 1)
        self.assertEqual(rows[0][1], "Driver pick up")

    def test_missing_status_column_is_ignored(self):
        rows = [("Waybill",), ("LF1",)]
        _apply_status_aliases(rows, 0, None)
        self.assertEqual(rows[1], ("LF1",))
