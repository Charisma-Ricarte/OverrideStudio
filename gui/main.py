# gui/main.py
import sys
import asyncio
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QListWidget, QProgressBar, QLineEdit
)
from PySide6.QtCore import QTimer

from app.ftp_client import FTPClient


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini-FTP GUI")

        # Async loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # FTP Client
        self.client = FTPClient()

        # UI ----------------------------
        self.status = QLabel("Status: Idle")
        self.remote_list = QListWidget()

        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Remote filename")

        self.btn_list = QPushButton("LIST Files")
        self.btn_select = QPushButton("Select Local File")
        self.btn_put = QPushButton("PUT")
        self.btn_get = QPushButton("GET")
        self.btn_delete = QPushButton("DELETE")

        self.progress = QProgressBar()

        layout = QVBoxLayout()
        layout.addWidget(self.status)
        layout.addWidget(self.remote_list)
        layout.addWidget(self.filename_input)
        layout.addWidget(self.progress)
        layout.addWidget(self.btn_list)
        layout.addWidget(self.btn_select)
        layout.addWidget(self.btn_put)
        layout.addWidget(self.btn_get)
        layout.addWidget(self.btn_delete)
        self.setLayout(layout)

        self.selected_file = None

        # Button events
        self.btn_select.clicked.connect(self.pick_file)
        self.btn_list.clicked.connect(lambda: self.run_async(self.do_list()))
        self.btn_put.clicked.connect(lambda: self.run_async(self.do_put()))
        self.btn_get.clicked.connect(lambda: self.run_async(self.do_get()))
        self.btn_delete.clicked.connect(lambda: self.run_async(self.do_delete()))

        # Poll async loop periodically
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(5)

    # ------------------------------
    def tick(self):
        try:
            self.loop.stop()
            self.loop.run_forever()
        except Exception as e:
            print("Loop tick error:", e)

    def run_async(self, coro):
        asyncio.ensure_future(coro, loop=self.loop)

    # ------------------------------
    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            self.selected_file = path
            self.status.setText(f"Selected: {path}")

    # ------------------------------
    async def do_list(self):
        self.status.setText("Listing...")
        await self.client.start()

        files = await self.client.list_files()
        self.remote_list.clear()

        for f in files:
            self.remote_list.addItem(f)

        self.status.setText("LIST complete")

    async def do_put(self):
        if not self.selected_file:
            self.status.setText("No file selected")
            return

        await self.client.start()

        remote = self.filename_input.text() or self.selected_file.split("/")[-1]
        self.status.setText(f"Uploading {remote}...")

        await self.client.put_file(self.selected_file, remote)
        self.status.setText("PUT complete")

    async def do_get(self):
        remote = self.filename_input.text().strip()
        if not remote:
            self.status.setText("Enter filename")
            return

        await self.client.start()
        self.status.setText(f"Downloading {remote}...")

        await self.client.get_file(remote, remote)
        self.status.setText("GET complete")

    async def do_delete(self):
        remote = self.filename_input.text().strip()
        if not remote:
            self.status.setText("Enter filename")
            return

        await self.client.start()

        ok = await self.client.delete_file(remote)
        self.status.setText("Delete OK" if ok else "Delete failed")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(500, 500)
    win.show()
    sys.exit(app.exec())
