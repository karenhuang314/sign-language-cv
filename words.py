"""
words.py - ASL fingerspelling word challenge mode for SignLingo.
Presents randomized words up to 5 characters with sequential real-time tracking.
"""

import os
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

# Bundle path resolution
if getattr(sys, "frozen", False):
    os.chdir(sys._MEIPASS)
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

FRAMES_NEEDED = 8
WORD_CELEBRATE_SECS = 1.3

examples = load_all_examples()
LETTERS = sorted({e["letter"] for e in examples})
if not LETTERS:
    raise SystemExit("No examples found. Record some with collect_data.py first.")
LETTERS = sorted(LETTERS + list(MOTION_LETTERS))

# Dictionary of real words between 2 and 5 characters
DICTIONARY = [
    # 2-letter
    "AI", "AT", "BY", "GO", "HI", "IN", "IS", "IT", "MY", "NO", "ON", "OR", "TO", "UP",
    # 3-letter
    "ACE", "ACT", "AIR", "ARM", "BAD", "BAG", "BAR", "BAT", "BED", "BET", "BIG", "BIT",
    "BOX", "BOY", "BUS", "BUY", "CAN", "CAP", "CAR", "CAT", "CUP", "CUT", "DAY", "DOG",
    "DRY", "EAR", "EAT", "EGG", "END", "EYE", "FAN", "FAR", "FAT", "FIT", "FLY", "FOR",
    "FOX", "FUN", "GET", "HAT", "HIT", "HOT", "ICE", "INK", "JAR", "KEY", "LEG", "LIP",
    "MAP", "NET", "NUT", "PEN", "PET", "PIN", "POT", "RED", "RUN", "SIT", "SKY", "SUN",
    "TEA", "TIE", "TOY", "VAN", "WAR", "WET", "WIN", "ZIP",
    # 4-letter
    "ABLE", "ACID", "AGED", "AWAY", "BABY", "BACK", "BAKE", "BALL", "BAND", "BANK",
    "BARN", "BATH", "BEAR", "BEAT", "BIRD", "BITE", "BLUE", "BOAT", "BODY", "BONE",
    "BOOK", "BORN", "BURN", "BUSY", "BYTE", "CAFE", "CAKE", "CALL", "CALM", "CAMP",
    "CARD", "CARE", "CHAT", "CHEF", "CITY", "CLAY", "CLIP", "CLUB", "COAT", "CODE",
    "COLD", "COOK", "COOL", "COPY", "CORN", "COST", "DARK", "DATA", "DATE", "DAWN",
    "DEAL", "DEAR", "DESK", "DIET", "DISH", "DOOR", "DRAW", "DROP", "DRUM", "DUCK",
    "DUST", "DUTY", "EASY", "EDGE", "EVEN", "EXIT", "FACE", "FACT", "FAIL", "FAIR",
    "FARM", "FAST", "FEEL", "FILL", "FILM", "FIND", "FIRE", "FISH", "FIVE", "FLAG",
    "FLOW", "FOOD", "FORK", "FREE", "FROG", "FULL", "GAME", "GATE", "GIFT", "GLOW",
    "GOLD", "GOOD", "GRAB", "GRID", "GROW", "HAIR", "HALF", "HAND", "HARD", "HEAD",
    "HELP", "HERO", "HIDE", "HILL", "HOLD", "HOME", "HOPE", "HORN", "HOUR", "HUNT",
    "ICON", "IDEA", "IRON", "ITEM", "JOIN", "JUMP", "JUST", "KEEP", "KING", "KITE",
    "KNOT", "LAKE", "LAMP", "LAND", "LANE", "LEAF", "LEAN", "LION", "LOCK", "LOOP",
    "LUCK", "MAKE", "MARK", "MATH", "MEAL", "MIND", "MOON", "NAME", "NEAR", "NEST",
    "NODE", "NOTE", "OPEN", "PACK", "PAGE", "PARK", "PATH", "PLAN", "PLAY", "PLUG",
    "POST", "PUMP", "RAIN", "READ", "RING", "ROAD", "ROBOT", "ROCK", "ROOF", "ROOM",
    "ROSE", "SAFE", "SAND", "SEED", "SHIP", "SHOP", "SIGN", "SNOW", "STAR", "STEP",
    "TEAM", "TECH", "TEST", "TIME", "TREE", "UNIT", "USER", "VIEW", "WAVE", "WIND",
    # 5-letter
    "APPLE", "BEACH", "BLACK", "BRAIN", "BREAD", "BROWN", "CHAIR", "CHESS", "CLEAN",
    "CLOCK", "CLOUD", "CRAFT", "DANCE", "DRAFT", "DREAM", "DRIVE", "EARTH", "FLAME",
    "FLOAT", "FOCUS", "FRUIT", "GIANT", "GLASS", "GRAPE", "GREEN", "HEART", "HONEY",
    "HOUSE", "IMAGE", "JUICE", "LIGHT", "LOGIC", "LUNCH", "MAGIC", "MATCH", "MODEL",
    "MONEY", "MOUSE", "MUSIC", "NIGHT", "OCEAN", "PAINT", "PAPER", "PARTY", "PEACE",
    "PIANO", "PILOT", "PIZZA", "PLANT", "PLATE", "POINT", "POWER", "PRIDE", "PRIME",
    "QUICK", "QUIET", "RADIO", "RIVER", "ROBOT", "SCALE", "SCOPE", "SHARK", "SHIRT",
    "SMILE", "SMOKE", "SNAKE", "SPACE", "SPEED", "SPORT", "STAND", "STORM", "SUGAR",
    "TABLE", "TIGER", "TOUCH", "TRAIN", "TRUCK", "VALVE", "VOICE", "WATER", "WHEEL",
    "WHITE", "WOMAN", "WORLD", "YOUTH"
]

# Keep only words whose letters exist entirely within your dataset
VALID_WORDS = [w for w in DICTIONARY if len(w) <= 5 and all(c in LETTERS for c in w)]


def get_random_word(previous_word=""):
    """
    Returns a random word (<= 5 chars) from the available dataset letters.
    If no dictionary words match, synthesizes a 2-4 letter combination.
    """
    if VALID_WORDS:
        candidates = [w for w in VALID_WORDS if w != previous_word] or VALID_WORDS
        return random.choice(candidates)

    static_pool = [c for c in LETTERS if c not in MOTION_LETTERS] or LETTERS
    length = random.randint(2, min(4, len(static_pool)))
    return "".join(random.choice(static_pool) for _ in range(length))


def draw_word_hud(frame, current_word, char_idx, target, guess, streak, frames_needed, words_done):
    """Same look as letter practice (ui_style.py): the word sits where "Make: B" goes."""
    ui.draw_word(frame, "Spell: ", current_word, char_idx)
    ui.draw_progress(frame, streak / frames_needed)
    ui.draw_seen(frame, guess)
    if target in MOTION_LETTERS:
        ui.draw_tip(frame, ui.motion_tip(target))
    ui.draw_info(frame, f"Words spelled: {words_done}")
    ui.draw_help(frame, "SPACE = skip word   ESC = menu")
    return frame


def draw_success_card(frame, word):
    ui.draw_correct(frame, f"Spelled {word}!")
    return frame


landmarker = vision.HandLandmarker.create_from_options(
    vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path="hand_landmarker.task"),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
    )
)
motion_tracker = MotionRecognizer()
cap = cv2.VideoCapture(0)
start_time = time.time()
last_timestamp_ms = 0

current_word = get_random_word()
char_idx = 0
words_done = 0
streak = 0
celebrate_until = 0
just_spelled = ""

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    timestamp_ms = max(int((time.time() - start_time) * 1000), last_timestamp_ms + 1)
    last_timestamp_ms = timestamp_ms
    result = landmarker.detect_for_video(mp_image, timestamp_ms)
    h, w = frame.shape[:2]
    now = time.time()

    guess = None
    hand = result.hand_landmarks[0] if result.hand_landmarks else None
    if hand:
        ui.draw_hand(frame, hand)
        guess, _ = guess_letter(hand_to_numbers(hand), examples)

    motion_letter = motion_tracker.update(hand, time.monotonic(), w / h)
    if motion_letter:
        guess = motion_letter

    target = current_word[char_idx]

    if now < celebrate_until:
        frame = draw_success_card(frame, just_spelled)
    else:
        if target in MOTION_LETTERS:
            streak = FRAMES_NEEDED if motion_letter == target else 0
        else:
            streak = streak + 1 if guess == target else 0

        if streak >= FRAMES_NEEDED:
            streak = 0
            char_idx += 1
            if char_idx >= len(current_word):
                words_done += 1
                just_spelled = current_word
                celebrate_until = now + WORD_CELEBRATE_SECS
                current_word = get_random_word(previous_word=current_word)
                char_idx = 0

        frame = draw_word_hud(
            frame=frame,
            current_word=current_word,
            char_idx=char_idx,
            target=current_word[char_idx],
            guess=guess,
            streak=streak,
            frames_needed=FRAMES_NEEDED,
            words_done=words_done
        )

    cv2.imshow(ui.WINDOW, frame)
    key = cv2.waitKey(1) & 0xFF
    if key == 27:
        break
    elif key == ord(" "):
        current_word = get_random_word(previous_word=current_word)
        char_idx = 0
        streak = 0

cap.release()
cv2.destroyAllWindows()