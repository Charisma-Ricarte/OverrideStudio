# gui/widgets.py
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QProgressBar, QFileDialog, QLineEdit, QListWidget
)
from pathlib import Path

class FileTransferWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.status = QLabel("Idle")
        self.server_list = QListWidget()
        self.progress = QProgressBar()
        self.remote_input = QLineEdit()
        self.remote_input.setPlaceholderText("Remote filename")
        self.btn_select = QPushButton("Select Local File")
        self.btn_put = QPushButton("PUT")
        self.btn_get = QPushButton("GET")
        self.btn_list = QPushButton("LIST")
        self.btn_delete = QPushButton("Delete Selected")

        left = QVBoxLayout()
        left.addWidget(self.server_list)
        left.addWidget(self.btn_list)
        left.addWidget(self.btn_delete)

        right = QVBoxLayout()
        right.addWidget(self.status)
        right.addWidget(self.progress)
        right.addWidget(self.remote_input)
        right.addWidget(self.btn_select)
        right.addWidget(self.btn_put)
        right.addWidget(self.btn_get)
        right.addStretch()

        layout = QHBoxLayout()
        layout.addLayout(left)
        layout.addLayout(right)
        self.setLayout(layout)

    def select_local_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Local File")
        if path:
            self.remote_input.setText(Path(path).name)
            self.status.setText(f"Local selected: {path}")
