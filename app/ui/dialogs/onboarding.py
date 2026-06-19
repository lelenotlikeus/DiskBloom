from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from ..theme import ThemeManager


COPY = {
    "en": [
        ("Welcome to DiskBloom", "Choose a folder, scan it, then use the tree and inspector to understand where space is going."),
        ("Scan safely", "DiskBloom skips symlinks, reports inaccessible folders, and keeps scans read-only."),
        ("Clean with confidence", "Move to Trash is the default cleanup action. Permanent deletion stays hidden in Advanced."),
        ("Pick the right engine", "DiskBloom can use Standard, Parallel, or optional indexed scanning depending on the user's system. You can change this in Settings."),
    ],
    "it": [
        ("Benvenuto in DiskBloom", "Scegli una cartella, scansiona e usa albero e pannello dettagli per capire dove va lo spazio."),
        ("Scansione sicura", "DiskBloom salta i symlink, segnala le cartelle non accessibili e non modifica i file durante la scansione."),
        ("Pulizia controllata", "Sposta nel Cestino e l'azione predefinita. L'eliminazione permanente resta nascosta in Avanzate."),
        ("Scegli il motore giusto", "DiskBloom puo usare Standard, Parallel o scansione indicizzata opzionale in base al sistema dell'utente. Puoi cambiarlo in Impostazioni."),
    ],
}


class OnboardingDialog(QDialog):
    choose_folder_requested = Signal()

    def __init__(self, language: str = "en", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("DiskBloom")
        self.setMinimumWidth(560)
        self._steps = COPY.get(language, COPY["en"])
        self._index = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        header = QLabel()
        header.setObjectName("brandIcon")
        header.setFixedSize(42, 42)
        header.setPixmap(QIcon(ThemeManager.asset_path("logo.svg")).pixmap(42, 42))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.stack = QStackedWidget()
        for title, body in self._steps:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(12, 8, 12, 8)
            page_layout.setSpacing(10)
            title_label = QLabel(title)
            title_label.setObjectName("emptyTitle")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            body_label = QLabel(body)
            body_label.setObjectName("emptyBody")
            body_label.setWordWrap(True)
            body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page_layout.addWidget(title_label)
            page_layout.addWidget(body_label)
            self.stack.addWidget(page)
        layout.addWidget(self.stack)

        self.progress = QLabel()
        self.progress.setObjectName("muted")
        self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress)

        button_row = QHBoxLayout()
        self.back_button = QPushButton("Back" if language == "en" else "Indietro")
        self.next_button = QPushButton("Next" if language == "en" else "Avanti")
        self.next_button.setObjectName("primary")
        self.skip_button = QPushButton("Skip" if language == "en" else "Salta")
        self.choose_button = QPushButton("Choose Folder" if language == "en" else "Scegli cartella")
        self.choose_button.setObjectName("primary")
        self.choose_button.setVisible(False)
        button_row.addWidget(self.skip_button)
        button_row.addStretch(1)
        button_row.addWidget(self.back_button)
        button_row.addWidget(self.next_button)
        button_row.addWidget(self.choose_button)
        layout.addLayout(button_row)

        self.back_button.clicked.connect(self._back)
        self.next_button.clicked.connect(self._next)
        self.skip_button.clicked.connect(self.accept)
        self.choose_button.clicked.connect(self._choose_folder)
        self._sync()

    def _sync(self) -> None:
        self.stack.setCurrentIndex(self._index)
        self.back_button.setEnabled(self._index > 0)
        final = self._index == len(self._steps) - 1
        self.next_button.setVisible(not final)
        self.choose_button.setVisible(final)
        self.progress.setText(f"{self._index + 1} / {len(self._steps)}")

    def _back(self) -> None:
        self._index = max(0, self._index - 1)
        self._sync()

    def _next(self) -> None:
        self._index = min(len(self._steps) - 1, self._index + 1)
        self._sync()

    def _choose_folder(self) -> None:
        self.choose_folder_requested.emit()
        self.accept()
