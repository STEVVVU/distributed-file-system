"""Deterministic ownership, verdict and deletion-boundary regression checks."""
import copy
import io
import types
import unittest
from unittest.mock import patch

import verify


class Process:
    def __init__(self, fail=None):
        self.fail = fail
        self.returncode = None
        self.waited = False

    def poll(self):
        return self.returncode

    def terminate(self):
        if self.fail == "terminate":
            raise OSError("injected termination failure")

    def wait(self, timeout):
        if self.fail == "wait":
            raise OSError("injected wait failure")
        self.waited = True
        self.returncode = 0


class CleanupTests(unittest.TestCase):
    def workbench(self, processes=None):
        workbench = object.__new__(verify.Workbench)
        workbench.args = types.SimpleNamespace(run="unit-owned")
        workbench.data = verify.ROOT.resolve() / ".local/unit-owned/data"
        workbench.owned_data = workbench.data
        workbench.processes = processes or {}
        workbench.logs = [io.BytesIO()]
        workbench.result = {"passed": False, "cleanup": False, "events": [], "error": "earlier drive error"}
        workbench.saved = []
        workbench.save = lambda: workbench.saved.append(copy.deepcopy(workbench.result))
        return workbench

    def test_stop_retains_handle_until_successful_wait(self):
        for failure in ("terminate", "wait"):
            with self.subTest(failure=failure):
                process = Process(failure)
                workbench = self.workbench({"volume": process})
                with self.assertRaises(OSError):
                    workbench.stop("volume")
                self.assertIs(workbench.processes["volume"], process)

    def test_cleanup_continues_after_one_process_fails(self):
        failed, healthy = Process("terminate"), Process()
        workbench = self.workbench({"first": failed, "second": healthy})
        with patch.object(verify.shutil, "rmtree") as remove:
            workbench.finish(True)
        self.assertTrue(healthy.waited)
        self.assertEqual(workbench.processes, {"first": failed})
        self.assertTrue(workbench.logs[0].closed)
        remove.assert_not_called()
        self.assertFalse(workbench.saved[-1]["passed"])
        self.assertFalse(workbench.saved[-1]["cleanup"])
        self.assertIn("injected termination failure", " ".join(workbench.result["cleanup_errors"]))
        self.assertEqual(workbench.result["error"], "earlier drive error")

    def test_data_cleanup_failure_cannot_persist_success(self):
        workbench = self.workbench({"volume": Process()})
        with patch.object(verify.shutil, "rmtree", side_effect=OSError("injected data cleanup failure")):
            workbench.finish(True)
        self.assertFalse(workbench.processes)
        self.assertTrue(workbench.logs[0].closed)
        self.assertTrue(all(not result["passed"] for result in workbench.saved))
        self.assertFalse(workbench.saved[-1]["cleanup"])
        self.assertIn("injected data cleanup failure", " ".join(workbench.result["cleanup_errors"]))

    def test_evidence_capture_failure_retains_data_and_failing_verdict(self):
        workbench = self.workbench({"volume": Process()})
        workbench.before_remove_data = unittest.mock.Mock(side_effect=OSError("snapshot failed"))
        with patch.object(verify.shutil, "rmtree") as remove:
            workbench.finish(True)
        remove.assert_not_called()
        self.assertFalse(workbench.result["passed"])
        self.assertFalse(workbench.result["cleanup"])
        self.assertIn("snapshot failed", " ".join(workbench.result["cleanup_errors"]))

    def test_log_failure_does_not_skip_other_logs_or_data(self):
        workbench = self.workbench()
        class BrokenLog:
            def close(self):
                raise OSError("injected log failure")
        workbench.logs.insert(0, BrokenLog())
        with patch.object(verify.shutil, "rmtree") as remove:
            workbench.finish(True)
        self.assertTrue(workbench.logs[1].closed)
        remove.assert_called_once_with(workbench.owned_data)
        self.assertFalse(workbench.result["passed"])

    def test_success_is_saved_only_after_cleanup(self):
        workbench = self.workbench({"volume": Process()})
        with patch.object(verify.shutil, "rmtree") as remove:
            workbench.finish(True)
        remove.assert_called_once_with(workbench.owned_data)
        self.assertFalse(workbench.saved[0]["passed"])
        self.assertTrue(workbench.saved[-1]["passed"])
        self.assertTrue(workbench.saved[-1]["cleanup"])

    def test_recursive_delete_rejects_outside_and_changed_root(self):
        workbench = self.workbench()
        workbench.before_remove_data = before_remove = unittest.mock.Mock()
        outside = verify.ROOT.resolve() / "outside-owned-data"
        with patch.object(verify.shutil, "rmtree") as remove:
            with self.assertRaises(ValueError):
                workbench.remove_data(outside)
            workbench.data = outside
            with self.assertRaises(ValueError):
                workbench.remove_data(outside)
        remove.assert_not_called()
        before_remove.assert_not_called()

    def test_resolved_replica_link_cannot_escape_owned_data(self):
        workbench = self.workbench()
        target = types.SimpleNamespace(resolve=lambda: verify.ROOT.resolve() / "outside-owned-data")
        with patch.object(verify.shutil, "rmtree") as remove:
            with self.assertRaises(ValueError):
                workbench.remove_data(target)
        remove.assert_not_called()

    def test_owned_replica_child_can_be_removed(self):
        workbench = self.workbench()
        target = workbench.data / "volume-0"
        with patch.object(verify.shutil, "rmtree") as remove:
            workbench.remove_data(target)
        remove.assert_called_once_with(target)


if __name__ == "__main__":
    unittest.main()
