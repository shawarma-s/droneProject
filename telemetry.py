from __future__ import annotations

import queue
import sys
import threading
from collections.abc import Callable

from djitellopy import Tello
from PySide6 import QtCore, QtGui, QtWidgets
from imageProcessing import main as run_gesture_recognition


MOVEMENT_DISTANCE_CM = 20


class DroneIndicator(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.yaw = 0.0
        self.setMinimumSize(260, 180)

    def set_yaw(self, yaw: float) -> None:
        self.yaw = yaw
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor("#20242b"))
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-self.yaw)

        painter.setPen(QtGui.QPen(QtGui.QColor("#6ee7b7"), 3))
        painter.setBrush(QtGui.QColor("#14532d"))
        painter.drawRoundedRect(-70, -35, 140, 70, 18, 18)
        painter.setBrush(QtGui.QColor("#fbbf24"))
        painter.drawEllipse(-12, -12, 24, 24)
        painter.setPen(QtGui.QPen(QtGui.QColor("#60a5fa"), 3))
        painter.drawLine(0, -35, 0, -75)
        painter.drawLine(-12, -63, 0, -75)
        painter.drawLine(12, -63, 0, -75)


class TelemetryWindow(QtWidgets.QWidget):
    command_error = QtCore.Signal(str)

    def __init__(
        self,
        tello: Tello,
        command_callback: Callable[[str], None] | None = None,
        key_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self.tello = tello
        self.command_callback = command_callback
        self.key_callback = key_callback
        self.gesture_enabled = True
        self.command_queue: queue.Queue[tuple[str, Callable[[], None]]] = queue.Queue(
            maxsize=1
        )
        self.manual_keys: set[int] = set()
        self.manual_timer = QtCore.QTimer(self)
        self.manual_timer.timeout.connect(self._send_manual_control)
        self.manual_timer.start(100)
        self.command_stop = threading.Event()
        self.command_thread = threading.Thread(
            target=self._run_commands,
            daemon=True,
        )
        self.command_error.connect(self._show_command_error)
        self.command_thread.start()

        self.setWindowTitle("Tello Telemetry and Control")
        self.resize(440, 650)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self.labels = {
            "battery": QtWidgets.QLabel("-- %"),
            "height": QtWidgets.QLabel("-- cm"),
            "distance": QtWidgets.QLabel("-- cm"),
            "pitch": QtWidgets.QLabel("-- deg"),
            "roll": QtWidgets.QLabel("-- deg"),
            "yaw": QtWidgets.QLabel("-- deg"),
            "acceleration": QtWidgets.QLabel("-- / -- / --"),
            "signal": QtWidgets.QLabel("--"),
            "mode": QtWidgets.QLabel("Gesture control enabled"),
        }

        telemetry_layout = QtWidgets.QFormLayout()
        telemetry_layout.addRow("Battery:", self.labels["battery"])
        telemetry_layout.addRow("Height:", self.labels["height"])
        telemetry_layout.addRow("Distance:", self.labels["distance"])
        telemetry_layout.addRow("Pitch:", self.labels["pitch"])
        telemetry_layout.addRow("Roll:", self.labels["roll"])
        telemetry_layout.addRow("Yaw:", self.labels["yaw"])
        telemetry_layout.addRow("Acceleration X / Y / Z:", self.labels["acceleration"])
        telemetry_layout.addRow("Wi-Fi signal:", self.labels["signal"])

        self.mode_button = QtWidgets.QPushButton("Disable gesture control")
        self.mode_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.mode_button.clicked.connect(self.toggle_control_mode)
        self.indicator = DroneIndicator()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Drone telemetry"))
        layout.addLayout(telemetry_layout)
        layout.addWidget(self.indicator)
        layout.addWidget(self.labels["mode"])
        layout.addWidget(self.mode_button)
        layout.addWidget(
            QtWidgets.QLabel(
                "Manual controls: arrows = horizontal, ,/. = down/up, "
                "S or , = down; . = up; F = take off when landed"
            )
        )

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_telemetry)
        self.timer.start(100)
        self.camera_thread: threading.Thread | None = None

    def _run_commands(self) -> None:
        while not self.command_stop.is_set() or not self.command_queue.empty():
            try:
                _, command = self.command_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                command()
            except Exception as error:
                self.command_error.emit(f"Command failed: {error}")
            finally:
                self.command_queue.task_done()

    def _submit(self, name: str, command: Callable[[], None]) -> None:
        try:
            self.command_queue.put_nowait((name, command))
        except queue.Full:
            self.labels["mode"].setText("Command skipped: another command is pending")

    def _show_command_error(self, message: str) -> None:
        self.labels["mode"].setText(message)

    def _send_manual_control(self) -> None:
        if self.gesture_enabled:
            return

        left_right = 0
        forward = 0
        up_down = 0
        if QtCore.Qt.Key.Key_Left in self.manual_keys:
            left_right -= 20
        if QtCore.Qt.Key.Key_Right in self.manual_keys:
            left_right += 20
        if QtCore.Qt.Key.Key_Up in self.manual_keys:
            forward += 20
        if QtCore.Qt.Key.Key_Down in self.manual_keys:
            forward -= 20
        if (
            QtCore.Qt.Key.Key_Comma in self.manual_keys
            or QtCore.Qt.Key.Key_S in self.manual_keys
        ):
            up_down -= 20
        if QtCore.Qt.Key.Key_Period in self.manual_keys:
            up_down += 20

        self.tello.send_rc_control(left_right, forward, up_down, 0)

    def toggle_control_mode(self) -> None:
        self.gesture_enabled = not self.gesture_enabled
        if self.gesture_enabled:
            self.manual_keys.clear()
            self.tello.send_rc_control(0, 0, 0, 0)
            self.labels["mode"].setText("Gesture control enabled")
            self.mode_button.setText("Disable gesture control")
        else:
            self.labels["mode"].setText("Manual control enabled")
            self.mode_button.setText("Enable gesture control")
            self.setFocus()

        if self.command_callback is not None:
            self.command_callback("gesture_enabled" if self.gesture_enabled else "manual")

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_F:
            if self.key_callback is not None:
                self.key_callback("f")
            event.accept()
            return

        if self.gesture_enabled:
            return

        manual_keys = {
            QtCore.Qt.Key.Key_Left,
            QtCore.Qt.Key.Key_Right,
            QtCore.Qt.Key.Key_Up,
            QtCore.Qt.Key.Key_Down,
            QtCore.Qt.Key.Key_Comma,
            QtCore.Qt.Key.Key_S,
            QtCore.Qt.Key.Key_Period,
        }
        if event.key() in manual_keys:
            self.manual_keys.add(event.key())
            self._send_manual_control()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() in self.manual_keys:
            self.manual_keys.discard(event.key())
            self._send_manual_control()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def update_telemetry(self) -> None:
        state = self.tello.get_current_state()
        self.labels["battery"].setText(f"{state.get('bat', '--')} %")
        self.labels["height"].setText(f"{state.get('h', '--')} cm")
        self.labels["distance"].setText(f"{state.get('tof', '--')} cm")

        pitch = state.get("pitch", "--")
        roll = state.get("roll", "--")
        yaw = state.get("yaw", "--")
        self.labels["pitch"].setText(f"{pitch} deg")
        self.labels["roll"].setText(f"{roll} deg")
        self.labels["yaw"].setText(f"{yaw} deg")
        self.indicator.set_yaw(float(yaw) if isinstance(yaw, (int, float)) else 0)

        acceleration = (
            state.get("agx", "--"),
            state.get("agy", "--"),
            state.get("agz", "--"),
        )
        self.labels["acceleration"].setText(" / ".join(map(str, acceleration)))
        self.labels["signal"].setText(f"{state.get('wifi', '--')} dBm")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.manual_timer.stop()
        self.manual_keys.clear()
        self.tello.send_rc_control(0, 0, 0, 0)
        self.command_stop.set()
        self.command_thread.join(timeout=2)
        event.accept()


def main() -> None:
    tello = Tello()
    stream_started = False
    airborne = False
    camera_thread: threading.Thread | None = None
    try:
        print("Connecting to the Tello...")
        tello.connect()
        print(f"Battery: {tello.get_battery()}%")
        tello.streamon()
        stream_started = True
        frame_reader = tello.get_frame_read()
        tello.takeoff()
        airborne = True

        app = QtWidgets.QApplication(sys.argv)
        window = TelemetryWindow(tello, key_callback=lambda key: handle_key(key))
        window.show()

        def submit(name: str, command: Callable[[], None]) -> None:
            window._submit(name, command)

        def handle_gesture(gesture: str) -> None:
            nonlocal airborne
            if not window.gesture_enabled or not airborne:
                return

            commands = {
                "move_left": tello.move_left,
                "move_right": tello.move_right,
                "move_up": tello.move_up,
                "move_down": tello.move_down,
                "move_forward": tello.move_forward,
                "move_backward": tello.move_back,
            }
            if gesture == "land":
                submit("land", tello.land)
                airborne = False
            elif gesture in commands:
                command = commands[gesture]
                submit(
                    gesture,
                    lambda command=command: command(MOVEMENT_DISTANCE_CM),
                )

        def handle_key(key: str) -> None:
            nonlocal airborne
            if key == "f" and not airborne:
                submit("takeoff", tello.takeoff)
                airborne = True

        def process_camera() -> None:
            run_gesture_recognition(
                on_gesture=handle_gesture,
                frame_provider=lambda: frame_reader.frame,
                on_key=handle_key,
                stop_event=camera_stop,
            )

        camera_stop = threading.Event()
        app.aboutToQuit.connect(camera_stop.set)
        camera_thread = threading.Thread(target=process_camera, daemon=True)
        camera_thread.start()
        sys.exit(app.exec())
    finally:
        if camera_thread is not None:
            camera_thread.join(timeout=2)
        if airborne:
            tello.land()
        if stream_started:
            tello.streamoff()
        tello.end()


if __name__ == "__main__":
    main()
