from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ...core.scanners.everything_scanner import is_available as everything_available


@dataclass(slots=True)
class SettingsValues:
    language: str
    theme: str
    scan_engine: str
    everything_cli_path: str
    parallel_workers: int
    prefer_indexed_scan: bool
    show_onboarding_next_start: bool


class SettingsDialog(QDialog):
    def __init__(self, values: SettingsValues, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self.values = values

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.language = QComboBox()
        self.language.addItem("English", "en")
        self.language.addItem("Italiano", "it")
        self.language.setCurrentIndex(max(0, self.language.findData(values.language)))
        form.addRow("Language", self.language)

        self.theme = QComboBox()
        self.theme.addItem("Dark", "dark")
        self.theme.addItem("Light", "light")
        self.theme.setCurrentIndex(max(0, self.theme.findData(values.theme)))
        form.addRow("Theme", self.theme)

        self.engine = QComboBox()
        self.engine.addItem("Auto", "auto")
        self.engine.addItem("Standard", "standard")
        self.engine.addItem("Parallel", "parallel")
        self.engine.addItem("Everything", "everything")
        self.engine.setCurrentIndex(max(0, self.engine.findData(values.scan_engine)))
        form.addRow("Scan engine", self.engine)

        self.everything_path = QLineEdit(values.everything_cli_path)
        self.everything_path.setPlaceholderText(r"Optional path to es.exe")
        form.addRow("Everything CLI", self.everything_path)

        self.workers = QSpinBox()
        self.workers.setRange(0, 32)
        self.workers.setValue(values.parallel_workers)
        self.workers.setSpecialValueText("Auto")
        form.addRow("Parallel workers", self.workers)

        self.prefer_indexed = QCheckBox("Prefer indexed scan in Auto mode")
        self.prefer_indexed.setChecked(values.prefer_indexed_scan)
        form.addRow("", self.prefer_indexed)

        self.show_onboarding = QCheckBox("Show guided tutorial on next start")
        self.show_onboarding.setChecked(values.show_onboarding_next_start)
        form.addRow("", self.show_onboarding)

        layout.addLayout(form)

        self.availability = QLabel()
        self.availability.setObjectName("muted")
        self.availability.setWordWrap(True)
        layout.addWidget(self.availability)

        refresh = QPushButton("Refresh availability")
        refresh.clicked.connect(self._refresh_availability)
        layout.addWidget(refresh)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_availability()

    def current_values(self) -> SettingsValues:
        return SettingsValues(
            language=str(self.language.currentData()),
            theme=str(self.theme.currentData()),
            scan_engine=str(self.engine.currentData()),
            everything_cli_path=self.everything_path.text().strip(),
            parallel_workers=int(self.workers.value()),
            prefer_indexed_scan=self.prefer_indexed.isChecked(),
            show_onboarding_next_start=self.show_onboarding.isChecked(),
        )

    def _refresh_availability(self) -> None:
        available, reason, _ = everything_available(self.everything_path.text().strip())
        self.availability.setText(
            f"Everything: {'Available' if available else 'Not installed'} - {reason}\n"
            "Parallel: Available\n"
            "Windows Fast / MFT: Not implemented yet"
        )
