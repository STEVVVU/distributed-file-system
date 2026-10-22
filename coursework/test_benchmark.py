import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import verify
from benchmark import Bench,payload
from benchmark_support import load


class BenchmarkTests(unittest.TestCase):
    def test_storage_snapshot_runs_after_writer_shutdown_before_guarded_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            data=root/'.local'/'snapshot-owned'/'data';data.mkdir(parents=True)
            temporary=data/'CURRENT.tmp';temporary.write_bytes(b'temp')
            bench=Bench.__new__(Bench)
            bench.args=SimpleNamespace(run='snapshot-owned')
            bench.data=bench.owned_data=data
            bench.logs=[];bench.result=dict(passed=False,cleanup=False,events=[])
            bench.save=lambda:None
            bench.storage_live_payload_bytes=7
            process=SimpleNamespace(returncode=None)
            process.poll=lambda:process.returncode
            process.terminate=lambda:None
            def stopped(timeout):
                temporary.rename(data/'CURRENT')
                (data/'CURRENT').write_bytes(b'stable')
                process.returncode=0
            process.wait=stopped
            bench.processes={'filer':process}
            def remove(target):
                self.assertEqual(target,data)
                self.assertFalse(bench.processes)
                self.assertEqual(bench.storage['apparent_bytes'],6)
                self.assertEqual(bench.storage['live_payload_bytes'],7)
            with mock.patch.object(verify,'ROOT',root), mock.patch.object(verify.shutil,'rmtree',side_effect=remove) as deletion:
                bench.finish(True)
                deletion.assert_called_once_with(data)
            self.assertTrue(bench.result['passed']);self.assertTrue(bench.result['cleanup'])

    def test_storage_snapshot_refuses_live_writers(self):
        bench=Bench.__new__(Bench)
        bench.owned_data=Path('owned-data');bench.storage_live_payload_bytes=1
        bench.processes={'filer':object()}
        with self.assertRaisesRegex(AssertionError,'every owned writer'):
            bench.before_remove_data(bench.owned_data)

    def test_exact_deterministic_bytes(self):
        for size in [1,4096,1048576]:
            data=payload(size)
            self.assertEqual(len(data),size)
            self.assertEqual(hashlib.sha256(data).digest(),hashlib.sha256(payload(size)).digest())

    def test_timeout_is_not_success(self):
        def fail(_):raise TimeoutError('controlled unavailable file')
        result=load(fail,2,1)
        self.assertEqual(result['finished'],0)
        self.assertEqual(result['timed_out'],2)
