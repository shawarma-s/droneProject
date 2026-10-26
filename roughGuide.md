The repository currently has the dependency list in `requirements.txt`, but the three Python modules are empty:

- `imageProcessing.py`
- `droneControl.py`
- `telemetry.py`

The README describes two related systems: gesture-based movement and a pinky-triggered follow mode. A clean setup would separate those responsibilities rather than placing all logic in one loop.

## 1. Prepare the Python environment

The project already declares:

- OpenCV for camera input and image display.
- `djitellopy` for communicating with the Tello.

The hand detector is a separate concern. OpenCV can capture and process frames, but it does not by itself identify fingertips or count raised fingers. The project therefore needs either:

- the hand-tracking library specified by the report, or
- another landmark detector that produces the required hand keypoints.

The environment setup should include:

1. Create and activate a virtual environment.
2. Install `requirements.txt`.
3. Add the chosen hand-landmark dependency if it is not already included in the report’s setup.
4. Confirm that Python can import OpenCV, `djitellopy`, and the hand-tracking package.
5. Test the webcam independently before connecting the drone.

Do not begin with the drone connected. First verify that the camera can produce frames and that hand landmarks can be drawn on those frames.

## 2. Establish the OpenCV processing pipeline

`imageProcessing.py` should be responsible for vision only.

Its processing pipeline should be conceptually:

1. Open the webcam with `cv2.VideoCapture`.
2. Read a frame.
3. Convert the frame into the color format expected by the hand detector.
4. Run hand detection or landmark estimation.
5. Extract the landmarks for the detected hand.
6. Determine which fingers are extended.
7. Return a structured result to the control layer.
8. Draw optional diagnostic landmarks and labels for the operator.
9. Display the frame and provide a clean quit path.

The image-processing module should not directly call Tello movement methods. Instead, it should return information such as:

- whether a hand was detected;
- the number or identity of extended fingers;
- the hand’s bounding box or center;
- the wrist and fingertip coordinates;
- whether the hand appears to satisfy a special gesture.

That separation makes it possible to test gesture recognition with prerecorded camera footage without risking drone movement.

## 3. Represent gestures as data

The README in `README.md` lists the desired gesture meanings. The implementation should translate detector output into a neutral gesture representation before translating it into a drone command.

For example, the flow should be:

```text
hand landmarks
    -> finger-state representation
    -> named gesture/state
    -> requested movement
    -> safety-checked Tello command
```

The gesture recognizer needs to account for more than just the number of raised fingers:

- which fingers are raised;
- whether fingers point upward or downward;
- whether the thumb and index finger touch;
- whether the hand has disappeared;
- whether the gesture is stable across multiple frames.

A gesture should normally be accepted only after it has remained stable for several frames. Otherwise, small detection fluctuations could cause repeated or contradictory commands.

The gesture recognizer should also have an explicit “unknown” or “no command” result. It should not interpret every failed detection as a movement.

## 4. Set up the Tello connection

`droneControl.py` should own the drone lifecycle.

The control setup should follow this order:

1. Create the Tello object.
2. Connect to the drone.
3. Read and log the battery level.
4. Start the video stream only if the implementation uses the drone’s camera; otherwise keep the webcam and drone-video paths distinct.
5. Keep the drone landed while testing gesture recognition.
6. Send takeoff only after an explicit operator action.
7. Send movement commands through a single command interface.
8. Land on exit, on a failsafe, or when the operator requests it.
9. End the video stream and disconnect cleanly.

The control module should not allow image-processing code to call arbitrary drone methods. A central command layer should validate:

- whether the drone is connected;
- whether takeoff has occurred;
- whether the requested command is safe in the current mode;
- whether another command is already active;
- whether the command should be sent once or continuously.

## 5. Choose the movement-control model

The README describes movement actions rather than continuous joystick control. There are two common ways to implement that:

### Discrete movement commands

Each recognized gesture maps to one short movement action, such as a limited translation or rotation. The command should have a bounded distance or duration, followed by a neutral period.

This is simpler for an initial implementation, but it can repeatedly trigger if the same gesture remains visible.

### Continuous `rc` control

The gesture determines a velocity direction, and the controller repeatedly sends roll, pitch, yaw, and vertical-speed values while the gesture is active. When the gesture changes or disappears, the controller sends a zero-velocity command.

This is more appropriate for follow mode and responsive steering, but it requires:

- a fixed control-loop rate;
- command timeout handling;
- explicit neutral commands;
- protection against stale gestures.

For this project, it is useful to keep the gesture recognizer independent of which of these movement strategies is eventually selected.

## 6. Add a command state machine

A small state machine will prevent conflicts between gestures and follow mode. Possible states include:

```text
DISCONNECTED
LANDED
READY
MANUAL_CONTROL
FOLLOW_CONTROL
LANDING
FAILSAFE
```

The state machine should define rules such as:

- movement gestures are ignored before the drone is ready;
- follow mode cannot activate unless a valid pinky gesture is stable;
- manual gestures do not override an active failsafe;
- landing cancels movement;
- loss of the hand in follow mode triggers the required response;
- reconnecting is not silently treated as success.

This logic belongs in `droneControl.py`, not in the OpenCV drawing code.

## 7. Implement follow mode using landmark geometry

Follow mode requires more than recognizing the pinky gesture. Once activated, the program must continuously estimate where the hand is relative to the camera image.

The vision layer should provide:

- the hand’s center position;
- the apparent hand size or bounding-box size;
- whether the hand is still confidently detected.

The control layer can then compare those measurements with desired values:

- horizontal error controls left/right correction;
- vertical error controls up/down correction;
- apparent-size error estimates whether the drone is too near or too far;
- a dead zone prevents constant oscillation.

The controller should smooth these values over multiple frames and limit the maximum speed. It should not command movement directly from one noisy frame.

Follow mode should also have an explicit activation and deactivation rule. A temporary pinky-detection failure should not necessarily activate or deactivate the mode immediately; use a short confirmation window. However, once the hand is genuinely lost while following, the failsafe must take priority over normal tracking.

## 8. Implement the follow-mode failsafe

The README requires that, when the hand is no longer detected during follow mode, the drone should:

1. Stop horizontal and rotational movement.
2. Descend slowly.
3. Deactivate follow mode.

That behavior should be centralized and idempotent: if multiple consecutive frames report “no hand,” the controller should not repeatedly create conflicting movement commands.

The failsafe should also be triggered by:

- camera failure;
- processing exceptions;
- loss of the drone connection;
- low battery;
- operator quit;
- command timeout.

The exact response should be tested while the drone is restrained or simulated before attempting a free flight.

## 9. Use telemetry separately

`telemetry.py` can periodically collect and display or log:

- battery;
- height;
- flight time;
- temperature;
- connection status;
- current control mode;
- last recognized gesture;
- whether a failsafe is active.

Telemetry should not decide movement. It should report state to the operator and provide diagnostics when tuning gesture thresholds or follow behavior.

## 10. Test in stages

A safe progression would be:

1. Test webcam capture only.
2. Test hand landmarks and visual overlays.
3. Test finger-state classification without a drone.
4. Test gesture stability and transitions using logged frames.
5. Connect to the Tello and read telemetry while it remains landed.
6. Verify that commands are generated but initially intercepted or logged.
7. Test individual movements in a clear indoor area with a human pilot ready to intervene.
8. Test hand-loss handling while the drone is stationary.
9. Test follow mode at low speed and short range.
10. Test landing, quit, connection loss, and low-battery paths.

The most important architectural principle is to keep the pipeline modular:

```text
OpenCV camera
    -> hand landmarks
    -> gesture/follow interpretation
    -> validated command state
    -> Tello control
    -> telemetry and safety logging
```

That structure lets you complete and test the computer-vision portion without accidentally coupling a misclassified gesture directly to an unsafe flight command.