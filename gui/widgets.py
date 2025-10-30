from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QProgressBar, QFileDialog

class FileTransferWidget(QWidget):
    """Widget to handle file transfer with progress and metrics"""
    def __init__(self, title="File Transfer"):
        super().__init__()
        self.label_status = QLabel(f"{title}: Idle")
        self.progress_bar = QProgressBar()
        self.btn_select = QPushButton("Select File")
        self.btn_start_put = QPushButton("PUT")
        self.btn_start_get = QPushButton("GET")

        layout = QVBoxLayout()
        layout.addWidget(self.label_status)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.btn_select)
        layout.addWidget(self.btn_start_put)
        layout.addWidget(self.btn_start_get)
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
