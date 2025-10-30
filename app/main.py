import sys, asyncio, time
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QProgressBar
from PySide6.QtCore import QTimer, Qt
from app.ftp_client import FTPClient

# Minimal widget instead of importing from widgets.py (simplified)
class FileTransferWidget(QWidget):
    def __init__(self, title="File Transfer"):
        super().__init__()
        self.label_status = QLabel(f"{title}: Idle")
        self.progress_bar = QProgressBar()
        self.btn_select = QPushButton("Select File")
        self.btn_put = QPushButton("PUT")
        self.btn_get = QPushButton("GET")

        layout = QVBoxLayout()
        layout.addWidget(self.label_status)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.btn_select)
        layout.addWidget(self.btn_put)
        layout.addWidget(self.btn_get)
        self.setLayout(layout)

        self.selected_file = None
        self.remote_name = None

        self.btn_select.clicked.connect(self.select_file)

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            self.selected_file = path
            self.remote_name = path.split("/")[-1]
            self.label_status.setText(f"Selected: {self.remote_name}")

    def update_progress(self, value, max_value=100):
        self.progress_bar.setMaximum(max_value)
        self.progress_bar.setValue(value)

    def update_status(self, text):
        self.label_status.setText(text)

# ------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini-FTP GUI")
        self.client = FTPClient(loss_rate=0.05)
        self.loop = asyncio.get_event_loop()

        self.transfer_widget = FileTransferWidget()
        self.label_metrics = QLabel("Metrics: N/A")

        layout = QVBoxLayout()
        layout.addWidget(self.transfer_widget)
        layout.addWidget(self.label_metrics)
        self.setLayout(layout)

        # Hook buttons
        self.transfer_widget.btn_put.clicked.connect(self.start_put)
        self.transfer_widget.btn_get.clicked.connect(self.start_get)

        # Timer to integrate asyncio with PySide6
        self.timer = QTimer()
        self.timer.timeout.connect(self.loop_iteration)
        self.timer.start(50)  # 20Hz

    def loop_iteration(self):
        self.loop.call_soon(self.loop.stop)
        self.loop.run_forever()

    # ------------------------
    def start_put(self):
        if not self.transfer_widget.selected_file:
            self.transfer_widget.update_status("No file selected for PUT")
            return
        self.transfer_widget.update_status("Starting PUT...")
        self.loop.create_task(self.put_task())

    async def put_task(self):
        await self.client.start()
        start_time = time.time()
        await self.client.put_file(
            self.transfer_widget.selected_file,
            self.transfer_widget.remote_name,
            resume=True
        )
        duration = time.time() - start_time
        self.transfer_widget.update_status(f"PUT complete in {duration:.2f}s")
        self.update_metrics()

    # ------------------------
    def start_get(self):
        if not self.transfer_widget.remote_name:
            self.transfer_widget.update_status("No file selected for GET")
            return
        self.transfer_widget.update_status("Starting GET...")
        self.loop.create_task(self.get_task())

    async def get_task(self):
        await self.client.start()
        start_time = time.time()
        await self.client.get_file(
            self.transfer_widget.remote_name,
            self.transfer_widget.remote_name,
            resume=True
        )
        duration = time.time() - start_time
        self.transfer_widget.update_status(f"GET complete in {duration:.2f}s")
        self.update_metrics()

    # ------------------------
    def update_metrics(self):
        m = self.client.metrics.report()
        text = (f"Bytes sent: {m['total_bytes']}, "
                f"Retransmissions: {m['retransmissions']}, "
                f"Avg latency: {m['avg_latency_ms']:.2f}ms, "
                f"p95 latency: {m['p95_latency_ms']:.2f}ms")
        self.label_metrics.setText(text)

# ------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(400, 300)
    win.show()
    sys.exit(app.exec())
