from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget
)
from PySide6.QtCore import Qt
from .theme import TEXT_SECONDARY, SUCCESS, ACCENT, DANGER, BORDER
from .animations import fade_in


class ActionItem(QFrame):
    def __init__(self, summary: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border-bottom: 1px solid {BORDER};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)
        
        # Check icon and title
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        
        status = summary.get("status", "success")
        icon_char = "✓"
        color = SUCCESS
        if status == "info":
            icon_char = "ℹ"
            color = ACCENT
        elif status not in ["success", "completed", "partial_success"]:
            icon_char = "❌"
            color = DANGER
            
        check = QLabel(icon_char)
        check.setStyleSheet(f"color: {color}; font-weight: bold; border: none;")
        
        title = summary.get("title", "Operation Result")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 600; border: none;")
        title_lbl.setWordWrap(True)
        
        # Ensure heightForWidth is respected
        policy = title_lbl.sizePolicy()
        policy.setHeightForWidth(True)
        title_lbl.setSizePolicy(policy)
        
        top_row.addWidget(check)
        top_row.addWidget(title_lbl, 1)
        
        layout.addLayout(top_row)
        
        # Subtitle
        subtitle = summary.get("subtitle", "")
        if subtitle:
            subtitle_lbl = QLabel(subtitle)
            subtitle_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; border: none;")
            subtitle_lbl.setWordWrap(True)
            subtitle_policy = subtitle_lbl.sizePolicy()
            subtitle_policy.setHeightForWidth(True)
            subtitle_lbl.setSizePolicy(subtitle_policy)
            layout.addWidget(subtitle_lbl)
            
        # Ensure the frame itself respects heightForWidth
        frame_policy = self.sizePolicy()
        frame_policy.setHeightForWidth(True)
        self.setSizePolicy(frame_policy)


class StatusCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(12)

        header = QLabel("SYSTEM STATUS")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        self.labels = {}
        fields = [
            ("Automation Engine", "Online"),
            ("Voice", "Ready"),
            ("Executor", "Idle"),
            ("Ollama", "Ready"),
            ("Current Mode", "Idle"),
            ("Current Task", "None")
        ]

        for label_text, default_val in fields:
            row = QHBoxLayout()
            
            # The bullet dot
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {ACCENT}; font-size: 10px; margin-right: 4px;")
            dot.setAlignment(Qt.AlignCenter)
            
            label = QLabel(label_text)
            label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
            
            val_label = QLabel(default_val)
            val_label.setStyleSheet(f"color: {ACCENT}; font-weight: 600; font-size: 12px;")
            val_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            row.addWidget(label)
            row.addStretch(1)
            row.addWidget(dot)
            row.addWidget(val_label)
            
            layout.addLayout(row)
            self.labels[label_text] = val_label

    def update_status(self, key: str, value: str):
        if key in self.labels:
            self.labels[key].setText(value)

    def set_mode(self, mode: str):
        self.update_status("Current Mode", mode)


class Sidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Increase width slightly for better reading of subtitles
        self.setFixedWidth(280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        self.status_card = StatusCard()
        layout.addWidget(self.status_card)

        self.actions_panel = QFrame()
        self.actions_panel.setObjectName("panel")
        actions_layout = QVBoxLayout(self.actions_panel)
        actions_layout.setContentsMargins(14, 14, 14, 14)
        actions_layout.setSpacing(8)

        header = QLabel("RECENT ACTIONS")
        header.setObjectName("sectionHeader")
        actions_layout.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.list_container)
        actions_layout.addWidget(self.scroll)

        layout.addWidget(self.actions_panel, 1)

    def add_action(self, summary: dict):
        item = ActionItem(summary)
        self.list_layout.insertWidget(0, item)  # newest on top
        fade_in(item)
