"""
practice.py - fingerspelling practice mode (Step 7 of the mentor's guide).

Run:  python practice.py        (random letters)
      python practice.py B      (focus mode: only B, good for testing one letter)
  - The screen shows a letter to make, e.g. "Make: B".
  - Hold the sign steady. When the app sees that letter 10 frames in a row,
    it shows "Correct!" for 1.5 seconds and moves to the next letter.
  - J and Z are motion letters: do the whole movement (J with your pinky,
    Z with your index finger). These use Etinosa's motion_recognition.py.
  - Press any letter key to switch to focus mode on that letter: it keeps
    asking for the same letter and shows how many times it worked and how
    long the last one took. Press 0 to go back to random letters.
  - Press SPACE to skip a letter, ESC to go back (to the menu in the app).

It uses every data/examples_*.json file (Karen's, the Kaggle dataset, and
anything recorded with collect_data.py) and the shared recipe in features.py.
"""

import random
import sys
import time
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from features import hand_to_numbers, guess_letter, load_all_examples, MOTION_LETTERS
from motion_recognition import MotionRecognizer
import ui_style as ui

FRAMES_NEEDED = 10      # how many frames in a row must match
CORRECT_SECONDS = 1.5   # how long "Correct!" stays on screen

examples = load_all_examples()
LETTERS = sorted({e["letter"] for e in examples})
if not LETTERS:
    raise SystemExit("No examples found. Record some with collect_data.py first.")
LETTERS = sorted(LETTERS + list(MOTION_LETTERS))
print("Practicing letters:", " ".join(LETTERS))


def next_target(current=None):
    """Pick a random letter, but not the same one twice in a row.
    In focus mode, always the focus letter."""
    if focus:
        return focus
    choices = [L for L in LETTERS if L != current] or LETTERS
    return random.choice(choices)


landmarker = vision.HandLandmarker.create_from_options(
    vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path="hand_landmarker.task"),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
    )
)

motion_tracker = MotionRecognizer()

cap = cv2.VideoCapture(0)
start = time.time()
last_timestamp_ms = 0

# Focus mode: python practice.py B  (or press a letter key while running)
focus = sys.argv[1].upper() if len(sys.argv) > 1 else None
if focus and focus not in LETTERS:
    raise SystemExit(f"No examples for {focus}. Letters available: {' '.join(LETTERS)}")
focus_hits = 0          # how many times the focus letter worked
last_took = None        # seconds the last success took
target_since = time.time()

target = next_target()
streak = 0              # matching frames in a row
correct_until = 0       # time when the "Correct!" message ends
score = 0

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    timestamp_ms = max(int((time.time() - start) * 1000), last_timestamp_ms + 1)
    last_timestamp_ms = timestamp_ms
    result = landmarker.detect_for_video(mp_image, timestamp_ms)
    h, w = frame.shape[:2]
    now = time.time()

    guess = None
    hand = result.hand_landmarks[0] if result.hand_landmarks else None
    if hand:
        ui.draw_hand(frame, hand)
        guess, _ = guess_letter(hand_to_numbers(hand), examples)
    # The motion tracker watches every frame for a J or Z movement
    motion_letter = motion_tracker.update(hand, time.monotonic(), w / h)
    if motion_letter:
        guess = motion_letter

    if now < correct_until:
        # Showing "Correct!" - wait, then the next letter is already set
        ui.draw_correct(frame)
    else:
        if target in MOTION_LETTERS:
            # One finished movement is enough for J and Z
            streak = FRAMES_NEEDED if motion_letter == target else 0
        else:
            streak = streak + 1 if guess == target else 0
        if streak >= FRAMES_NEEDED:
            score += 1
            streak = 0
            correct_until = now + CORRECT_SECONDS
            last_took = now - target_since
            if focus:
                focus_hits += 1
            target = next_target(target)
            target_since = now + CORRECT_SECONDS

        ui.draw_target(frame, f"Make: {target}")
        ui.draw_progress(frame, streak / FRAMES_NEEDED)   # fills up as you hold the right sign
        ui.draw_seen(frame, guess)
        if target in MOTION_LETTERS:
            ui.draw_tip(frame, ui.motion_tip(target))

    if focus:
        took = f", last took {last_took:.1f}s" if last_took is not None else ""
        ui.draw_info(frame, f"Focus {focus}: {focus_hits} correct{took}")
        help_text = "letter key = focus   0 = random   SPACE = skip   ESC = menu"
    else:
        help_text = f"Score: {score}   letter key = focus   SPACE = skip   ESC = menu"
    ui.draw_help(frame, help_text)

    cv2.imshow(ui.WINDOW, frame)
    key = cv2.waitKey(1) & 0xFF
    if key == 27:                 # ESC quits
        break
    if key == ord(" "):           # skip this letter
        target = next_target(target)
        streak = 0
        target_since = time.time()
    elif key == ord("0"):         # back to random letters
        focus = None
        target = next_target(target)
        streak = 0
        target_since = time.time()
    elif key != 255 and chr(key).upper() in LETTERS:   # focus on that letter
        focus = chr(key).upper()
        focus_hits, last_took = 0, None
        target = focus
        streak = 0
        correct_until = 0
        target_since = time.time()

cap.release()
cv2.destroyAllWindows()
