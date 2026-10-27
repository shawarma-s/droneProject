from djitellopy import Tello

from imageProcessing import main as run_gesture_recognition


def report_dry_run_command(gesture: str) -> None:
    if gesture == "standby":
        print("Recognized standby gesture; no drone command sent.")
    elif gesture == "follow":
        print("Recognized follow gesture; follow control is not implemented.")
    else:
        print(f"Recognized command: {gesture} [DRY RUN: not sent to drone]")


def main() -> None:
    tello = Tello()
    stream_started = False
    try:
        print("Connecting to the Tello...")
        tello.connect()

        battery = tello.get_battery()
        print(f"Connected to the Tello. Battery: {battery}%")
        print("Starting the Tello video stream...")
        tello.streamon()
        stream_started = True
        frame_reader = tello.get_frame_read()

        print(
            "Using the Tello camera in gesture dry-run mode. "
            "No takeoff or movement commands will be sent."
        )
        run_gesture_recognition(
            on_gesture=report_dry_run_command,
            frame_provider=lambda: frame_reader.frame,
        )
    finally:
        try:
            if stream_started:
                tello.streamoff()
        finally:
            tello.end()
        print("Disconnected from the Tello.")


if __name__ == "__main__":
    main()
