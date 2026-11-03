import sys
import PySide6.QtCore as QtCore
from PySide6.QtCore import QTimer
from djitellopy import Tello
from PySide6.QtCore import QTimer as qtt
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QFormLayout)

class TelemetryWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Tello Telemetry")
        self.resize(400, 450)

        self.gesture_enabled = False

        # Labels whose values we will update later
        self.battery_label = QLabel("-- %")
        self.height_label = QLabel("-- cm")
        self.roll_label = QLabel("-- °")
        self.pitch_label = QLabel("-- °")
        self.yaw_label = QLabel("-- °")
        self.acceleration_label = QLabel("-- / -- / --")
        self.signal_label = QLabel("--")

        # Arrange telemetry as rows
        telemetry_layout = QFormLayout()
        telemetry_layout.addRow("Battery:", self.battery_label)
        telemetry_layout.addRow("Height:", self.height_label)
        telemetry_layout.addRow("Roll:", self.roll_label)
        telemetry_layout.addRow("Pitch:", self.pitch_label)
        telemetry_layout.addRow("Yaw:", self.yaw_label)
        telemetry_layout.addRow(
            "Acceleration X / Y / Z:",
            self.acceleration_label,
        )
        telemetry_layout.addRow("Wi-Fi SNR:", self.signal_label)

        # Control-mode button
        self.mode_label = QLabel("Selected mode: Manual")
        self.mode_button = QPushButton("Enable gesture control")
        self.mode_button.clicked.connect(self.toggle_control_mode)

        # Main window layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel("Drone telemetry"))
        main_layout.addLayout(telemetry_layout)
        main_layout.addWidget(self.mode_label)
        main_layout.addWidget(self.mode_button)
        main_layout.addWidget(
            QLabel("Interface preview — drone control is not connected.")
        )

        self.setLayout(main_layout)

        # Call update_telemetry every 100 ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_telemetry)
        self.timer.start(100)

    def toggle_control_mode(self):
        self.gesture_enabled = not self.gesture_enabled

        if self.gesture_enabled:
            self.mode_label.setText("Selected mode: Gesture")
            self.mode_button.setText("Switch to manual control")
        else:
            self.mode_label.setText("Selected mode: Manual")
            self.mode_button.setText("Enable gesture control")

    def update_telemetry(self):
        # Later: read cached drone telemetry and update the labels.
        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = TelemetryWindow()
    window.show()

    sys.exit(app.exec())
