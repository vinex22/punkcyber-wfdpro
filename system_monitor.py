"""
System Monitor GUI - PyQt5 + psutil
A simple system resource monitor similar to what the _MEI604122 app appears to do.
"""

import sys
import psutil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QTableWidget, QTableWidgetItem, QTabWidget,
    QHeaderView, QPushButton
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont


class SystemMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Monitor")
        self.setMinimumSize(800, 600)

        # Central widget with tabs
        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        # --- Overview tab ---
        overview = QWidget()
        overview_layout = QVBoxLayout(overview)

        # CPU
        cpu_label = QLabel("CPU Usage")
        cpu_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setMaximum(100)
        self.cpu_percent_label = QLabel("0%")

        cpu_row = QHBoxLayout()
        cpu_row.addWidget(self.cpu_bar, stretch=1)
        cpu_row.addWidget(self.cpu_percent_label)

        overview_layout.addWidget(cpu_label)
        overview_layout.addLayout(cpu_row)

        # Per-core CPU
        self.core_bars = []
        cores_label = QLabel("Per-Core CPU")
        cores_label.setFont(QFont("Segoe UI", 10))
        overview_layout.addWidget(cores_label)
        self.cores_layout = QVBoxLayout()
        for i in range(psutil.cpu_count(logical=True)):
            row = QHBoxLayout()
            lbl = QLabel(f"Core {i}")
            bar = QProgressBar()
            bar.setMaximum(100)
            bar.setFixedHeight(18)
            row.addWidget(lbl, stretch=0)
            row.addWidget(bar, stretch=1)
            self.cores_layout.addLayout(row)
            self.core_bars.append(bar)
        overview_layout.addLayout(self.cores_layout)

        # Memory
        mem_label = QLabel("Memory Usage")
        mem_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.mem_bar = QProgressBar()
        self.mem_bar.setMaximum(100)
        self.mem_detail_label = QLabel("")

        mem_row = QHBoxLayout()
        mem_row.addWidget(self.mem_bar, stretch=1)
        mem_row.addWidget(self.mem_detail_label)

        overview_layout.addWidget(mem_label)
        overview_layout.addLayout(mem_row)

        # Disk
        disk_label = QLabel("Disk Usage")
        disk_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        overview_layout.addWidget(disk_label)

        self.disk_table = QTableWidget()
        self.disk_table.setColumnCount(5)
        self.disk_table.setHorizontalHeaderLabels(["Drive", "Total", "Used", "Free", "Usage %"])
        self.disk_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        overview_layout.addWidget(self.disk_table)

        # Network
        net_label = QLabel("Network I/O")
        net_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.net_label = QLabel("")
        overview_layout.addWidget(net_label)
        overview_layout.addWidget(self.net_label)

        tabs.addTab(overview, "Overview")

        # --- Processes tab ---
        proc_widget = QWidget()
        proc_layout = QVBoxLayout(proc_widget)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.update_processes)
        proc_layout.addWidget(refresh_btn)

        self.proc_table = QTableWidget()
        self.proc_table.setColumnCount(5)
        self.proc_table.setHorizontalHeaderLabels(["PID", "Name", "CPU %", "Memory %", "Status"])
        self.proc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.proc_table.setSortingEnabled(True)
        proc_layout.addWidget(self.proc_table)

        tabs.addTab(proc_widget, "Processes")

        # Timer for live updates (every 2 seconds)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)

        # Initial update
        self.update_stats()
        self.update_processes()

    def update_stats(self):
        # CPU
        cpu = psutil.cpu_percent(interval=0)
        self.cpu_bar.setValue(int(cpu))
        self.cpu_percent_label.setText(f"{cpu:.1f}%")

        # Per-core
        per_cpu = psutil.cpu_percent(percpu=True)
        for i, pct in enumerate(per_cpu):
            if i < len(self.core_bars):
                self.core_bars[i].setValue(int(pct))

        # Memory
        mem = psutil.virtual_memory()
        self.mem_bar.setValue(int(mem.percent))
        self.mem_detail_label.setText(
            f"{self._fmt(mem.used)} / {self._fmt(mem.total)} ({mem.percent}%)"
        )

        # Disk
        partitions = psutil.disk_partitions(all=False)
        self.disk_table.setRowCount(len(partitions))
        for row, part in enumerate(partitions):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                self.disk_table.setItem(row, 0, QTableWidgetItem(part.device))
                self.disk_table.setItem(row, 1, QTableWidgetItem(self._fmt(usage.total)))
                self.disk_table.setItem(row, 2, QTableWidgetItem(self._fmt(usage.used)))
                self.disk_table.setItem(row, 3, QTableWidgetItem(self._fmt(usage.free)))
                self.disk_table.setItem(row, 4, QTableWidgetItem(f"{usage.percent}%"))
            except PermissionError:
                self.disk_table.setItem(row, 0, QTableWidgetItem(part.device))
                for c in range(1, 5):
                    self.disk_table.setItem(row, c, QTableWidgetItem("N/A"))

        # Network
        net = psutil.net_io_counters()
        self.net_label.setText(
            f"Sent: {self._fmt(net.bytes_sent)}   |   Received: {self._fmt(net.bytes_recv)}"
        )

    def update_processes(self):
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                info = p.info
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by memory usage descending
        procs.sort(key=lambda x: x.get('memory_percent') or 0, reverse=True)
        procs = procs[:200]  # Limit to top 200

        self.proc_table.setSortingEnabled(False)
        self.proc_table.setRowCount(len(procs))
        for row, p in enumerate(procs):
            self.proc_table.setItem(row, 0, QTableWidgetItem(str(p.get('pid', ''))))
            self.proc_table.setItem(row, 1, QTableWidgetItem(str(p.get('name', ''))))
            self.proc_table.setItem(row, 2, QTableWidgetItem(f"{p.get('cpu_percent', 0):.1f}"))
            self.proc_table.setItem(row, 3, QTableWidgetItem(f"{p.get('memory_percent', 0):.1f}"))
            self.proc_table.setItem(row, 4, QTableWidgetItem(str(p.get('status', ''))))
        self.proc_table.setSortingEnabled(True)

    @staticmethod
    def _fmt(num_bytes):
        """Format bytes to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if abs(num_bytes) < 1024:
                return f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024
        return f"{num_bytes:.1f} PB"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SystemMonitor()
    window.show()
    sys.exit(app.exec_())
