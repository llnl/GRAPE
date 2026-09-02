import os
import tempfile
import unittest
from unittest.mock import patch

from tools.render_timing_chart import render_lines
from vine import grapeMenu
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

    def test_progress_lines_include_elapsed_header(self):
        scheduler = grapeTest.Test()
        lines = scheduler._render_progress_lines(
            [
                {"name": "suite1", "returncode": 0, "start": 0.0, "end": 6.0},
                {"name": "suite2", "returncode": 0, "start": 2.0, "end": 8.5},
            ],
            12,
            final=False,
        )
        self.assertEqual(lines[0], "Elapsed: 8.50 seconds")
        self.assertIn("suite1", lines[1])

    def test_final_progress_lines_include_total_header(self):
        scheduler = grapeTest.Test()
        lines = scheduler._render_progress_lines(
            [
                {"name": "suite1", "returncode": 0, "start": 0.0, "end": 6.0},
            ],
            12,
            final=True,
        )
        self.assertEqual(lines[0], "Total: 6.00 seconds")


class TestSuiteOrdering(unittest.TestCase):

    def test_publish_aggregate_is_not_in_broad_default(self):
        self.assertNotIn("Publish", test_suites.all_suite_names())
        self.assertIn("Publish", test_suites.visible_suite_names())
        self.assertIn("PublishFFDefault", test_suites.all_suite_names())

    def test_split_aggregate_aliases_stay_out_of_broad_default(self):
        self.assertNotIn("Clone", test_suites.all_suite_names())
        self.assertNotIn("MergeDown", test_suites.all_suite_names())
        self.assertNotIn("NestedSubproject", test_suites.all_suite_names())
        self.assertNotIn("Status", test_suites.all_suite_names())
        self.assertNotIn("GrapeUp", test_suites.all_suite_names())
        self.assertIn("CloneNested", test_suites.all_suite_names())
        self.assertIn("MergeDownSubmoduleConflict", test_suites.all_suite_names())
        self.assertIn("NestedSubprojectWorkspaceSync", test_suites.all_suite_names())
        self.assertIn("StatusSubmodule", test_suites.all_suite_names())
        self.assertIn("GrapeUpSubmodule", test_suites.all_suite_names())

    def test_aggregate_aliases_still_resolve_to_explicit_classes(self):
        self.assertEqual(
            test_suites.resolve_selector("Clone.testClone"),
            "test/clone/aggregate.py::TestClone::testClone",
        )
        self.assertEqual(
            test_suites.resolve_selector("Status.testGrapeStatus"),
            "test/workspace_scenarios/status/aggregate.py::TestStatusScenarios::testGrapeStatus",
        )

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

    def test_execute_defaults_full_run_to_shard_count(self):
        scheduler = grapeTest.Test()
        args = {
            "<suite>": [],
            "--base": "origin/master",
            "--changed": False,
            "--debug": False,
            "--durations": "0",
            "--quiet": False,
            "--workers": None,
        }
        with patch.object(scheduler, "_run_parallel", return_value=0) as run_parallel:
            with patch("vine.grapeTest.pytest.main") as pytest_main:
                scheduler.execute(args)
        run_parallel.assert_called_once_with([], args)
        pytest_main.assert_not_called()

    def test_missing_pytest_reports_clear_error_for_grape_test(self):
        scheduler = grapeTest.Test()
        args = {
            "<suite>": [],
            "--base": "origin/master",
            "--changed": False,
            "--debug": False,
            "--durations": "0",
            "--quiet": False,
            "--workers": "1",
        }
        with patch.object(grapeTest, "pytest", None):
            with patch("builtins.print") as mock_print:
                self.assertTrue(scheduler.execute(args))
        mock_print.assert_any_call(
            "*** grape test requires pytest, but pytest is not installed in this Python environment."
        )

    def test_list_suites_and_menu_setup_do_not_require_pytest(self):
        scheduler = grapeTest.Test()
        args = {
            "<suite>": ["listSuites"],
            "--base": "origin/master",
            "--changed": False,
            "--debug": False,
            "--durations": "0",
            "--quiet": False,
            "--workers": None,
        }
        with patch.object(grapeTest, "pytest", None):
            with patch("builtins.print") as mock_print:
                self.assertTrue(scheduler.execute(args))
            grapeMenu._resetMenu()
            menu = grapeMenu.menu(workspace_dir=os.getcwd())
            self.assertTrue(menu.hasOption("publish"))
            self.assertTrue(menu.hasOption("test"))
            grapeMenu._resetMenu()
        mock_print.assert_called_once()

    def test_quiet_disables_live_progress(self):
        scheduler = grapeTest.Test()
        self.assertFalse(
            scheduler._should_render_live_progress(
                {"--quiet": True},
                ["StatusRepo", "CloneSmoke"],
            )
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
                args={"--debug": False, "--durations": "0", "--quiet": False},
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
                args={"--debug": False, "--durations": "0", "--quiet": False},
                env={},
                progress_state=None,
            )
            self.assertEqual(pending, ["serial"])
            self.assertTrue(serial_running)
            self.assertEqual(len(futures), 2)


class _RecordingExecutor:

    def submit(self, fn, *args):
        return object()
