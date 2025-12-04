# gui/main.py
import sys
import asyncio
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QListWidget, QProgressBar, QLineEdit
)
from PySide6.QtCore import QTimer

from app.ftp_client import FTPClient
from app.fileops import count_chunks

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini-FTP GUI (Improved)")
        self.resize(700, 480)

        # dedicated asyncio loop for the GUI
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.client = FTPClient(loss_rate=0.0)
        self.selected_file = None

        # Left: server file list
        self.server_list = QListWidget()
        self.btn_list = QPushButton("Refresh LIST")
        self.btn_delete = QPushButton("Delete Selected")

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("<b>Server files</b>"))
        left_layout.addWidget(self.server_list)
        left_layout.addWidget(self.btn_list)
        left_layout.addWidget(self.btn_delete)

        # Right: controls
        self.status = QLabel("Status: Idle")
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Remote filename")

        self.btn_select = QPushButton("Select Local File")
        self.btn_put = QPushButton("PUT (Upload)")
        self.btn_get = QPushButton("GET (Download)")

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.status)
        right_layout.addWidget(self.progress)
        right_layout.addWidget(QLabel("Remote filename"))
        right_layout.addWidget(self.filename_input)
        right_layout.addWidget(self.btn_select)
        right_layout.addWidget(self.btn_put)
        right_layout.addWidget(self.btn_get)
        right_layout.addStretch()

        container = QHBoxLayout()
        container.addLayout(left_layout, 1)
        container.addLayout(right_layout, 2)
        self.setLayout(container)

        # connections
        self.btn_list.clicked.connect(lambda: self.run_async(self.do_list()))
        self.btn_delete.clicked.connect(lambda: self.run_async(self.do_delete_selected()))
        self.btn_select.clicked.connect(self.pick_file)
        self.btn_put.clicked.connect(lambda: self.run_async(self.do_put()))
        self.btn_get.clicked.connect(lambda: self.run_async(self.do_get()))

        # Qt <-> asyncio integration timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._qt_iteration)
        self.timer.start(10)

    def _qt_iteration(self):
        try:
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()
        except Exception:
            pass

    def run_async(self, coro):
        asyncio.ensure_future(coro, loop=self.loop)

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            self.selected_file = path
            self.filename_input.setText(Path(path).name)
            self.status.setText(f"Selected: {path}")

    async def do_list(self):
        try:
            await self.client.start()
            files = await self.client.list_files()
            self.server_list.clear()
            for f in files:
                self.server_list.addItem(f)
            self.status.setText("LIST complete")
        except Exception as e:
            self.status.setText(f"LIST failed: {e}")

    async def do_delete_selected(self):
        item = self.server_list.currentItem()
        if not item:
            self.status.setText("Select item to delete")
            return
        name = item.text()
        await self.client.start()
        ok = await self.client.delete_file(name)
        self.status.setText("DELETE OK" if ok else "DELETE failed")
        await self.do_list()

    async def do_put(self):
        if not self.selected_file:
            self.status.setText("Select a local file first")
            return
        try:
            await self.client.start()
            remote = self.filename_input.text().strip() or Path(self.selected_file).name
            total = count_chunks(self.selected_file)
            def progress_cb(done, total_count):
                pct = int(done / total_count * 100) if total_count else 100
                self.progress.setMaximum(100)
                self.progress.setValue(pct)
            self.client.on_progress = progress_cb
            self.progress.setValue(0)
            self.status.setText("Uploading...")
            await self.client.put_file(self.selected_file, remote)
            self.status.setText("PUT complete")
            self.progress.setValue(100)
            self.client.on_progress = None
            await self.do_list()
        except Exception as e:
            self.status.setText(f"PUT failed: {e}")
            self.client.on_progress = None

    async def do_get(self):
        name = self.filename_input.text().strip()
        if not name:
            self.status.setText("Enter remote filename")
            return
        # Ask user where to save
        save_path, _ = QFileDialog.getSaveFileName(self, "Save As", name)
        if not save_path:
            self.status.setText("GET cancelled")
            return
        try:
            await self.client.start()
            self.status.setText("Downloading...")
            await self.client.get_file(name, save_path)
            self.status.setText(f"GET complete -> {save_path}")
        except FileNotFoundError:
            self.status.setText("GET failed: remote not found")
        except Exception as e:
            self.status.setText(f"GET failed: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
