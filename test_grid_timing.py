"""Regression: real ROS epoch timestamps must not reveal future grid buckets."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np


class GridTimingTest(unittest.TestCase):
    def test_bucket_waits_for_last_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copyfile(Path(__file__).with_name('grid_prog.py'), root/'grid_prog.py')
            (root/'rgbd_test').mkdir()
            (root/'demo_test').mkdir()
            t0 = 1_789_808_000.
            ts = t0 + np.array([0., .1, .5, .7, 1.])
            np.save(root/'rgbd_test/depth.npy', np.full((5, 40, 40), 1000, np.uint16))
            np.save(root/'rgbd_test/color.npy', np.full((5, 40, 40, 3), 128, np.uint8))
            np.save(root/'rgbd_test/K.npy', np.array([40., 40., 20., 20.]))
            np.save(root/'rgbd_test/times.npy', ts)
            np.save(root/'rgbd_test/mount2.npy', np.array([.3, 0., 0.]))
            tel = np.zeros((5, 7)); tel[:, 0] = ts
            np.savez(root/'test.npz', tel=tel)
            (root/'demo_test/win.json').write_text(json.dumps(dict(t0=t0, t1=t0+1)))
            subprocess.run([sys.executable, str(root/'grid_prog.py'), '--runs', 'test',
                            '--out', str(root/'grid.npz')], check=True, capture_output=True)
            with np.load(root/'grid.npz') as grid:
                np.testing.assert_allclose(grid['test_t']-t0, [.1, .7, 1.], atol=1e-6)
                self.assertEqual(str(grid['time_basis']), 'absolute_ros_seconds')
                self.assertEqual(str(grid['bucket_timestamp']), 'last_observation')
                # Before the first bucket completes nothing can be shown, despite
                # the clock being a large epoch value (the original regression).
                self.assertEqual(int((grid['test_t'] <= t0+.05).sum()), 0)
                self.assertEqual(int((grid['test_t'] <= t0+.6).sum()), 1)
                self.assertEqual(int((grid['test_t'] <= t0+1).sum()), 3)


if __name__ == '__main__':
    unittest.main()
