import hashlib
import unittest
from benchmark import payload
from benchmark_support import load


class BenchmarkTests(unittest.TestCase):
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
