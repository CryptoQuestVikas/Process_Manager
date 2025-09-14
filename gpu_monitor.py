from typing import List, Dict, Any

from utils import log

# The 'nvidia-ml-py' package provides the 'pynvml' module.
# This is a try-except block to ensure the application runs
# even if the NVIDIA driver/library is not installed.
try:
    import pynvml
    PYNXML_AVAILABLE = True
except ImportError:
    PYNXML_AVAILABLE = False
    pynvml = None # Assign None to pynvml if it couldn't be imported


class GPUMonitor:
    """
    A wrapper for fetching NVIDIA GPU stats using the pynvml library.
    Gracefully handles cases where nvidia-ml-py is not installed or no
    NVIDIA GPU/drivers are found.
    """

    def __init__(self):
        """
        Initializes the GPUMonitor. It attempts to initialize the pynvml
        library and sets an availability flag.
        """
        self.is_available = False
        self.pid_gpu_memory_map: Dict[int, int] = {}

        if PYNXML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.is_available = True
                log.info("nvidia-ml-py (pynvml) initialized successfully. GPU monitoring enabled.")
            except pynvml.NVMLError as e:
                log.warning(f"Failed to initialize pynvml. GPU monitoring disabled. Error: {e}")
                self.is_available = False
        else:
            log.info("nvidia-ml-py library not found. GPU monitoring is disabled.")

    def _map_pids_to_gpus(self) -> None:
        """
        Creates a fresh map of process PIDs to their GPU memory usage.
        This is called on each monitoring cycle to get the latest data and is
        more efficient than querying for each process individually.
        """
        if not self.is_available:
            return

        # Reset map for each refresh cycle
        self.pid_gpu_memory_map = {}
        try:
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                # nvmlDeviceGetComputeRunningProcesses is generally sufficient
                procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                for p in procs:
                    # A single process can use multiple GPUs, so we aggregate memory
                    self.pid_gpu_memory_map[p.pid] = self.pid_gpu_memory_map.get(p.pid, 0) + p.usedGpuMemory
        except pynvml.NVMLError as e:
            # This can happen if drivers are updated, system sleeps, etc.
            log.error(f"Error fetching GPU process info: {e}")
            self.pid_gpu_memory_map = {}


    def get_gpu_info(self) -> List[Dict[str, Any]]:
        """
        Retrieves detailed information for each available NVIDIA GPU.

        Returns:
            A list of dictionaries, where each dictionary represents a GPU's stats.
            Returns an empty list if GPU monitoring is not available.
        """
        if not self.is_available:
            return []

        gpu_info_list = []
        try:
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                gpu_name = pynvml.nvmlDeviceGetName(handle)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util_rates = pynvml.nvmlDeviceGetUtilizationRates(handle)

                gpu_info_list.append({
                    "name": gpu_name,
                    "uuid": pynvml.nvmlDeviceGetUUID(handle),
                    "total_memory": mem_info.total,
                    "used_memory": mem_info.used,
                    "memory_percent": (mem_info.used / mem_info.total * 100) if mem_info.total > 0 else 0,
                    "gpu_utilization": util_rates.gpu,
                })
        except pynvml.NVMLError as e:
            log.error(f"Could not retrieve GPU info during update. Disabling monitoring. Error: {e}")
            self.is_available = False # Disable if a runtime error occurs
            return []
        
        return gpu_info_list

    def get_process_gpu_memory(self, pid: int) -> int:
        """
        Gets the GPU memory usage for a specific process PID from the pre-fetched map.

        Args:
            pid: The process ID.

        Returns:
            The used GPU memory in bytes, or 0 if the process is not found on the GPU.
        """
        return self.pid_gpu_memory_map.get(pid, 0)

    def shutdown(self):
        """
        Properly shuts down the pynvml library when the application closes.
        """
        if self.is_available:
            try:
                pynvml.nvmlShutdown()
                log.info("pynvml shut down successfully.")
            except pynvml.NVMLError as e:
                log.error(f"Error during pynvml shutdown: {e}")
