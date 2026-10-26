from pathlib import Path
from urllib.request import urlopen

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


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


def main() -> None:
    ensure_model()
    options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        raise RuntimeError("Could not open the webcam.")

    timestamp_ms = 0
    try:
        with vision.HandLandmarker.create_from_options(options) as hand_landmarker:
            while True:
                ret, frame = capture.read()
                if not ret:
                    break

                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                results = hand_landmarker.detect_for_video(mp_image, timestamp_ms)
                timestamp_ms += 1

                for hand_landmarks in results.hand_landmarks:
                    draw_landmarks(frame, hand_landmarks)

                    for landmark_id, landmark in enumerate(hand_landmarks):
                        print(
                            f"Landmark {landmark_id}: "
                            f"(x: {landmark.x}, y: {landmark.y}, z: {landmark.z})"
                        )

                    thumb_tip = hand_landmarks[4]
                    index_tip = hand_landmarks[8]
                    distance = (
                        (thumb_tip.x - index_tip.x) ** 2
                        + (thumb_tip.y - index_tip.y) ** 2
                    ) ** 0.5
                    label = "Pinch" if distance < 0.05 else "Open Hand"
                    cv2.putText(
                        frame,
                        label,
                        (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2,
                    )

                cv2.imshow("Hand Tracking", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
