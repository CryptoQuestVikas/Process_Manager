import sys
import time
import csv
from collections import deque
from typing import Dict, Any, List

import psutil
from PySide6.QtCore import Qt, QThread, Slot, QTimer, QSize
from PySide6.QtGui import QColor, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QTabWidget, QGridLayout, QFrame, QMessageBox, QMenu, QPushButton, QFileDialog
)
import pyqtgraph as pg

from monitor import SystemMonitor
from utils import log

# --- Configuration ---
REFRESH_INTERVAL_MS = 1500
CHART_HISTORY_LENGTH = 60
HIGH_USAGE_THRESHOLD = 80.0

# --- Styling ---
STYLE_SHEET = """
    QWidget {
        font-size: 11pt;
    }
    QTabWidget::pane {
        border-top: 2px solid #C2C7CB;
    }
    QHeaderView::section {
        background-color: #f0f0f0;
        padding: 4px;
        border: 1px solid #dcdcdc;
        font-weight: bold;
    }
    QProgressBar {
        border: 1px solid grey;
        border-radius: 5px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #05B8CC;
        width: 10px;
    }
"""
HIGH_USAGE_STYLE = "QProgressBar::chunk { background-color: #F73859; }"
NORMAL_USAGE_STYLE = "QProgressBar::chunk { background-color: #05B8CC; }"


class ProcessManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Real-Time Process Manager")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(QSize(800, 600))
        self.setStyleSheet(STYLE_SHEET)

        self.cpu_history = deque([0] * CHART_HISTORY_LENGTH, maxlen=CHART_HISTORY_LENGTH)
        self.ram_history = deque([0] * CHART_HISTORY_LENGTH, maxlen=CHART_HISTORY_LENGTH)
        self.gpu_history = {}

        self._setup_ui()
        self._setup_monitor_thread()

        self.process_widgets = {}
        self.table_needs_full_rebuild = True
        
        log.info("Application UI initialized.")
        self.show()

    def _setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        self._create_overview_tab()
        self._create_per_core_tab()
        self._create_gpu_tab()
        self._create_processes_tab()
        
        self.statusBar().showMessage("Initializing...")
        
    def _create_overview_tab(self):
        # This method remains unchanged
        tab = QWidget()
        layout = QGridLayout(tab)
        layout.setSpacing(20)
        cpu_frame = QFrame()
        cpu_frame.setFrameShape(QFrame.StyledPanel)
        cpu_layout = QVBoxLayout(cpu_frame)
        self.cpu_total_label = QLabel("CPU Total Usage: 0.0%")
        self.cpu_total_progress = QProgressBar()
        self.cpu_cores_label = QLabel(f"Cores: {psutil.cpu_count(logical=False)} Physical, {psutil.cpu_count(logical=True)} Logical")
        self.cpu_chart = self._create_plot_widget("CPU Usage History (%)")
        cpu_layout.addWidget(self.cpu_total_label)
        cpu_layout.addWidget(self.cpu_total_progress)
        cpu_layout.addWidget(self.cpu_cores_label)
        cpu_layout.addWidget(self.cpu_chart, stretch=1)
        layout.addWidget(cpu_frame, 0, 0)
        ram_frame = QFrame()
        ram_frame.setFrameShape(QFrame.StyledPanel)
        ram_layout = QVBoxLayout(ram_frame)
        self.ram_usage_label = QLabel("RAM Usage: 0.00 / 0.00 GB (0.0%)")
        self.ram_usage_progress = QProgressBar()
        self.ram_chart = self._create_plot_widget("RAM Usage History (%)")
        ram_layout.addWidget(self.ram_usage_label)
        ram_layout.addWidget(self.ram_usage_progress)
        ram_layout.addWidget(self.ram_chart, stretch=1)
        layout.addWidget(ram_frame, 0, 1)
        self.tabs.addTab(tab, "Overview")

    def _create_plot_widget(self, title: str) -> pg.PlotWidget:
        # This method remains unchanged
        plot = pg.PlotWidget()
        plot.setTitle(title)
        plot.setLabel('left', 'Usage', units='%')
        plot.setLabel('bottom', 'Time (updates)')
        plot.showGrid(x=True, y=True)
        plot.setYRange(0, 100)
        return plot

    def _create_per_core_tab(self):
        # This method remains unchanged
        tab = QWidget()
        self.per_core_layout = QGridLayout(tab)
        self.per_core_layout.setSpacing(10)
        self.per_core_widgets = []
        num_cores = psutil.cpu_count(logical=True)
        cols = 4
        for i in range(num_cores):
            label = QLabel(f"Core {i}: 0.0%")
            progress = QProgressBar()
            self.per_core_layout.addWidget(label, i // cols, 2 * (i % cols))
            self.per_core_layout.addWidget(progress, i // cols, 2 * (i % cols) + 1)
            self.per_core_widgets.append((label, progress))
        self.tabs.addTab(tab, "Per-Core CPU")

    def _create_gpu_tab(self):
        # This method remains unchanged
        self.gpu_tab = QWidget()
        self.gpu_layout = QVBoxLayout(self.gpu_tab)
        self.gpu_widgets = {}
        self.tabs.addTab(self.gpu_tab, "GPU")

    def _create_processes_tab(self):
        # *** THIS METHOD IS UPDATED ***
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Top bar with filter and export button
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addWidget(QLabel("Filter:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by name or PID...")
        self.search_input.textChanged.connect(self._filter_processes)
        top_bar_layout.addWidget(self.search_input)
        
        # Add Export Button
        self.export_button = QPushButton("Export to CSV")
        self.export_button.clicked.connect(self._export_processes_to_csv)
        top_bar_layout.addWidget(self.export_button)

        layout.addLayout(top_bar_layout)

        # Process Table (unchanged)
        self.process_table = QTableWidget()
        self.process_table.setColumnCount(7)
        self.process_table.setHorizontalHeaderLabels(["PID", "Name", "CPU %", "RAM %", "GPU Mem (MB)", "Memory (MB)", "Command"])
        self.process_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.process_table.setSelectionMode(QTableWidget.SingleSelection)
        self.process_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.process_table.setSortingEnabled(True)
        self.process_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.process_table.horizontalHeader().setStretchLastSection(True)
        self.process_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.process_table.customContextMenuRequested.connect(self._show_process_context_menu)
        
        layout.addWidget(self.process_table)
        self.tabs.addTab(tab, "Processes")
        
    def _export_processes_to_csv(self):
        """
        Opens a file dialog to save the current process list to a CSV file.
        """
        # Suggest a filename with a timestamp
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        suggested_filename = f"process_snapshot_{timestamp}.csv"
        
        # Open "Save File" dialog
        filePath, _ = QFileDialog.getSaveFileName(self, "Export to CSV", suggested_filename, "CSV Files (*.csv)")

        if not filePath:
            # User cancelled the dialog
            return

        try:
            with open(filePath, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                
                # Write header
                header = [self.process_table.horizontalHeaderItem(i).text() for i in range(self.process_table.columnCount())]
                writer.writerow(header)
                
                # Write data rows (only visible ones)
                for row in range(self.process_table.rowCount()):
                    if not self.process_table.isRowHidden(row):
                        row_data = [self.process_table.item(row, col).text() for col in range(self.process_table.columnCount())]
                        writer.writerow(row_data)

            self.statusBar().showMessage(f"Successfully exported process list to {filePath}", 5000) # Message disappears after 5s
            log.info(f"Process list exported to {filePath}")
        except Exception as e:
            log.error(f"Failed to export to CSV: {e}")
            QMessageBox.critical(self, "Export Error", f"Could not write to file:\n{e}")

    # All other methods (_setup_monitor_thread, update_ui, etc.) remain the same
    # as the previously corrected version. I'm including them here for completeness.
    
    def _setup_monitor_thread(self):
        self.thread = QThread()
        self.monitor = SystemMonitor(refresh_interval=REFRESH_INTERVAL_MS / 1000.0)
        self.monitor.moveToThread(self.thread)
        self.thread.started.connect(self.monitor.run)
        self.monitor.data_updated.connect(self.update_ui)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    @Slot(dict)
    def update_ui(self, data: Dict[str, Any]):
        self._update_overview_tab(data)
        self._update_per_core_tab(data['cpu']['per_cpu_percent'])
        self._update_gpu_tab(data['gpu'])
        self._update_processes_tab(data['processes'])
        self.statusBar().showMessage(f"Last updated: {time.strftime('%H:%M:%S')}")

    def _update_overview_tab(self, data: Dict[str, Any]):
        cpu_percent = data['cpu']['total_percent']
        self.cpu_total_label.setText(f"CPU Total Usage: {cpu_percent:.1f}%")
        self.cpu_total_progress.setValue(int(cpu_percent))
        self._set_progress_bar_style(self.cpu_total_progress, cpu_percent)
        self.cpu_history.append(cpu_percent)
        self.cpu_chart.plot(list(self.cpu_history), clear=True, pen='c')
        ram_data = data['ram']
        total_ram_gb = ram_data['total'] / (1024**3)
        used_ram_gb = ram_data['used'] / (1024**3)
        ram_percent = ram_data['percent']
        self.ram_usage_label.setText(f"RAM Usage: {used_ram_gb:.2f} / {total_ram_gb:.2f} GB ({ram_percent:.1f}%)")
        self.ram_usage_progress.setValue(int(ram_percent))
        self._set_progress_bar_style(self.ram_usage_progress, ram_percent)
        self.ram_history.append(ram_percent)
        self.ram_chart.plot(list(self.ram_history), clear=True, pen='m')
        
    def _update_per_core_tab(self, per_cpu_data: List[float]):
        for i, (label, progress) in enumerate(self.per_core_widgets):
            if i < len(per_cpu_data):
                percent = per_cpu_data[i]
                label.setText(f"Core {i}: {percent:.1f}%")
                progress.setValue(int(percent))
                self._set_progress_bar_style(progress, percent)

    def _update_gpu_tab(self, gpu_data: List[Dict[str, Any]]):
        if not gpu_data and not self.gpu_widgets:
            if self.gpu_layout.count() == 0:
                self.gpu_layout.addWidget(QLabel("No compatible GPU (NVIDIA) found or required drivers are not installed."))
            return
        current_gpus = {gpu['uuid'] for gpu in gpu_data}
        for uuid in list(self.gpu_widgets.keys()):
            if uuid not in current_gpus:
                widgets = self.gpu_widgets.pop(uuid)
                widgets['frame'].deleteLater()
        for gpu in gpu_data:
            uuid = gpu['uuid']
            if uuid not in self.gpu_widgets:
                frame = QFrame()
                frame.setFrameShape(QFrame.StyledPanel)
                layout = QGridLayout(frame)
                name_label = QLabel(f"<b>{gpu['name']}</b>")
                mem_label, mem_progress = QLabel(), QProgressBar()
                util_label, util_progress = QLabel(), QProgressBar()
                chart = self._create_plot_widget("GPU Usage History (%)")
                layout.addWidget(name_label, 0, 0, 1, 2)
                layout.addWidget(util_label, 1, 0); layout.addWidget(util_progress, 1, 1)
                layout.addWidget(mem_label, 2, 0); layout.addWidget(mem_progress, 2, 1)
                layout.addWidget(chart, 0, 2, 3, 1)
                self.gpu_layout.addWidget(frame)
                self.gpu_widgets[uuid] = {'frame': frame, 'mem_label': mem_label, 'mem_progress': mem_progress, 'util_label': util_label, 'util_progress': util_progress, 'chart': chart}
                self.gpu_history[uuid] = deque([0] * CHART_HISTORY_LENGTH, maxlen=CHART_HISTORY_LENGTH)
            widgets = self.gpu_widgets[uuid]
            mem_used_gb, mem_total_gb, mem_percent = gpu['used_memory'] / (1024**3), gpu['total_memory'] / (1024**3), gpu['memory_percent']
            widgets['mem_label'].setText(f"Memory: {mem_used_gb:.2f}/{mem_total_gb:.2f} GB")
            widgets['mem_progress'].setValue(int(mem_percent)); self._set_progress_bar_style(widgets['mem_progress'], mem_percent)
            util_percent = gpu['gpu_utilization']
            widgets['util_label'].setText(f"Utilization: {util_percent}%")
            widgets['util_progress'].setValue(util_percent); self._set_progress_bar_style(widgets['util_progress'], util_percent)
            self.gpu_history[uuid].append(util_percent)
            widgets['chart'].plot(list(self.gpu_history[uuid]), clear=True, pen='g')
            
    def _update_processes_tab(self, processes: List[Dict[str, Any]]):
        self.process_table.setSortingEnabled(False)
        new_pids = {p['pid'] for p in processes}
        current_pids = set(self.process_widgets.keys())
        for pid in current_pids - new_pids:
            row_to_remove = -1
            for row in range(self.process_table.rowCount()):
                pid_item = self.process_table.item(row, 0)
                if pid_item and int(pid_item.text()) == pid:
                    row_to_remove = row
                    break
            if row_to_remove != -1: self.process_table.removeRow(row_to_remove)
            if pid in self.process_widgets: del self.process_widgets[pid]
        for proc_data in processes:
            pid = proc_data['pid']
            if pid in self.process_widgets:
                row_items = self.process_widgets[pid]
                row_items['cpu'].setText(f"{proc_data['cpu_percent']:.1f}")
                row_items['ram'].setText(f"{proc_data['memory_percent']:.2f}")
                row_items['gpu_mem'].setText(f"{proc_data['gpu_memory_bytes'] / (1024**2):.2f}")
                row_items['mem_bytes'].setText(f"{proc_data['memory_bytes'] / (1024**2):.2f}")
            else:
                row_position = self.process_table.rowCount()
                self.process_table.insertRow(row_position)
                pid_item = QTableWidgetItem(); pid_item.setData(Qt.DisplayRole, pid)
                items = {'pid': pid_item, 'name': QTableWidgetItem(proc_data['name']), 'cpu': QTableWidgetItem(f"{proc_data['cpu_percent']:.1f}"), 'ram': QTableWidgetItem(f"{proc_data['memory_percent']:.2f}"), 'gpu_mem': QTableWidgetItem(f"{proc_data['gpu_memory_bytes'] / (1024**2):.2f}"), 'mem_bytes': QTableWidgetItem(f"{proc_data['memory_bytes'] / (1024**2):.2f}"), 'command': QTableWidgetItem(proc_data['command'])}
                for key in ['pid', 'cpu', 'ram', 'gpu_mem', 'mem_bytes']: items[key].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                for i, key in enumerate(['pid', 'name', 'cpu', 'ram', 'gpu_mem', 'mem_bytes', 'command']): self.process_table.setItem(row_position, i, items[key])
                self.process_widgets[pid] = items
        self.process_table.setSortingEnabled(True)
        self._filter_processes()

    def _filter_processes(self):
        filter_text = self.search_input.text().lower()
        for row in range(self.process_table.rowCount()):
            pid_item = self.process_table.item(row, 0)
            name_item = self.process_table.item(row, 1)
            if pid_item and name_item:
                pid_match = filter_text in pid_item.text().lower()
                name_match = filter_text in name_item.text().lower()
                self.process_table.setRowHidden(row, not (pid_match or name_match))

    def _show_process_context_menu(self, pos):
        selected_items = self.process_table.selectedItems()
        if not selected_items: return
        menu = QMenu()
        kill_action = QAction("Kill Process", self)
        kill_action.triggered.connect(self._kill_selected_process)
        menu.addAction(kill_action)
        menu.exec(self.process_table.viewport().mapToGlobal(pos))
        
    def _kill_selected_process(self):
        selected_items = self.process_table.selectedItems()
        if not selected_items: return
        row = selected_items[0].row()
        pid = int(self.process_table.item(row, 0).text())
        name = self.process_table.item(row, 1).text()
        reply = QMessageBox.question(self, 'Confirm Kill', f"Are you sure you want to terminate process '{name}' (PID: {pid})?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                p = psutil.Process(pid)
                p.terminate()
                log.info(f"Attempted to terminate process {name} (PID: {pid}).")
                QMessageBox.information(self, "Success", f"Termination signal sent to '{name}'.")
            except psutil.NoSuchProcess:
                log.warning(f"Process {pid} no longer exists.")
                QMessageBox.warning(self, "Error", "Process no longer exists.")
            except psutil.AccessDenied:
                log.error(f"Access denied to terminate process {pid}.")
                QMessageBox.critical(self, "Error", "Access denied. Try running as administrator.")

    def _set_progress_bar_style(self, pbar: QProgressBar, value: float):
        if value > HIGH_USAGE_THRESHOLD: pbar.setStyleSheet(HIGH_USAGE_STYLE)
        else: pbar.setStyleSheet(NORMAL_USAGE_STYLE)

    def closeEvent(self, event):
        log.info("Close event triggered. Shutting down monitor thread.")
        self.monitor.stop()
        self.thread.quit()
        self.thread.wait(2000)
        event.accept()
