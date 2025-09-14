import time
from typing import Dict, Any, List
import psutil
from PySide6.QtCore import QObject, Signal, QMutex

from gpu_monitor import GPUMonitor
from utils import log

class SystemMonitor(QObject):
    """
    A worker QObject that runs in a separate thread to monitor system resources.
    It periodically collects data and emits a signal with the results.
    """
    # Signal to emit data: dict contains all system information
    data_updated = Signal(dict)

    def __init__(self, refresh_interval: float = 1.5):
        super().__init__()
        self._refresh_interval = refresh_interval
        self._is_running = True
        self._mutex = QMutex()

        self.gpu_monitor = GPUMonitor()
        
        # For CPU percentage calculation
        self._last_cpu_times = psutil.cpu_times(percpu=True)

    def run(self):
        """The main monitoring loop."""
        log.info("System monitor thread started.")
        while self._is_running:
            start_time = time.time()
            
            # Update GPU process map before fetching process list
            self.gpu_monitor._map_pids_to_gpus()

            system_data = self._collect_data()
            if self._is_running:
                self.data_updated.emit(system_data)

            # Ensure the loop runs at the desired refresh interval
            elapsed_time = time.time() - start_time
            sleep_time = self._refresh_interval - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.gpu_monitor.shutdown()
        log.info("System monitor thread stopped.")

    def stop(self):
        """Stops the monitoring loop."""
        self._mutex.lock()
        self._is_running = False
        self._mutex.unlock()

    def _calculate_cpu_percent(self) -> (float, List[float]):
        """
        Calculates total and per-core CPU usage since the last call.
        This non-blocking approach is better than psutil.cpu_percent(interval=...).
        """
        current_times = psutil.cpu_times(percpu=True)
        last_times = self._last_cpu_times
        self._last_cpu_times = current_times

        per_cpu_percent = []
        total_delta_user = 0
        total_delta_system = 0
        total_delta_idle = 0
        total_delta_all = 0

        for i in range(len(current_times)):
            current = current_times[i]
            last = last_times[i]

            delta_user = current.user - last.user
            delta_system = current.system - last.system
            delta_idle = current.idle - last.idle
            delta_all = delta_user + delta_system + delta_idle

            # Avoid division by zero on the first run or if times haven't changed
            if delta_all == 0:
                percent = 0.0
            else:
                percent = (delta_user + delta_system) / delta_all * 100
            
            per_cpu_percent.append(max(0.0, min(100.0, percent)))

            total_delta_user += delta_user
            total_delta_system += delta_system
            total_delta_idle += delta_idle
            total_delta_all += delta_all

        if total_delta_all == 0:
            total_percent = 0.0
        else:
            total_percent = (total_delta_user + total_delta_system) / total_delta_all * 100
        
        return max(0.0, min(100.0, total_percent)), per_cpu_percent

    def _collect_data(self) -> Dict[str, Any]:
        """Gathers all system metrics."""
        # RAM
        ram = psutil.virtual_memory()
        
        # CPU
        total_cpu_percent, per_cpu_percent = self._calculate_cpu_percent()

        # Processes
        processes_data = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info', 'cmdline']):
            try:
                pinfo = proc.info
                # Get full command line, handling potential empty lists
                cmd = ' '.join(pinfo['cmdline']) if pinfo['cmdline'] else ''
                processes_data.append({
                    "pid": pinfo['pid'],
                    "name": pinfo['name'],
                    "cpu_percent": pinfo['cpu_percent'],
                    "memory_bytes": pinfo['memory_info'].rss,
                    "memory_percent": ram.total and (pinfo['memory_info'].rss / ram.total * 100) or 0,
                    "gpu_memory_bytes": self.gpu_monitor.get_process_gpu_memory(pinfo['pid']),
                    "command": cmd,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process might have terminated, or we lack permissions
                pass

        return {
            "ram": {
                "total": ram.total,
                "used": ram.used,
                "percent": ram.percent,
            },
            "cpu": {
                "total_percent": total_cpu_percent,
                "per_cpu_percent": per_cpu_percent,
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
            },
            "gpu": self.gpu_monitor.get_gpu_info(),
            "processes": processes_data,
        }
