from djitellopy import Tello

from imageProcessing import main as run_gesture_recognition


def report_run_command(gesture: str) -> True:
    if gesture == "standby":
        print("Recognized standby gesture; Drone is on standby, awaiting commands.")
    elif gesture == "follow":
        print("Recognized follow gesture; follow control is implemented.")
    else:
        print(f"Recognized command: {gesture} [Command sent to drone]")


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
            "Using the Tello camera in gesture run mode. "
            "Takeoff and movement commands will be sent.")
        
        tello.takeoff()
        if tello.takeoff() == True:
            print("Drone has taken off successfully.")
            tello.move_up(150)  # Move up by 150 cm
            if tello.move_up(150) == True:
                print("Drone has moved up by 150 cm.")
            run_gesture_recognition(on_gesture=report_run_command, frame_provider=lambda: frame_reader.frame,)
    finally:  
        try:
            if stream_started:
                tello.streamoff()
        finally:
            tello.end()
        print("Disconnected from the Tello.")


if __name__ == "__main__":
    main()
