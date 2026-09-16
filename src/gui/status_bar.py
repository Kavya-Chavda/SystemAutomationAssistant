from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from PySide6.QtCore import QTimer, QDateTime
from .theme import TEXT_SECONDARY, SUCCESS


class BottomStatusBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)

        self.time_label = QLabel()
        self.time_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")

        self.model_label = QLabel("Model: Unknown")
        self.model_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")

        self.ready_label = QLabel("● Checking...")
        self.ready_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")

        layout.addWidget(self.time_label)
        layout.addStretch(1)
        layout.addWidget(self.model_label)
        layout.addSpacing(16)
        layout.addWidget(self.ready_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_time)
        self._timer.start(1000)
        self._update_time()

    def set_model(self, model_name: str):
        self.model_label.setText(f"Model: {model_name}")

    def update_model_status(self, model_name: str, text: str, color: str):
        self.model_label.setText(f"Model: {model_name}")
        self.ready_label.setText(f"● {text}")
        self.ready_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _update_time(self):
        self.time_label.setText(QDateTime.currentDateTime().toString("hh:mm:ss  |  dd MMM yyyy"))
