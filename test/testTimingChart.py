import os
import tempfile
import unittest
from unittest.mock import patch

from tools.render_timing_chart import render_lines
from vine import grapeTest
from vine import test_suites


class TestTimingChart(unittest.TestCase):

    def test_duration_column_alignment(self):
        lines = render_lines(
            [
                {"name": "Branches", "returncode": 0, "start": 0.0, "end": 1.81},
                {"name": "Publish", "returncode": 0, "start": 0.0, "end": 19.45},
            ],
            20,
            ".",
        )
        self.assertEqual(lines[0].index("["), lines[1].index("["))

    def test_explicit_span_keeps_live_chart_stable(self):
        lines = render_lines(
            [
                {"name": "suite1", "returncode": 0, "start": 0.0, "end": 6.0},
                {"name": "suite2", "status": "( )", "start": 0.0, "end": 0.0, "duration_text": "0.00 seconds"},
            ],
            12,
            ".",
            global_start=0.0,
            global_end=30.0,
        )
        self.assertIn("[...         ]", lines[0])
        self.assertIn("[            ]", lines[1])


class TestSuiteOrdering(unittest.TestCase):

    def test_publish_aggregate_is_not_in_broad_default(self):
        self.assertNotIn("Publish", test_suites.all_suite_names())
        self.assertIn("Publish", test_suites.visible_suite_names())
        self.assertIn("PublishFFDefault", test_suites.all_suite_names())

    def test_named_suites_launch_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            order_path = os.path.join(tmpdir, "suite_order.txt")
            with open(order_path, "w", encoding="utf-8") as handle:
                handle.write("# launch these first\nClone\nStatus\n")

            ordered = test_suites.order_selectors(
                ["Branches", "Status", "Review", "Clone", "GrapeUp"],
                order_path=order_path,
            )

        self.assertEqual(
            ordered,
            ["Clone", "Status", "Branches", "Review", "GrapeUp"],
        )

    def test_invalid_alias_in_order_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            order_path = os.path.join(tmpdir, "suite_order.txt")
            with open(order_path, "w", encoding="utf-8") as handle:
                handle.write("NotASuite\n")

            with self.assertRaisesRegex(ValueError, "NotASuite"):
                test_suites.order_selectors(["Branches", "Clone"], order_path=order_path)


class TestSchedulerRules(unittest.TestCase):

    def test_default_workers_match_selected_suite_count(self):
        scheduler = grapeTest.Test()
        self.assertEqual(
            scheduler._parse_workers(None, selectors=["A", "B", "C"], debug=False),
            3,
        )

    def test_single_suite_default_stays_serial(self):
        scheduler = grapeTest.Test()
        self.assertEqual(
            scheduler._parse_workers(None, selectors=["A"], debug=False),
            1,
        )

    def test_serial_suite_can_launch_with_normal_suites(self):
        scheduler = grapeTest.Test()
        futures = {}
        with patch("vine.test_suites.is_serial_selector", side_effect=lambda selector: selector == "serial"):
            pending, serial_running = scheduler._launch_ready_work(
                executor=_RecordingExecutor(),
                pending=["serial", "Status", "MergeDown"],
                futures=futures,
                workers=3,
                serial_running=False,
                args={"--debug": False, "--durations": "0"},
                env={},
                progress_state=None,
            )
        self.assertEqual(pending, [])
        self.assertTrue(serial_running)
        self.assertEqual(len(futures), 3)

    def test_second_serial_suite_stays_pending(self):
        scheduler = grapeTest.Test()
        futures = {}
        with patch("vine.test_suites.is_serial_selector", side_effect=lambda selector: selector == "serial"):
            pending, serial_running = scheduler._launch_ready_work(
                executor=_RecordingExecutor(),
                pending=["serial", "Clone", "serial"],
                futures=futures,
                workers=3,
                serial_running=False,
                args={"--debug": False, "--durations": "0"},
                env={},
                progress_state=None,
            )
            self.assertEqual(pending, ["serial"])
            self.assertTrue(serial_running)
            self.assertEqual(len(futures), 2)


class _RecordingExecutor:

    def submit(self, fn, *args):
        return object()
