import unittest

from frame.geometry import FocusGap, Rect, window_rect


class GeometryTest(unittest.TestCase):
    def test_accessibility_coordinates(self):
        self.assertEqual(
            window_rect((100, 80), (400, 200), 900), Rect(100, 620, 400, 200)
        )

    def test_secondary_display(self):
        self.assertEqual(
            window_rect((-1200, 100), (800, 600), 900), Rect(-1200, 200, 800, 600)
        )

    def test_rounds_outward(self):
        self.assertEqual(
            window_rect((10.2, 20.3), (30.1, 40.2), 900), Rect(10, 839, 31, 41)
        )

    def test_rejects_invalid_frames(self):
        for position, size, height in (
            ((0, 0), (0, 10), 900),
            ((0, 0), (10, -1), 900),
            ((float("nan"), 0), (10, 10), 900),
            ((0, 0), (10, 10), 0),
            ((0, 0), (float("inf"), 10), 900),
            ((1e308, 0), (1e308, 10), 900),
            ((0, -1e308), (10, 10), 1e308),
        ):
            with self.subTest(position=position, size=size):
                self.assertIsNone(window_rect(position, size, height))

    def test_intersection_and_expansion(self):
        rect = Rect(100, 100, 500, 300)
        self.assertTrue(rect.intersects(Rect(0, 0, 200, 200)))
        self.assertFalse(rect.intersects(Rect(700, 100, 10, 10)))
        self.assertEqual(rect.expanded(1), Rect(99, 99, 502, 302))

    def test_degenerate_rectangles_do_not_intersect(self):
        rect = Rect(0, 0, 100, 100)
        for invalid in (Rect(50, 50, 0, 10), Rect(50, 50, 10, 0), Rect(50, 50, -1, 10)):
            with self.subTest(rect=invalid):
                self.assertFalse(rect.intersects(invalid))
                self.assertFalse(invalid.intersects(rect))
        self.assertFalse(rect.intersects(Rect(100, 0, 10, 10)))


class FocusGapTest(unittest.TestCase):
    def test_empty_or_expired_gap_hides(self):
        gap = FocusGap()
        self.assertTrue(gap.expired(1))
        gap.seen(1)
        self.assertFalse(gap.expired(1.249))
        self.assertTrue(gap.expired(1.25))

    def test_reset_hides_immediately(self):
        gap = FocusGap()
        gap.seen(1)
        gap.reset()
        self.assertTrue(gap.expired(1.01))

    def test_rejects_invalid_delay(self):
        for seconds in (-0.1, float("nan"), float("inf"), float("-inf")):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                FocusGap(seconds)

    def test_zero_delay_expires_immediately(self):
        gap = FocusGap(0)
        gap.seen(1)
        self.assertTrue(gap.expired(1))


if __name__ == "__main__":
    unittest.main()
