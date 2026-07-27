# ui/assistant_dialog.py
"""
AI Assistant Dialog – offline, multilingual inventory Q&A (PyQt6).
Supports Persian/English UI, RTL/LTR, non-blocking queries, and chat export.
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton,
    QComboBox, QLabel, QFileDialog, QMessageBox, QWidget, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QTextCursor, QAction

from ai.llm_helper import LLMHelper


# ======================================================================
# Translations (UI strings) - FA/EN only (current requirement)
# ======================================================================
UI_TEXT = {
    "en": {
        "window_title": "📦 Inventory Assistant (Offline)",
        "placeholder": "Type your question (e.g., Do we have FLG-100? / گسکت چی داریم؟)",
        "send": "Send",
        "clear": "Clear",
        "stop": "Stop",
        "export": "Export Chat",
        "language": "Language:",
        "thinking": "Searching the database…",
        "you": "You",
        "assistant": "Assistant",
        "system": "System",
        "welcome": (
            "<b>Welcome to iMat Assistant!</b><br>"
            "You can ask questions like:<br>"
            "• What items do we have with 'gasket'?<br>"
            "• Do we have FLG-100?<br>"
            "• Show low stock items below 15<br>"
            "• Recent transactions 7 days<br>"
            "• Warehouse summary<br>"
            "I answer using your inventory database — no internet required."
        ),
        "cleared": "Chat cleared. Ask a new question about your inventory.",
        "error": "Error",
        "empty_response": "Empty response from assistant.",
        "busy_warn": "Please wait, previous request is still running.",
        "export_success": "Chat exported successfully.",
        "export_failed": "Failed to export chat.",
        "sample_label": "Quick questions:",
        "auto": "Auto-detect",
        "status_ready": "Ready",
        "status_busy": "Processing...",
    },
    "fa": {
        "window_title": "📦 دستیار انبار (آفلاین)",
        "placeholder": "سوال خود را بنویسید (مثلاً: گسکت چی داریم؟ / Do we have FLG-100?)",
        "send": "ارسال",
        "clear": "پاک‌سازی",
        "stop": "توقف",
        "export": "خروجی گفتگو",
        "language": "زبان:",
        "thinking": "در حال جستجو در پایگاه داده…",
        "you": "شما",
        "assistant": "دستیار",
        "system": "سیستم",
        "welcome": (
            "<b>به دستیار iMat خوش آمدید!</b><br>"
            "می‌توانید سوالاتی مانند این بپرسید:<br>"
            "• چه گسکت‌هایی داریم؟<br>"
            "• FLG-100 داریم؟<br>"
            "• کمبود زیر ۱۵ تا چی داریم؟<br>"
            "• تراکنش‌های ۷ روز اخیر<br>"
            "• خلاصه وضعیت انبار<br>"
            "من با استفاده از پایگاه داده انبار شما پاسخ می‌دهم — بدون نیاز به اینترنت."
        ),
        "cleared": "گفتگو پاک شد. سوال جدیدی درباره انبار خود بپرسید.",
        "error": "خطا",
        "empty_response": "پاسخ دستیار خالی بود.",
        "busy_warn": "درخواست قبلی هنوز در حال پردازش است.",
        "export_success": "خروجی گفتگو با موفقیت ذخیره شد.",
        "export_failed": "ذخیره خروجی گفتگو ناموفق بود.",
        "sample_label": "سوالات سریع:",
        "auto": "تشخیص خودکار",
        "status_ready": "آماده",
        "status_busy": "در حال پردازش...",
    },
}


# ======================================================================
# Worker (background thread)
# ======================================================================
class QueryWorker(QObject):
    finished = pyqtSignal(str)   # response_html
    failed = pyqtSignal(str)     # error message

    def __init__(self, assistant: LLMHelper, question: str, lang: Optional[str]):
        super().__init__()
        self.assistant = assistant
        self.question = question
        self.lang = lang

    def run(self):
        try:
            # Compatible with both signatures
            try:
                response = self.assistant.answer_query(self.question, lang=self.lang)
            except TypeError:
                response = self.assistant.answer_query(self.question)
            self.finished.emit(response or "")
        except Exception as e:
            self.failed.emit(str(e))


# ======================================================================
# Assistant Dialog
# ======================================================================
class AssistantDialog(QDialog):
    """Offline multilingual inventory assistant dialog."""

    SAMPLE_QUESTIONS = {
        "en": [
            "Do we have FLG-100?",
            "Show low stock below 10",
            "Where is gasket?",
            "Recent transactions 7 days",
            "Warehouse summary",
        ],
        "fa": [
            "FLG-100 داریم؟",
            "کمبود زیر ۱۰ تا چی داریم؟",
            "گسکت کجاست؟",
            "تراکنش‌های ۷ روز اخیر",
            "خلاصه انبار",
        ],
    }

    def __init__(self, parent=None, lang: str = "en"):
        super().__init__(parent)

        self.ui_lang = lang if lang in UI_TEXT else "en"
        self.assistant = LLMHelper()

        self._thread: Optional[QThread] = None
        self._worker: Optional[QueryWorker] = None
        self._message_log: List[Dict[str, str]] = []  # for export

        self._init_ui()
        self._apply_language()
        self._show_welcome()

    # ------------------------------------------------------------------
    # i18n helper
    # ------------------------------------------------------------------
    def tr_(self, key: str) -> str:
        return UI_TEXT.get(self.ui_lang, UI_TEXT["en"]).get(key, key)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _init_ui(self):
        self.resize(760, 620)
        self.setMinimumSize(680, 520)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # Top bar
        top_bar = QHBoxLayout()
        self.lang_label = QLabel()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("فارسی", "fa")
        idx = self.lang_combo.findData(self.ui_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color:#607D8B; font-size:11px;")

        top_bar.addWidget(self.lang_label)
        top_bar.addWidget(self.lang_combo)
        top_bar.addStretch(1)
        top_bar.addWidget(self.status_label)
        main_layout.addLayout(top_bar)

        # History
        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setFont(QFont("Segoe UI", 10))
        self.history_view.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        main_layout.addWidget(self.history_view, 1)

        # Quick samples row
        self.samples_wrap = QWidget()
        self.samples_layout = QHBoxLayout(self.samples_wrap)
        self.samples_layout.setContentsMargins(0, 0, 0, 0)
        self.samples_layout.setSpacing(6)

        self.samples_label = QLabel()
        self.samples_layout.addWidget(self.samples_label)

        self.sample_buttons: List[QPushButton] = []
        for _ in range(5):
            b = QPushButton()
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background:#E8F5E9;
                    border:1px solid #A5D6A7;
                    border-radius:12px;
                    padding:4px 10px;
                    color:#1B5E20;
                    font-size:11px;
                }
                QPushButton:hover { background:#C8E6C9; }
                QPushButton:disabled { color:#9E9E9E; background:#F1F8E9; }
            """)
            b.clicked.connect(self._on_sample_clicked)
            self.sample_buttons.append(b)
            self.samples_layout.addWidget(b)

        self.samples_layout.addStretch(1)
        main_layout.addWidget(self.samples_wrap)

        # Input row
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setFont(QFont("Segoe UI", 10))
        self.input_field.setStyleSheet("""
            QLineEdit {
                border: 2px solid #B0BEC5;
                border-radius: 6px;
                padding: 8px;
                background: white;
            }
            QLineEdit:focus { border-color: #004D40; }
        """)
        self.input_field.returnPressed.connect(self._ask_question)
        input_layout.addWidget(self.input_field, 1)

        self.send_button = QPushButton()
        self.send_button.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #004D40; color: white;
                border: none; border-radius: 6px; padding: 8px 16px;
            }
            QPushButton:hover { background-color: #00695C; }
            QPushButton:pressed { background-color: #00332B; }
            QPushButton:disabled { background-color: #80CBC4; }
        """)
        self.send_button.clicked.connect(self._ask_question)
        input_layout.addWidget(self.send_button)

        self.stop_button = QPushButton()
        self.stop_button.setFont(QFont("Segoe UI", 9))
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background:#FFF3E0; border:1px solid #FFB74D;
                border-radius:6px; padding:8px 12px;
            }
            QPushButton:hover { background:#FFE0B2; }
            QPushButton:disabled { background:#F5F5F5; border-color:#E0E0E0; color:#9E9E9E; }
        """)
        self.stop_button.clicked.connect(self._stop_request)
        input_layout.addWidget(self.stop_button)

        self.clear_button = QPushButton()
        self.clear_button.setFont(QFont("Segoe UI", 9))
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #ECEFF1; border: 1px solid #90A4AE;
                border-radius: 6px; padding: 8px 12px;
            }
            QPushButton:hover { background-color: #D7CCC8; }
        """)
        self.clear_button.clicked.connect(self._clear_history)
        input_layout.addWidget(self.clear_button)

        self.export_button = QPushButton()
        self.export_button.setFont(QFont("Segoe UI", 9))
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.setStyleSheet("""
            QPushButton {
                background:#E3F2FD; border:1px solid #90CAF9;
                border-radius:6px; padding:8px 12px;
            }
            QPushButton:hover { background:#BBDEFB; }
        """)
        self.export_button.clicked.connect(self._export_chat)
        input_layout.addWidget(self.export_button)

        main_layout.addLayout(input_layout)

        # shortcuts
        self._init_shortcuts()

    def _init_shortcuts(self):
        action_send = QAction(self)
        action_send.setShortcut("Ctrl+Return")
        action_send.triggered.connect(self._ask_question)
        self.addAction(action_send)

        action_clear = QAction(self)
        action_clear.setShortcut("Ctrl+L")
        action_clear.triggered.connect(self._clear_history)
        self.addAction(action_clear)

    # ------------------------------------------------------------------
    # language handling
    # ------------------------------------------------------------------
    def _apply_language(self):
        self.setWindowTitle(self.tr_("window_title"))
        self.lang_label.setText(self.tr_("language"))
        self.input_field.setPlaceholderText(self.tr_("placeholder"))
        self.send_button.setText(self.tr_("send"))
        self.clear_button.setText(self.tr_("clear"))
        self.stop_button.setText(self.tr_("stop"))
        self.export_button.setText(self.tr_("export"))
        self.samples_label.setText(self.tr_("sample_label"))
        self.status_label.setText(self.tr_("status_ready"))

        direction = Qt.LayoutDirection.RightToLeft if self.ui_lang == "fa" else Qt.LayoutDirection.LeftToRight
        self.setLayoutDirection(direction)

        self._refresh_sample_buttons()

    def _refresh_sample_buttons(self):
        samples = self.SAMPLE_QUESTIONS.get(self.ui_lang, self.SAMPLE_QUESTIONS["en"])
        for i, btn in enumerate(self.sample_buttons):
            if i < len(samples):
                btn.setText(samples[i])
                btn.setVisible(True)
            else:
                btn.setVisible(False)

    def _on_language_changed(self):
        self.ui_lang = self.lang_combo.currentData() or "en"
        self._apply_language()

    # ------------------------------------------------------------------
    # flow
    # ------------------------------------------------------------------
    def _show_welcome(self):
        self.history_view.clear()
        self._message_log.clear()
        self._append_message("system", self.tr_("welcome"))

    def _resolve_query_lang(self) -> Optional[str]:
        # explicit UI language for now (fa/en)
        return self.ui_lang

    def _on_sample_clicked(self):
        btn = self.sender()
        if isinstance(btn, QPushButton):
            self.input_field.setText(btn.text())
            self._ask_question()

    def _ask_question(self):
        question = self.input_field.text().strip()
        if not question:
            return

        if self._thread and self._thread.isRunning():
            self._append_message("system", html.escape(self.tr_("busy_warn")))
            return

        self._append_message("you", html.escape(question))
        self.input_field.clear()

        self._set_busy(True)
        self.status_label.setText(self.tr_("status_busy"))
        self._append_message("system", f"<i>{html.escape(self.tr_('thinking'))}</i>")

        self._thread = QThread(self)
        self._worker = QueryWorker(self.assistant, question, self._resolve_query_lang())
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_response)
        self._worker.failed.connect(self._on_error)

        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)

        self._thread.start()

    def _on_response(self, response_html: str):
        self._set_busy(False)
        self.status_label.setText(self.tr_("status_ready"))

        if not (response_html or "").strip():
            response_html = f"<p style='color:#C62828;'>{html.escape(self.tr_('empty_response'))}</p>"

        self._append_message("assistant", response_html)

    def _on_error(self, message: str):
        self._set_busy(False)
        self.status_label.setText(self.tr_("status_ready"))
        self._append_message(
            "assistant",
            f"<p style='color:#C62828;'><b>{html.escape(self.tr_('error'))}:</b> {html.escape(message)}</p>"
        )

    def _stop_request(self):
        if self._thread and self._thread.isRunning():
            self._thread.requestInterruption()
            self._thread.quit()
            self._thread.wait(1200)
            self._set_busy(False)
            self.status_label.setText(self.tr_("status_ready"))

    def _cleanup_thread(self):
        if self._worker:
            self._worker.deleteLater()
        if self._thread:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None

    def _set_busy(self, busy: bool):
        self.send_button.setEnabled(not busy)
        self.input_field.setEnabled(not busy)
        self.stop_button.setEnabled(busy)
        self.lang_combo.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        for b in self.sample_buttons:
            b.setEnabled(not busy)
        if not busy:
            self.input_field.setFocus()

    # ------------------------------------------------------------------
    # rendering + log
    # ------------------------------------------------------------------
    def _append_message(self, sender_key: str, content_html: str):
        """
        sender_key in {'you','assistant','system'}
        content_html can include HTML (assistant responses are HTML).
        """
        cursor = self.history_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.history_view.setTextCursor(cursor)

        if sender_key == "you":
            color, emoji = "#1565C0", "👤"
        elif sender_key == "system":
            color, emoji = "#6A1B9A", "ℹ️"
        else:
            color, emoji = "#2E7D32", "📦"

        label = self.tr_(sender_key)
        ts = datetime.now().strftime("%H:%M:%S")

        # direction based on UI language
        dir_attr = "rtl" if self.ui_lang == "fa" else "ltr"
        align = "right" if self.ui_lang == "fa" else "left"

        header = (
            f'<p dir="{dir_attr}" style="color:{color}; font-weight:bold; '
            f'margin:2px 0; text-align:{align};">'
            f'{emoji} {html.escape(label)} '
            f'<span style="font-size:10px; color:#90A4AE;">[{ts}]</span>'
            f"</p>"
        )
        body = (
            f'<div dir="{dir_attr}" style="margin:0 10px 12px 10px; text-align:{align};">'
            f"{content_html}</div>"
        )

        self.history_view.insertHtml(header + body)
        self.history_view.verticalScrollBar().setValue(
            self.history_view.verticalScrollBar().maximum()
        )

        self._message_log.append({
            "time": ts,
            "sender": sender_key,
            "label": label,
            "content_html": content_html,
        })

    # ------------------------------------------------------------------
    # clear/export
    # ------------------------------------------------------------------
    def _clear_history(self):
        self.history_view.clear()
        self._message_log.clear()
        self._append_message("system", html.escape(self.tr_("cleared")))

    def _export_chat(self):
        if not self._message_log:
            QMessageBox.information(self, self.tr_("export"), self.tr_("cleared"))
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            self.tr_("export"),
            f"assistant_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "HTML Files (*.html);;Text Files (*.txt)"
        )
        if not filename:
            return

        try:
            if filename.lower().endswith(".txt"):
                self._export_txt(filename)
            else:
                if not filename.lower().endswith(".html"):
                    filename += ".html"
                self._export_html(filename)
            QMessageBox.information(self, self.tr_("export"), self.tr_("export_success"))
        except Exception as e:
            QMessageBox.critical(self, self.tr_("error"), f"{self.tr_('export_failed')}\n{e}")

    def _export_txt(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            for m in self._message_log:
                # remove html tags for txt
                plain = self._strip_html(m["content_html"])
                f.write(f"[{m['time']}] {m['label']}: {plain}\n\n")

    def _export_html(self, filepath: str):
        dir_attr = "rtl" if self.ui_lang == "fa" else "ltr"
        align = "right" if self.ui_lang == "fa" else "left"

        parts = [
            "<!doctype html><html><head><meta charset='utf-8'>",
            f"<title>{html.escape(self.windowTitle())}</title>",
            "<style>body{font-family:Segoe UI,Arial;background:#F5F7FA;padding:20px}"
            ".c{max-width:900px;margin:auto;background:#fff;border-radius:12px;padding:20px}"
            ".m{margin-bottom:14px}.h{font-weight:700}.t{color:#90A4AE;font-size:11px}</style>",
            "</head>",
            f"<body dir='{dir_attr}'><div class='c'>",
            f"<h2 style='text-align:{align}'>{html.escape(self.windowTitle())}</h2>",
        ]
        for m in self._message_log:
            sender = html.escape(m["label"])
            time_ = html.escape(m["time"])
            parts.append(
                f"<div class='m' style='text-align:{align}'>"
                f"<div class='h'>{sender} <span class='t'>[{time_}]</span></div>"
                f"<div>{m['content_html']}</div>"
                f"</div>"
            )
        parts.append("</div></body></html>")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("".join(parts))

    @staticmethod
    def _strip_html(raw_html: str) -> str:
        # minimal tag stripper
        text = re_sub(r"<br\s*/?>", "\n", raw_html)
        text = re_sub(r"<[^>]+>", "", text)
        return html.unescape(text).strip()

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(1500)
        super().closeEvent(event)


# local helper (avoid importing re globally just for one function)
def re_sub(pattern: str, repl: str, text: str) -> str:
    import re
    return re.sub(pattern, repl, text, flags=re.IGNORECASE)