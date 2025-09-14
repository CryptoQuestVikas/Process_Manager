# process_manager/tests/test_monitor.py

import unittest
from unittest.mock import patch, MagicMock

# To test the non-GUI parts, we need to adjust the import path
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gpu_monitor import GPUMonitor

class TestGPUMonitor(unittest.TestCase):

    @patch('gpu_monitor.pynvml', new=None)
    @patch('gpu_monitor.PYNXML_AVAILABLE', new=False)
    def test_gpu_monitor_no_pynvml(self):
        """
        Test that GPUMonitor initializes correctly when pynvml is not available.
        """
        monitor = GPUMonitor()
        self.assertFalse(monitor.is_available)
        self.assertEqual(monitor.get_gpu_info(), [])
        monitor.shutdown() # Should not raise error

    @patch('gpu_monitor.pynvml')
    def test_gpu_monitor_init_fails(self, mock_pynvml):
        """
        Test that GPUMonitor handles initialization errors gracefully.
        """
        mock_pynvml.nvmlInit.side_effect = mock_pynvml.NVMLError_DriverNotLoaded()
        monitor = GPUMonitor()
        self.assertFalse(monitor.is_available)
        self.assertEqual(monitor.get_gpu_info(), [])

    @patch('gpu_monitor.pynvml')
    def test_gpu_monitor_init_success(self, mock_pynvml):
        """
        Test successful initialization.
        """
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        monitor = GPUMonitor()
        self.assertTrue(monitor.is_available)
        monitor.shutdown()
        mock_pynvml.nvmlShutdown.assert_called_once()

if __name__ == '__main__':
    unittest.main()