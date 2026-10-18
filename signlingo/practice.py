"""
practice.py - fingerspelling practice mode (Step 7 of the mentor's guide).

Run:  python -m signlingo.practice        (random letters)
      python -m signlingo.practice B      (focus mode: only B, good for testing one letter)
  - The screen shows a letter to make, e.g. "Make: B", and a reference picture.
  - Hold the sign steady. When the app sees that letter 10 frames in a row,
    it shows "Correct!" for 1.5 seconds and moves to the next letter.
  - J and Z are motion letters: do the whole movement (J with your pinky,
    Z with your index finger). These use Etinosa's motion_recognition.py.
  - Press a letter key to focus on that letter, or 0 for random letters.
  - SPACE skips; ESC or Main Menu returns to the menu; native close quits.
  - The gear or comma opens the shared camera settings.

Uses data/examples_*.json and the shared recipe in features.py.
"""

import random
import sys
import time
import cv2
import mediapipe as mp

from signlingo import ui
from signlingo.features import hand_to_numbers, guess_letter, load_all_examples, MOTION_LETTERS
from signlingo.menu_button import MENU_BUTTON, draw_menu_button, install
from signlingo.motion_recognition import MotionRecognizer
from signlingo.runtime import mode_camera, require_open_window
from signlingo.settings import get_settings
from signlingo.settings_ui import SettingsPanel, limit_frame_rate

FRAMES_NEEDED = 10
CORRECT_SECONDS = 1.5

examples = load_all_examples()
LETTERS = sorted({e["letter"] for e in examples})
if not LETTERS:
    raise SystemExit("No examples found. Record some with collect_data.py first.")
LETTERS = sorted(LETTERS + list(MOTION_LETTERS))


def next_target_letter(current=None, focus=None):
    """Pick a different random letter, or keep the explicitly chosen focus."""
    if focus:
        return focus
    choices = [letter for letter in LETTERS if letter != current] or LETTERS
    return random.choice(choices)


def run_practice_mode():
    focus = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if focus and focus not in LETTERS:
        raise SystemExit(f"No examples for {focus}. Letters available: {' '.join(LETTERS)}")
    store = get_settings()
    settings_panel = SettingsPanel(store)
    settings_revision = -1
    motion_tracker = MotionRecognizer()
    start_time = time.monotonic()
    last_timestamp_ms = 0
    focus_hits = 0
    last_took = None
    target_since = time.time()
    target = next_target_letter(focus=focus)
    streak = 0
    correct_until = 0
    score = 0

    with mode_camera() as (landmarker, cap):
        ui.open_window()
        install(ui.WINDOW, settings_panel)
        while cap.isOpened():
            started = time.monotonic()
            require_open_window()
            if settings_revision != settings_panel.revision:
                settings_revision = settings_panel.revision
                streak = 0
                motion_tracker = MotionRecognizer()
            preferences = store.values
            ok, frame = cap.read()
            if not ok:
                break
            if preferences.selfie:
                frame = cv2.flip(frame, 1)
            frame = ui.fit(frame)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = max(int((time.monotonic() - start_time) * 1000), last_timestamp_ms + 1)
            last_timestamp_ms = timestamp_ms
            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            h, w = frame.shape[:2]
            now = time.time()

            guess = None
            hand = result.hand_landmarks[0] if result.hand_landmarks else None
            if hand:
                if preferences.show_landmarks:
                    ui.hand_dots(frame, hand)
                guess, _ = guess_letter(hand_to_numbers(hand), examples)
            motion_letter = motion_tracker.update(
                hand if not settings_panel.is_open else None, time.monotonic(), w / h)
            if motion_letter:
                guess = motion_letter

            if now < correct_until:
                ui.centered(frame, "Correct!", h // 2, 2.5, ui.GREEN, 6, boxed=True)
            else:
                if settings_panel.is_open:
                    streak = 0
                elif target in MOTION_LETTERS:
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
                    target = next_target_letter(target, focus=focus)
                    target_since = now + CORRECT_SECONDS

                seen = guess if guess else "?"
                tip = f"Move: {ui.motion_tip(target)}" if target in MOTION_LETTERS else None
                widest = max(ui.text_width(f"Make: {target}", 2.0, 5),
                             ui.text_width(tip, 0.8, 2) if tip else 0)
                ui.top_backdrop(frame, widest, 215 if tip else 175)
                ui.text(frame, f"Make: {target}", (20, 70), 2.0, ui.WHITE, 5)
                ui.sign_card(frame, target)
                ui.hold_bar(frame, streak, FRAMES_NEEDED)
                ui.text(frame, f"I see: {seen}", (20, 155), 1.0, ui.YELLOW, 2)
                if tip:
                    ui.text(frame, tip, (20, 195), 0.8, ui.TIP, 2)

            if focus:
                took = f", last took {last_took:.1f}s" if last_took is not None else ""
                help_text = "letter key = focus   0 = random   SPACE = skip   ESC = menu"
                focus_text = f"Focus {focus}: {focus_hits} correct{took}"
                ui.help_line(frame, help_text, above=focus_text)
            else:
                help_text = f"Score: {score}   letter key = focus   SPACE = skip   ESC = menu"
                ui.help_line(frame, help_text)

            draw_menu_button(frame)
            settings_panel.draw(frame)
            require_open_window()
            ui.show(frame)
            key = cv2.waitKey(1) & 0xFF
            require_open_window()
            if settings_panel.handle_key(key):
                limit_frame_rate(started, preferences.low_power)
                continue
            if MENU_BUTTON["clicked"]:
                MENU_BUTTON["clicked"] = False
                break
            elif key == 27:
                break
            elif key == ord(" "):
                target = next_target_letter(target, focus=focus)
                streak = 0
                target_since = time.time()
            elif key == ord("0"):
                focus = None
                target = next_target_letter(target)
                streak = 0
                target_since = time.time()
            elif key != 255 and chr(key).upper() in LETTERS:
                focus = chr(key).upper()
                focus_hits, last_took = 0, None
                target = focus
                streak = 0
                correct_until = 0
                target_since = time.time()
            limit_frame_rate(started, preferences.low_power)


if __name__ == "__main__":
    run_practice_mode()
