from djitellopy import Tello


def main() -> None:
    tello = Tello()
    connected = False

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
        print(f"Battery: {tello.get_battery()}%")
    finally:
        tello.end()
        if connected:
            print("Disconnected from the Tello.")


if __name__ == "__main__":
    main()
