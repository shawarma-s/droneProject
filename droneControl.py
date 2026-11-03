from djitellopy import Tello

from imageProcessing import main as run_gesture_recognition


MOVEMENT_DISTANCE_CM = 10


def main() -> None:
    tello = Tello()
    connected = False
    airborne = False
    stream_started = False

    def handle_gesture(gesture: str) -> None:
        nonlocal airborne

        if not airborne:
            return

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
            tello.land()
            airborne = False
        elif gesture == "standby":
            print("Standby gesture recognized; holding position.")
        elif gesture == "follow":
            print("Follow gesture recognized; follow mode is not enabled.")
        elif gesture in movement_commands:
            print(f"Recognized {gesture}; moving {MOVEMENT_DISTANCE_CM} cm.")
            movement_commands[gesture](MOVEMENT_DISTANCE_CM)

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
        tello.streamon()
        stream_started = True
        frame_reader = tello.get_frame_read()

        print("Taking off...")
        tello.takeoff()
        airborne = True
        print(
            "Gesture control is active. Each movement gesture moves the drone "
            f"{MOVEMENT_DISTANCE_CM} cm."
        )
        print("Press Q in the video window to land and stop.")

        run_gesture_recognition(
            on_gesture=handle_gesture,
            frame_provider=lambda: frame_reader.frame,
        )
    finally:
        try:
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
