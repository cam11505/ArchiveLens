from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout


class PasswordDialog(QDialog):
    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("內容來源密碼")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(message))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password)
        self.show_password = QCheckBox("顯示密碼")
        self.show_password.toggled.connect(
            lambda checked: self.password.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        layout.addWidget(self.show_password)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
