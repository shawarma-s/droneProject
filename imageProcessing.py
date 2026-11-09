from pathlib import Path
import time
from collections.abc import Callable
from urllib.request import urlopen

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from numpy.typing import NDArray


def notify_callback(callback: Callable, value, name: str) -> None:
    try:
        callback(value)
    except Exception as error:
        print(f"{name} callback failed: {error}")


MODEL_PATH = Path(__file__).with_name("hand_landmarker.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)


def ensure_model() -> None:
    if MODEL_PATH.exists():
        return

    print("Downloading the MediaPipe hand-landmarker model...")
    try:
        with urlopen(MODEL_URL, timeout=30) as response:
            MODEL_PATH.write_bytes(response.read())
    except Exception as error:
        MODEL_PATH.unlink(missing_ok=True)
        raise RuntimeError(
            f"Could not download the hand-landmarker model from {MODEL_URL}"
        ) from error


def draw_landmarks(frame, hand_landmarks) -> None:
    height, width = frame.shape[:2]
    points = [
        (int(landmark.x * width), int(landmark.y * height))
        for landmark in hand_landmarks
    ]

    for connection in vision.HandLandmarksConnections.HAND_CONNECTIONS:
        cv2.line(
            frame,
            points[connection.start],
            points[connection.end],
            (0, 255, 0),
            2,
        )

    for point in points:
        cv2.circle(frame, point, 4, (0, 0, 255), -1)


def is_finger_extended(hand_landmarks, tip_index: int, pip_index: int) -> bool:
    return hand_landmarks[tip_index].y < hand_landmarks[pip_index].y


def is_thumb_pointing_up(hand_landmarks) -> bool:
    thumb_mcp = hand_landmarks[2]
    thumb_tip = hand_landmarks[4]
    index_mcp = hand_landmarks[5]
    pinky_mcp = hand_landmarks[17]

    palm_width = (
        (index_mcp.x - pinky_mcp.x) ** 2
        + (index_mcp.y - pinky_mcp.y) ** 2
    ) ** 0.5
    thumb_length = (
        (thumb_tip.x - thumb_mcp.x) ** 2
        + (thumb_tip.y - thumb_mcp.y) ** 2
    ) ** 0.5

    return (
        palm_width > 0
        and thumb_tip.y < thumb_mcp.y
        and thumb_length > palm_width * 0.35
    )


def classify_gesture(hand_landmarks) -> str:
    finger_landmarks = {
        "index": (8, 6),
        "middle": (12, 10),
        "ring": (16, 14),
        "pinky": (20, 18),
    }
    raised_fingers = frozenset(
        name
        for name, (tip_index, pip_index) in finger_landmarks.items()
        if is_finger_extended(hand_landmarks, tip_index, pip_index)
    )
    if not raised_fingers and is_thumb_pointing_up(hand_landmarks):
        return "standby"

    gestures = {
        frozenset({"index"}): "move_left",
        frozenset({"index", "middle"}): "move_right",
        frozenset({"index", "middle", "ring"}): "move_up",
        frozenset({"index", "middle", "ring", "pinky"}): "move_down",
        frozenset({"index", "ring", "pinky"}): "move_forward",
        frozenset({"index", "middle", "pinky"}): "move_backward",
        frozenset({"middle", "ring", "pinky"}): "land",
        frozenset({"pinky"}): "follow",
    }
    return gestures.get(raised_fingers, "none")


def main(
    on_gesture: Callable[[str], None] | None = None,
    frame_provider: Callable[[], NDArray[np.uint8] | None] | None = None,
    on_hand=None,
    on_key: Callable[[str], None] | None = None,
    stop_event=None,
) -> None:
    ensure_model()
    options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    capture = None
    if frame_provider is None:
        capture = cv2.VideoCapture(0)
        if not capture.isOpened():
            raise RuntimeError("Could not open the webcam.")

    timestamp_ms = 0
    previous_gesture = "none"
    stable_gesture = "none"
    gesture_frames = 0
    required_stable_frames = 5
    missing_hand_since = None
    last_reported_gesture = "none"

    try:
        with vision.HandLandmarker.create_from_options(options) as hand_landmarker:
            while True:
                if stop_event is not None and stop_event.is_set():
                    break
                if capture is not None:
                    ret, frame = capture.read()
                    if not ret:
                        raise RuntimeError("Could not read a frame from the webcam.")
                else:
                    if frame_provider is None:
                        raise RuntimeError("No camera frame source is available.")
                    frame = frame_provider()
                    if frame is None:
                        if on_hand is not None:
                            notify_callback(on_hand, None, "Hand tracking")
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord("q"):
                            break
                        if key == ord("f") and on_key is not None:
                            notify_callback(on_key, "f", "Keyboard")
                        time.sleep(0.01)
                        continue

                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                results = hand_landmarker.detect_for_video(mp_image, timestamp_ms)
                timestamp_ms += 1

                if results.hand_landmarks:
                    missing_hand_since = None
                    hand_landmarks = results.hand_landmarks[0]
                    draw_landmarks(frame, hand_landmarks)
                    gesture = classify_gesture(hand_landmarks)
                    if gesture == previous_gesture:
                        gesture_frames += 1
                    else:
                        previous_gesture = gesture
                        gesture_frames = 1
                        stable_gesture = "none"

                    if gesture_frames >= required_stable_frames:
                        stable_gesture = gesture
                else:
                    if missing_hand_since is None:
                        missing_hand_since = time.monotonic()
                    previous_gesture = "none"
                    gesture_frames = 0
                    if time.monotonic() - missing_hand_since >= 30:
                        stable_gesture = "land"
                    else:
                        stable_gesture = "none"

                if stable_gesture != last_reported_gesture:
                    if stable_gesture != "none" and on_gesture is not None:
                        notify_callback(on_gesture, stable_gesture, "Gesture")
                    last_reported_gesture = stable_gesture

                if on_hand is not None:
                    hand = results.hand_landmarks[0] if results.hand_landmarks else None
                    notify_callback(on_hand, hand, "Hand tracking")

                cv2.putText(
                    frame,
                    f"Gesture: {stable_gesture}",
                    (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )

                cv2.imshow("Hand Tracking", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("f") and on_key is not None:
                    notify_callback(on_key, "f", "Keyboard")
    finally:
        if capture is not None:
            capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
