# gui/widgets.py
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QProgressBar, QFileDialog, QLineEdit, QListWidget, QListWidgetItem
)


class FileTransferWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.server_list = QListWidget()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_delete = QPushButton("Delete")

        self.label_status = QLabel("Status: Idle")
        self.progress_bar = QProgressBar()

        self.btn_select = QPushButton("Select Local File")
        self.remote_name_input = QLineEdit()

        self.btn_put = QPushButton("PUT")
        self.btn_get = QPushButton("GET")

        layout = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()

        left.addWidget(QLabel("Server Files"))
        left.addWidget(self.server_list)
        left.addWidget(self.btn_refresh)
        left.addWidget(self.btn_delete)

        right.addWidget(self.label_status)
        right.addWidget(self.progress_bar)
        right.addWidget(self.btn_select)
        right.addWidget(self.remote_name_input)
        right.addWidget(self.btn_put)
        right.addWidget(self.btn_get)
        right.addStretch()

        layout.addLayout(left)
        layout.addLayout(right)
        self.setLayout(layout)

        self.selected_file = None
        self.btn_select.clicked.connect(self.pick_file)

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if path:
            self.selected_file = path
            self.label_status.setText(f"Selected: {path}")

    def update_list(self, items):
        self.server_list.clear()
        for i in items:
            self.server_list.addItem(QListWidgetItem(i))

    def set_progress(self, value):
        self.progress_bar.setValue(value)

    def set_status(self, msg):
        self.label_status.setText(msg)
