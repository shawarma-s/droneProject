from djitellopy import Tello

from imageProcessing import main as run_gesture_recognition


def report_run_command(gesture: str) -> None:
    if gesture == "standby":
        print("Recognized standby gesture; Drone is on standby, awaiting commands.")
    elif gesture == "follow":
        print("Recognized follow gesture; follow control is not enabled.")
    else:
        print(f"Recognized command: {gesture} [dry run; no command sent]")


def main() -> None:
    tello = Tello()
    connected = False
    stream_started = False
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

        print(
            "Using the Tello camera in gesture dry-run mode. "
            "The drone will remain landed and no flight commands will be sent."
        )
        print("Press Q in the video window to stop.")

        run_gesture_recognition(
            on_gesture=report_run_command,
            frame_provider=lambda: frame_reader.frame,
        )
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
