import queue
import threading
from collections.abc import Callable

from djitellopy import Tello

from imageProcessing import main as run_gesture_recognition


MOVEMENT_DISTANCE_CM = 20


def main() -> None:
    tello = Tello()
    connected = False
    airborne = False
    stream_started = False
    follow_enabled = False
    target_palm_width = None
    command_queue: queue.Queue[tuple[str, Callable[[], None]]] = queue.Queue(maxsize=1)

    def handle_gesture(gesture: str) -> None:
        nonlocal airborne, follow_enabled, target_palm_width


        if not airborne:
            return
        if follow_enabled and gesture != "follow":
            follow_enabled = False
            target_palm_width = None
            tello.send_rc_control(0, 0, 0, 0)

        movement_commands = {
            "move_left": tello.move_left,
            "move_right": tello.move_right,
            "move_up": tello.move_up,
            "move_down": tello.move_down,
            "move_forward": tello.move_forward,
            "move_backward": tello.move_back,
            }

        if gesture == "land":
            print("Landing gesture recognized. Landing the drone.")
            try:
                command_queue.put_nowait(("land", tello.land))
            except queue.Full:
                print("Landing command is already queued.")
            airborne = False
        elif gesture == "standby":
            print("Standby gesture recognized; holding position.")
        elif gesture == "follow":
            follow_enabled = True
            target_palm_width = None
            print("Follow enabled. Hold your palm facing the camera.")
        elif gesture in movement_commands:
            print(f"Recognized {gesture}; moving {MOVEMENT_DISTANCE_CM} cm.")
            command = movement_commands[gesture]
            try:
                command_queue.put_nowait(
                    (gesture, lambda command=command: command(MOVEMENT_DISTANCE_CM))
                )
            except queue.Full:
                print("Skipping movement; the previous command is still queued.")

    def update_follow(hand):
        nonlocal target_palm_width

        if not airborne or not follow_enabled:
            return

        if hand is None:
            tello.send_rc_control(0, 0, 0, 0)
            return

        # Index and pinky knuckles mark opposite sides of the palm.
        index = hand[5]
        pinky = hand[17]
        center_x = (index.x + pinky.x) / 2
        palm_width = ((index.x - pinky.x)**2 + (index.y - pinky.y)**2)**0.5

        if palm_width < 0.01:
            tello.send_rc_control(0, 0, 0, 0)
            return

        if target_palm_width is None:
            target_palm_width = palm_width

        # imageProcessing.py mirrors the frame with cv2.flip(frame, 1).
        error_x = 0.5 - center_x
        yaw = 0
        if abs(error_x) > 0.08:
            yaw = int(max(-20, min(20, 60 * error_x)))

        # Smaller palm: move forward. Larger palm: move back.
        ratio = palm_width / target_palm_width
        forward = 0
        if ratio < 0.85:
            forward = 10
        elif ratio > 1.15:
            forward = -10

        tello.send_rc_control(0, forward, 0, yaw)

    try:
        print("Connecting to the Tello...")
        try:
            tello.connect()
        except OSError as error:
            raise RuntimeError(
                "Could not reach the Tello at 192.168.10.1. "
                "Connect this computer to the Tello's Wi-Fi network, "
                "disable VPNs or other active network routes, and try again."
            ) from error
        connected = True

        battery = tello.get_battery()
        print(f"Connected to the Tello. Battery: {battery}%")
        print("Starting the Tello video stream...")
        tello.set_video_fps(Tello.FPS_15)
        tello.streamon()
        stream_started = True
        frame_reader = tello.get_frame_read()

        print("Taking off...")
        tello.takeoff()
        airborne = True
        command_stop = threading.Event()

        def run_commands() -> None:
            while not command_stop.is_set() or not command_queue.empty():
                try:
                    _, command = command_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    command()
                except Exception as error:
                    print(f"Tello command failed: {error}")
                finally:
                    command_queue.task_done()

        command_thread = threading.Thread(target=run_commands, daemon=True)
        command_thread.start()

        print(
            "Gesture control is active. Each movement gesture moves the drone "
            f"{MOVEMENT_DISTANCE_CM} cm."
        )
        print("Press Q in the video window to land and stop.")

        run_gesture_recognition(
            on_gesture=handle_gesture,
            frame_provider=lambda: frame_reader.frame,
            on_hand=update_follow,
        )
    finally:
        try:
            if "command_stop" in locals():
                command_stop.set()
                if "command_thread" in locals():
                    command_thread.join(timeout=2)
            if airborne:
                print("Landing the drone before shutdown.")
                tello.land()
        finally:
            try:
                if stream_started:
                    tello.streamoff()
            finally:
                tello.end()
        if connected:
            print("Disconnected from the Tello.")


if __name__ == "__main__":
    main()
