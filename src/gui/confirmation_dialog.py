from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from src.gui.theme import stylesheet, DANGER, TEXT

class ConfirmationDialog(QDialog):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 150)
        self.setStyleSheet(stylesheet())
        
        # Remove context help button (?) on Windows
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        
        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet(f"color: {TEXT}; font-size: 14px;")
        layout.addWidget(lbl_msg)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 32)
        cancel_btn.clicked.connect(self.reject)
        
        confirm_btn = QPushButton("Confirm")
        confirm_btn.setFixedSize(100, 32)
        confirm_btn.setStyleSheet(f"background-color: {DANGER}; border: none;")
        confirm_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)
        
        layout.addLayout(btn_layout)
