from __future__ import annotations

import queue
import sys
import threading
import time
from collections.abc import Callable

from djitellopy import Tello
from PySide6 import QtCore, QtGui, QtWidgets
from imageProcessing import main as run_gesture_recognition


MOVEMENT_DISTANCE_CM = 20
FOLLOW_DEAD_ZONE = 0.08
FOLLOW_MAX_VELOCITY = 20
FOLLOW_MAX_YAW = 30


class DroneIndicator(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.yaw = 0.0
        self.setMinimumSize(260, 210)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_yaw(self, yaw: float) -> None:
        self.yaw = yaw
        self.update()

    def reset(self) -> None:
        self.set_yaw(0.0)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor("#11112d"))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)
        painter.setPen(QtGui.QPen(QtGui.QColor("#28245c"), 1))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)
        painter.setPen(QtGui.QPen(QtGui.QColor("#252052"), 1))
        for x in range(24, self.width(), 32):
            painter.drawLine(x, 12, x, self.height() - 12)
        for y in range(20, self.height(), 32):
            painter.drawLine(12, y, self.width() - 12, y)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-self.yaw)

        painter.setPen(QtGui.QPen(QtGui.QColor("#ff3d81"), 3))
        painter.setBrush(QtGui.QColor("#241b55"))
        painter.drawRoundedRect(-72, -35, 144, 70, 18, 18)
        painter.setBrush(QtGui.QColor("#ff3d81"))
        painter.drawEllipse(-11, -11, 22, 22)
        painter.setPen(QtGui.QPen(QtGui.QColor("#7c4dff"), 4))
        painter.drawLine(0, -35, 0, -78)
        painter.drawLine(-13, -65, 0, -78)
        painter.drawLine(13, -65, 0, -78)


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
        application = QtWidgets.QApplication.instance()
        if application is not None:
            application.installEventFilter(self)
        self.command_stop = threading.Event()
        self.command_thread = threading.Thread(
            target=self._run_commands,
            daemon=True,
        )
        self.command_error.connect(self._show_command_error)
        self.command_thread.start()

        self.setWindowTitle("Tello Telemetry and Control")
        self.resize(760, 820)
        self.setMinimumSize(620, 680)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(
            """
            QWidget {
                color: #f3f1ff;
                font-family: "Avenir Next", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QMainWindow, QWidget#telemetryRoot {
                background: #080820;
            }
            QLabel#eyebrow {
                color: #9c8cff;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel#pageTitle {
                color: #ffffff;
                font-size: 26px;
                font-weight: 800;
            }
            QLabel#subtitle {
                color: #9692b7;
                font-size: 12px;
            }
            QFrame#card {
                background: #11112d;
                border: 1px solid #252052;
                border-radius: 16px;
            }
            QLabel#cardTitle {
                color: #ffffff;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#metricName {
                color: #918cae;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#metricValue {
                color: #ffffff;
                font-size: 20px;
                font-weight: 800;
            }
            QLabel#metricAccent {
                color: #ff3d81;
                font-size: 20px;
                font-weight: 800;
            }
            QLabel#status {
                background: #182b36;
                border: 1px solid #2ee6a6;
                border-radius: 10px;
                color: #5ff0bd;
                font-size: 12px;
                font-weight: 700;
                padding: 8px 12px;
            }
            QPushButton {
                background: #6d3df5;
                border: 1px solid #8e6cff;
                border-radius: 10px;
                color: white;
                font-weight: 700;
                padding: 11px 16px;
            }
            QPushButton:hover {
                background: #8057ff;
            }
            QPushButton:pressed {
                background: #572bcf;
            }
            QLabel#hint {
                color: #8985a7;
                font-size: 11px;
            }
            """
        )
        self.setObjectName("telemetryRoot")

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

        for name, label in self.labels.items():
            if name != "mode":
                label.setObjectName("metricValue")

        self.mode_button = QtWidgets.QPushButton("Disable gesture control")
        self.mode_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.mode_button.clicked.connect(self.toggle_control_mode)
        self.indicator = DroneIndicator()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(16)

        eyebrow = QtWidgets.QLabel("TELLO / FLIGHT SYSTEM")
        eyebrow.setObjectName("eyebrow")
        title = QtWidgets.QLabel("Drone telemetry")
        title.setObjectName("pageTitle")
        subtitle = QtWidgets.QLabel("Live flight data and control center")
        subtitle.setObjectName("subtitle")
        header = QtWidgets.QVBoxLayout()
        header.setSpacing(3)
        header.addWidget(eyebrow)
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        metrics_card = QtWidgets.QFrame()
        metrics_card.setObjectName("card")
        metrics_layout = QtWidgets.QGridLayout(metrics_card)
        metrics_layout.setContentsMargins(18, 16, 18, 16)
        metrics_layout.setHorizontalSpacing(28)
        metrics_layout.setVerticalSpacing(16)
        metric_specs = [
            ("battery", "BATTERY", 0, 0),
            ("height", "ALTITUDE", 0, 1),
            ("distance", "DISTANCE", 0, 2),
            ("pitch", "PITCH", 1, 0),
            ("roll", "ROLL", 1, 1),
            ("yaw", "YAW", 1, 2),
            ("acceleration", "ACCELERATION X / Y / Z", 2, 0),
            ("signal", "WI-FI SIGNAL", 2, 2),
        ]
        for key, name, row, column in metric_specs:
            metric = QtWidgets.QVBoxLayout()
            metric.setSpacing(3)
            metric_name = QtWidgets.QLabel(name)
            metric_name.setObjectName("metricName")
            metric.addWidget(metric_name)
            metric.addWidget(self.labels[key])
            metrics_layout.addLayout(metric, row, column, 1, 2 if key == "acceleration" else 1)
        layout.addWidget(metrics_card)

        indicator_card = QtWidgets.QFrame()
        indicator_card.setObjectName("card")
        indicator_layout = QtWidgets.QVBoxLayout(indicator_card)
        indicator_layout.setContentsMargins(18, 14, 18, 14)
        indicator_title = QtWidgets.QLabel("AIRCRAFT ORIENTATION")
        indicator_title.setObjectName("cardTitle")
        indicator_layout.addWidget(indicator_title)
        indicator_layout.addWidget(self.indicator)
        layout.addWidget(indicator_card, 1)

        controls_card = QtWidgets.QFrame()
        controls_card.setObjectName("card")
        controls_layout = QtWidgets.QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(18, 14, 18, 14)
        controls_layout.setSpacing(10)
        self.labels["mode"].setObjectName("status")
        controls_layout.addWidget(self.labels["mode"])
        controls_layout.addWidget(self.mode_button)
        hint = QtWidgets.QLabel(
            "Manual: arrows move  •  S or , descend  •  . ascend  •  F take off  •  L land  •  P flip"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        controls_layout.addWidget(hint)
        layout.addWidget(controls_card)

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

    def _submit(self, name: str, command: Callable[[], None]) -> bool:
        try:
            self.command_queue.put_nowait((name, command))
            return True
        except queue.Full:
            self.labels["mode"].setText("Command skipped: another command is pending")
            return False

    def _clear_pending_commands(self) -> None:
        while True:
            try:
                self.command_queue.get_nowait()
            except queue.Empty:
                return
            else:
                self.command_queue.task_done()

    def _show_command_error(self, message: str) -> None:
        self.labels["mode"].setText(message)

    def _send_rc_control(
        self,
        left_right: int,
        forward: int,
        up_down: int,
        yaw: int,
    ) -> None:
        try:
            self.tello.send_rc_control(left_right, forward, up_down, yaw)
        except Exception as error:
            self.command_error.emit(f"RC command failed: {error}")

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

        self._send_rc_control(left_right, forward, up_down, 0)

    def _manual_key_codes(self) -> set[int]:
        return {
            QtCore.Qt.Key.Key_Left,
            QtCore.Qt.Key.Key_Right,
            QtCore.Qt.Key.Key_Up,
            QtCore.Qt.Key.Key_Down,
            QtCore.Qt.Key.Key_Comma,
            QtCore.Qt.Key.Key_S,
            QtCore.Qt.Key.Key_Period,
        }

    def _handle_key_press(self, key: int, auto_repeat: bool = False) -> bool:
        if key == QtCore.Qt.Key.Key_F:
            if not auto_repeat and self.key_callback is not None:
                self.key_callback("f")
            return True

        if key == QtCore.Qt.Key.Key_L:
            if not auto_repeat and not self.gesture_enabled and self.key_callback is not None:
                self.key_callback("l")
            return True

        if key == QtCore.Qt.Key.Key_P:
            if not auto_repeat and not self.gesture_enabled and self.key_callback is not None:
                self.key_callback("p")
            return True

        if self.gesture_enabled or key not in self._manual_key_codes():
            return False

        self.manual_keys.add(key)
        self._send_manual_control()
        return True

    def _handle_key_release(self, key: int) -> bool:
        if key in self.manual_keys:
            self.manual_keys.discard(key)
            self._send_manual_control()
            return True
        return False

    def eventFilter(
        self,
        watched: QtCore.QObject,
        event: QtCore.QEvent,
    ) -> bool:
        if not self.isActiveWindow():
            return super().eventFilter(watched, event)
        if event.type() == QtCore.QEvent.Type.KeyPress:
            key_event = event
            return self._handle_key_press(
                key_event.key(),
                key_event.isAutoRepeat(),
            )
        if event.type() == QtCore.QEvent.Type.KeyRelease:
            return self._handle_key_release(event.key())
        return super().eventFilter(watched, event)

    def toggle_control_mode(self) -> None:
        self.gesture_enabled = not self.gesture_enabled
        if self.gesture_enabled:
            self.manual_keys.clear()
            self._send_rc_control(0, 0, 0, 0)
            self.labels["mode"].setText("Gesture control enabled")
            self.mode_button.setText("Disable gesture control")
        else:
            self.labels["mode"].setText("Manual control enabled")
            self.mode_button.setText("Enable gesture control")
            self.setFocus()

        if self.command_callback is not None:
            self.command_callback("gesture_enabled" if self.gesture_enabled else "manual")

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if self._handle_key_press(event.key(), event.isAutoRepeat()):
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        if self._handle_key_release(event.key()):
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
        application = QtWidgets.QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        self.manual_timer.stop()
        self.manual_keys.clear()
        self._send_rc_control(0, 0, 0, 0)
        self.command_stop.set()
        self.command_thread.join(timeout=2)
        event.accept()


def main() -> None:
    tello = Tello()
    stream_started = False
    airborne = False
    camera_thread: threading.Thread | None = None
    window: TelemetryWindow | None = None
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
        window.indicator.reset()
        window.show()

        follow_enabled = False
        target_palm_width: float | None = None
        takeoff_pending = False
        landing_pending = False
        last_takeoff_time = 0.0

        def handle_control_error(message: str) -> None:
            nonlocal airborne, follow_enabled, target_palm_width
            if message.startswith("RC command failed:"):
                airborne = False
                follow_enabled = False
                target_palm_width = None
                window.labels["mode"].setText(
                    "RC control lost; press F to retry takeoff"
                )

        window.command_error.connect(handle_control_error)

        def submit(name: str, command: Callable[[], None]) -> bool:
            return window._submit(name, command)

        def handle_gesture(gesture: str) -> None:
            nonlocal airborne, follow_enabled, target_palm_width
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
            if follow_enabled and gesture != "follow":
                follow_enabled = False
                target_palm_width = None
                window._send_rc_control(0, 0, 0, 0)
                window.labels["mode"].setText("Gesture control enabled")
            if gesture == "follow":
                follow_enabled = True
                target_palm_width = None
                window.labels["mode"].setText(
                    "Follow control enabled"
                )
                print("Follow enabled. Hold your palm facing the camera.")
            elif gesture == "standby":
                window.labels["mode"].setText("Standby: holding position")
            elif gesture in commands:
                command = commands[gesture]
                submit(
                    gesture,
                    lambda command=command: command(MOVEMENT_DISTANCE_CM),
                )

        def update_follow(hand) -> None:
            nonlocal target_palm_width
            if not window.gesture_enabled or not airborne or not follow_enabled:
                return
            if hand is None:
                tello.send_rc_control(0, 0, 0, 0)
                return

            index = hand[5]
            pinky = hand[17]
            center_x = (index.x + pinky.x) / 2
            palm_width = ((index.x - pinky.x) ** 2 + (index.y - pinky.y) ** 2) ** 0.5
            if palm_width < 0.01:
                tello.send_rc_control(0, 0, 0, 0)
                return
            if target_palm_width is None:
                target_palm_width = palm_width

            error_x = center_x - 0.5
            error_y = (index.y + pinky.y) / 2 - 0.5
            left_right = (
                int(max(-FOLLOW_MAX_VELOCITY, min(FOLLOW_MAX_VELOCITY, -60 * error_x)))
                if abs(error_x) > FOLLOW_DEAD_ZONE
                else 0
            )
            up_down = (
                int(max(-FOLLOW_MAX_VELOCITY, min(FOLLOW_MAX_VELOCITY, -60 * error_y)))
                if abs(error_y) > FOLLOW_DEAD_ZONE
                else 0
            )
            ratio = palm_width / target_palm_width
            forward = (
                FOLLOW_MAX_VELOCITY
                if ratio < 0.85
                else -FOLLOW_MAX_VELOCITY
                if ratio > 1.15
                else 0
            )
            yaw = (
                int(max(-FOLLOW_MAX_YAW, min(FOLLOW_MAX_YAW, -60 * error_x)))
                if abs(error_x) > FOLLOW_DEAD_ZONE
                else 0
            )
            tello.send_rc_control(left_right, forward, up_down, yaw)

        def handle_key(key: str) -> None:
            nonlocal airborne, follow_enabled, target_palm_width
            nonlocal takeoff_pending, landing_pending
            if (
                key == "f"
                and not airborne
                and not takeoff_pending
                and not landing_pending
            ):
                window._clear_pending_commands()

                def takeoff() -> None:
                    nonlocal airborne, takeoff_pending
                    nonlocal last_takeoff_time
                    try:
                        tello.takeoff()
                    except Exception:
                        takeoff_pending = False
                        raise
                    airborne = True
                    takeoff_pending = False
                    last_takeoff_time = time.monotonic()
                    window.labels["mode"].setText("Takeoff complete")

                takeoff_pending = True
                if not submit("takeoff", takeoff):
                    takeoff_pending = False
                else:
                    follow_enabled = False
                    target_palm_width = None
            elif key == "l" and not window.gesture_enabled and airborne:
                follow_enabled = False
                target_palm_width = None
                tello.send_rc_control(0, 0, 0, 0)
                window._clear_pending_commands()

                def land() -> None:
                    nonlocal landing_pending
                    try:
                        tello.land()
                    finally:
                        landing_pending = False

                landing_pending = True
                if not submit("land", land):
                    landing_pending = False
                window.labels["mode"].setText("Landing requested")
                airborne = False
            elif key == "p" and not window.gesture_enabled and airborne:
                def flip() -> None:
                    time_since_takeoff = time.monotonic() - last_takeoff_time
                    if time_since_takeoff < 2:
                        time.sleep(2 - time_since_takeoff)
                    tello.flip_forward()

                if submit("flip", flip):
                    window.labels["mode"].setText("Forward flip requested")

        def process_camera() -> None:
            run_gesture_recognition(
                on_gesture=handle_gesture,
                frame_provider=lambda: frame_reader.frame,
                on_hand=update_follow,
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
        if window is not None:
            window.indicator.reset()
        if stream_started:
            tello.streamoff()
        tello.end()


if __name__ == "__main__":
    main()
