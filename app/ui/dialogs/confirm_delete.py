from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout

from ...core.formatting import format_size
from ...core.models import DiskItem


class ConfirmDeleteDialog(QDialog):
    def __init__(self, item: DiskItem, permanent: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.permanent = permanent
        self.setWindowTitle("Delete Permanently" if permanent else "Move to Trash")
        folder_warning = "\n\nThis is a folder. All scanned children inside it will be affected." if item.is_folder else ""
        action = "Permanently delete" if permanent else "Move this item to the system Trash/Recycle Bin"
        restore_note = (
            "This cannot be restored from Trash. Make sure you have backups."
            if permanent
            else "You can restore this from the system Trash/Recycle Bin."
        )
        message = (
            f"{action}?\n\n"
            f"Name: {item.name}\n"
            f"Path: {item.absolute_path}\n"
            f"Size: {format_size(item.size)}"
            f"{folder_warning}\n\n"
            f"Total space to reclaim: {format_size(item.size)}\n"
            f"{restore_note}"
        )
        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.confirm_input: QLineEdit | None = None
        if permanent:
            warning = QLabel("Type DELETE to enable permanent deletion.")
            warning.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(warning)
            self.confirm_input = QLineEdit()
            self.confirm_input.setPlaceholderText("DELETE")
            layout.addWidget(self.confirm_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Delete Permanently" if permanent else "Move to Trash")
        if permanent and self.confirm_input:
            ok_button.setEnabled(False)
            self.confirm_input.textChanged.connect(lambda text: ok_button.setEnabled(text == "DELETE"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
