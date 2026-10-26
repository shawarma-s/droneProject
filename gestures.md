The best way to extend `imageProcessing.py` is to build the gesture system in layers:

```text
MediaPipe landmarks
    -> finger states
    -> gesture name
    -> stable gesture
    -> drone command later
```

Do not put Tello movement calls in `imageProcessing.py`. According to `roughGuide.md`, this file should identify gestures and return vision information. `droneControl.py` should later decide whether and how to move the drone.

---

## 1. Understand the 21 landmarks

MediaPipe returns 21 landmarks for every detected hand:

```text
0  wrist

1  thumb CMC
2  thumb MCP
3  thumb IP
4  thumb tip

5  index MCP
6  index PIP
7  index DIP
8  index tip

9  middle MCP
10 middle PIP
11 middle DIP
12 middle tip

13 ring MCP
14 ring PIP
15 ring DIP
16 ring tip

17 pinky MCP
18 pinky PIP
19 pinky DIP
20 pinky tip
```

The current code already uses:

```python
thumb_tip = hand_landmarks[4]
index_tip = hand_landmarks[8]
```

You can use the other fingertip and joint indexes to determine which fingers are extended.

---

## 2. Represent finger states

Instead of immediately deciding that a hand means `"move left"` or `"move right"`, first represent the hand as a set of finger states.

For example:

```python
{
    "thumb": True,
    "index": False,
    "middle": False,
    "ring": False,
    "pinky": False,
}
```

This means only the thumb is extended.

Add this function above `main()`:

```python
def get_finger_states(hand_landmarks) -> dict[str, bool]:
    return {
        "thumb": is_thumb_extended(hand_landmarks),
        "index": is_finger_extended(hand_landmarks, 8, 6),
        "middle": is_finger_extended(hand_landmarks, 12, 10),
        "ring": is_finger_extended(hand_landmarks, 16, 14),
        "pinky": is_finger_extended(hand_landmarks, 20, 18),
    }
```

The arguments for the non-thumb fingers are:

```text
tip index, PIP joint index
```

For example:

```python
is_finger_extended(hand_landmarks, 8, 6)
```

means:

- index fingertip: landmark `8`
- index PIP joint: landmark `6`

---

## 3. Detect upright fingers

For an upright hand, an extended finger usually has a smaller `y` value at its tip than at its PIP joint.

Image coordinates increase downward:

```text
top of image:    y = 0.0
bottom of image: y = 1.0
```

Therefore:

```python
def is_finger_extended(hand_landmarks, tip_index: int, pip_index: int) -> bool:
    tip = hand_landmarks[tip_index]
    pip = hand_landmarks[pip_index]
    return tip.y < pip.y
```

This works for the upright gestures described in the README.

It does not yet support arbitrary hand rotation. Later, you can replace this with an angle-based calculation if users need to rotate their hands.

---

## 4. Detect the thumb separately

The thumb moves sideways rather than vertically, so comparing only `y` coordinates is not reliable.

A simple first version can compare the thumb tip to the thumb’s MCP joint:

```python
def is_thumb_extended(hand_landmarks) -> bool:
    thumb_tip = hand_landmarks[4]
    thumb_mcp = hand_landmarks[2]

    return abs(thumb_tip.x - thumb_mcp.x) > 0.08
```

This is only a starting point. Because the image is flipped with:

```python
frame = cv2.flip(frame, 1)
```

the thumb’s horizontal direction depends on which hand is being used and how the hand is oriented.

A more reliable version should use MediaPipe’s handedness result. The current detector returns:

```python
results.handedness
```

alongside:

```python
results.hand_landmarks
```

For your first version, keep the thumb test simple and tune the `0.08` threshold while looking at the landmark overlay.

---

## 5. Recognize the README gestures

The README defines these gestures:

| Finger state | Gesture |
|---|---|
| Thumb | Move left |
| Thumb + index | Move right |
| Thumb + index + middle | Move up |
| Thumb + index + middle + ring | Move down |
| All five | Move forward |
| Thumb and index touching, other fingers up | Move backwards |
| Index and middle pointing down | Land |
| Only pinky up | Follow mode |

Add a classifier:

```python
def classify_gesture(hand_landmarks) -> str:
    fingers = get_finger_states(hand_landmarks)

    thumb = fingers["thumb"]
    index = fingers["index"]
    middle = fingers["middle"]
    ring = fingers["ring"]
    pinky = fingers["pinky"]

    if is_land_gesture(hand_landmarks):
        return "land"

    if is_pinch(hand_landmarks) and middle and ring and pinky:
        return "move_backward"

    if thumb and index and middle and ring and pinky:
        return "move_forward"

    if thumb and index and middle and ring and not pinky:
        return "move_down"

    if thumb and index and middle and not ring and not pinky:
        return "move_up"

    if thumb and index and not middle and not ring and not pinky:
        return "move_right"

    if thumb and not index and not middle and not ring and not pinky:
        return "move_left"

    if pinky and not thumb and not index and not middle and not ring:
        return "follow"

    return "none"
```

The order matters. More specific gestures should be checked first.

For example, the all-five-fingers gesture also contains:

```text
thumb + index
thumb + index + middle
thumb + index + middle + ring
```

If you checked `"thumb + index"` first, an open hand would incorrectly become `"move_right"`.

---

## 6. Reuse the current pinch calculation

Move the existing pinch calculation into a function:

```python
def is_pinch(hand_landmarks) -> bool:
    thumb_tip = hand_landmarks[4]
    index_tip = hand_landmarks[8]

    distance = (
        (thumb_tip.x - index_tip.x) ** 2
        + (thumb_tip.y - index_tip.y) ** 2
    ) ** 0.5

    return distance < 0.05
```

Then this condition:

```python
if is_pinch(hand_landmarks) and middle and ring and pinky:
    return "move_backward"
```

means:

- thumb and index are touching;
- middle, ring, and pinky are extended.

That corresponds to the `"👌"` gesture described in the README.

You may need to tune `0.05`. A smaller value requires a tighter pinch; a larger value makes detection easier but less precise.

---

## 7. Detect the landing gesture

The landing gesture is:

```text
index and middle fingers pointing down
```

The current `is_finger_extended()` function assumes fingers point upward, so you need a separate downward test.

```python
def is_finger_pointing_down(
    hand_landmarks,
    tip_index: int,
    pip_index: int,
) -> bool:
    tip = hand_landmarks[tip_index]
    pip = hand_landmarks[pip_index]
    return tip.y > pip.y
```

Then:

```python
def is_land_gesture(hand_landmarks) -> bool:
    index_down = is_finger_pointing_down(hand_landmarks, 8, 6)
    middle_down = is_finger_pointing_down(hand_landmarks, 12, 10)

    thumb = is_thumb_extended(hand_landmarks)
    ring = is_finger_extended(hand_landmarks, 16, 14)
    pinky = is_finger_extended(hand_landmarks, 20, 18)

    return (
        index_down
        and middle_down
        and not thumb
        and not ring
        and not pinky
    )
```

This is a basic version. Before allowing it to trigger a real landing, make the controller require the gesture to be stable for multiple frames and ideally require a separate confirmation.

A mistaken landing classification is more serious than a mistaken movement classification.

---

## 8. Use the classifier inside the current loop

Currently, the loop calculates the pinch label directly:

```python
label = "Pinch" if distance < 0.05 else "Open Hand"
```

Replace that part with:

```python
gesture = classify_gesture(hand_landmarks)
```

Then display the gesture:

```python
cv2.putText(
    frame,
    gesture,
    (50, 50),
    cv2.FONT_HERSHEY_SIMPLEX,
    1,
    (0, 255, 0),
    2,
)
```

You can also display the individual finger states while tuning:

```python
finger_text = ", ".join(
    name for name, extended in get_finger_states(hand_landmarks).items()
    if extended
)

cv2.putText(
    frame,
    finger_text or "none",
    (50, 90),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.7,
    (255, 255, 0),
    2,
)
```

This helps you determine whether a problem is in:

1. finger detection, or
2. gesture classification.

For example, if an open hand displays only:

```text
thumb, index, middle, ring
```

then the problem is probably the pinky detection threshold, not the gesture mapping.

---

## 9. Add gesture stability

MediaPipe landmarks can fluctuate between frames. If you send a drone command whenever one frame is classified, the drone may receive rapidly changing commands.

A gesture should be accepted only after appearing consistently for several frames.

Add these variables near the start of `main()`:

```python
previous_gesture = "none"
stable_gesture = "none"
gesture_frames = 0
required_stable_frames = 5
```

Inside the hand-processing loop:

```python
gesture = classify_gesture(hand_landmarks)

if gesture == previous_gesture:
    gesture_frames += 1
else:
    previous_gesture = gesture
    gesture_frames = 1

if gesture_frames >= required_stable_frames:
    stable_gesture = gesture
```

Display the stable result:

```python
cv2.putText(
    frame,
    f"Gesture: {stable_gesture}",
    (50, 50),
    cv2.FONT_HERSHEY_SIMPLEX,
    1,
    (0, 255, 0),
    2,
)
```

This means a gesture must be recognized for five consecutive frames before it becomes active.

You should also reset the gesture when no hand is detected:

```python
if not results.hand_landmarks:
    previous_gesture = "none"
    stable_gesture = "none"
    gesture_frames = 0
```

This is important for the follow-mode failsafe described in the rough guide.

---

## 10. Detect the pinky follow gesture

The follow gesture is:

```text
only pinky pointing up
```

The classifier already represents that as:

```python
if pinky and not thumb and not index and not middle and not ring:
    return "follow"
```

However, recognizing `"follow"` and following the hand are separate tasks.

The vision code should provide information such as:

```text
gesture = "follow"
hand center = (x, y)
hand size = ...
```

The actual follow controller in `droneControl.py` can use that data to decide:

- move left or right based on the hand’s horizontal position;
- move up or down based on the hand’s vertical position;
- move forward or backward based on the apparent hand size;
- stop when the hand is centered.

`imageProcessing.py` should not directly call:

```python
drone.move_left(...)
drone.send_rc_control(...)
```

---

## 11. Calculate the hand center

For follow mode, calculate the center of the hand landmarks:

```python
def get_hand_center(hand_landmarks) -> tuple[float, float]:
    x_values = [landmark.x for landmark in hand_landmarks]
    y_values = [landmark.y for landmark in hand_landmarks]

    return (
        sum(x_values) / len(x_values),
        sum(y_values) / len(y_values),
    )
```

The result is normalized:

```text
x = 0.0 -> left edge
x = 0.5 -> center
x = 1.0 -> right edge

y = 0.0 -> top edge
y = 0.5 -> center
y = 1.0 -> bottom edge
```

A controller can use a dead zone:

```python
center_x, center_y = get_hand_center(hand_landmarks)

horizontal_error = center_x - 0.5
vertical_error = center_y - 0.5

if abs(horizontal_error) < 0.1:
    horizontal_error = 0.0

if abs(vertical_error) < 0.1:
    vertical_error = 0.0
```

The dead zone prevents the drone from constantly correcting tiny movements.

---

## 12. Calculate approximate hand size

To estimate whether the hand is closer or farther from the camera, calculate a bounding box:

```python
def get_hand_bbox(hand_landmarks) -> tuple[float, float, float, float]:
    x_values = [landmark.x for landmark in hand_landmarks]
    y_values = [landmark.y for landmark in hand_landmarks]

    left = min(x_values)
    right = max(x_values)
    top = min(y_values)
    bottom = max(y_values)

    return left, top, right, bottom
```

Then:

```python
left, top, right, bottom = get_hand_bbox(hand_landmarks)
hand_width = right - left
hand_height = bottom - top
hand_size = max(hand_width, hand_height)
```

A larger hand usually means it is closer to the camera. A smaller hand usually means it is farther away.

You can return this data from the vision layer later:

```python
{
    "gesture": stable_gesture,
    "center": (center_x, center_y),
    "size": hand_size,
    "detected": True,
}
```

That structured result is more useful than returning only a string.

---

## 13. Recommended development order

Build and test the gestures in this order:

### Stage 1: finger-state display

First display:

```text
thumb=True
index=False
middle=False
ring=False
pinky=False
```

Do not classify gestures yet.

Test each finger independently.

### Stage 2: static gesture classification

Add `classify_gesture()` and display:

```text
move_left
move_right
move_up
move_down
move_forward
move_backward
land
follow
none
```

Do not connect the drone yet.

### Stage 3: stability filtering

Require several consecutive frames before changing the active gesture.

### Stage 4: recorded or webcam testing

Test:

- changing from one gesture to another;
- removing the hand;
- partially hiding fingers;
- moving the hand closer and farther away;
- rotating the hand slightly.

### Stage 5: command output only

Have the vision layer produce command names, but only print them:

```python
print(f"Command: {stable_gesture}")
```

Do not send them to the Tello yet.

### Stage 6: connect to `droneControl.py`

Only after the classifications are reliable should the control layer map gestures to movement commands.

---

## Important limitations of the first version

The simple comparisons above are useful for learning, but they have limitations:

- They assume the hand is mostly upright.
- They do not fully account for left versus right hand.
- They may misclassify bent fingers.
- The thumb requires different logic from the other fingers.
- A single frame can be noisy.
- A `"land"` gesture should have stronger confirmation than a movement gesture.
- The same gesture held for many frames must not repeatedly trigger discrete drone commands.

The rough guide’s architecture addresses this by separating:

```text
landmarks
    -> finger states
    -> named gesture
    -> stable gesture
    -> validated drone command
```

That is the main structure to preserve as you add more gestures.