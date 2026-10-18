"""
ui_style.py - the SignLingo look, in one place.

Every screen (menu, letter practice, word challenge, and anything added
later) draws its text, bars and hand dots with these helpers, so fonts,
sizes, colors and positions stay the same everywhere. To restyle the whole
app, change the values here, not in the screens. See DESIGN.md for the rules.

The look comes from the SignLingo Mac app (practice.py): big white
"Make: B" at the top left, a green progress bar under it, yellow "I see",
and a big green "Correct!" in the middle.
"""

import cv2

WINDOW = "SignLingo"            # every screen uses this one window
FONT = cv2.FONT_HERSHEY_SIMPLEX

# Colors are BGR (OpenCV's order: blue, green, red)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
ACCENT = (255, 200, 0)          # tips and extra info
LIGHT_GRAY = (200, 200, 200)    # help line at the bottom
GRAY = (130, 130, 130)          # letters not reached yet
BAR_EDGE = (100, 100, 100)
BACKGROUND = (24, 24, 27)       # menu background
RED = (60, 60, 255)

# Text styles: (font size, color, thickness)
TITLE = (2.0, WHITE, 5)         # "Make: B"
SEEN = (1.0, YELLOW, 2)         # "I see: B"
TIP = (0.8, ACCENT, 2)          # "Move: draw a J..."
INFO = (0.8, ACCENT, 2)         # "Focus B: 3 correct"
HELP = (0.6, LIGHT_GRAY, 2)     # key reminders
CORRECT = (2.5, GREEN, 6)       # "Correct!"

# Where things go (pixels from the top-left; bottom rows count up from the bottom)
LEFT = 20
TITLE_Y, BAR_Y, SEEN_Y, TIP_Y = 70, 95, 155, 195
BAR_W, BAR_H = 300, 20
INFO_FROM_BOTTOM, HELP_FROM_BOTTOM = 50, 20


def text(frame, words, x, y, style, color=None):
    size, default_color, thick = style
    cv2.putText(frame, words, (int(x), int(y)), FONT, size, color or default_color, thick, cv2.LINE_AA)


def text_width(words, style):
    size, _, thick = style
    return cv2.getTextSize(words, FONT, size, thick)[0][0]


def draw_target(frame, label):
    """The big instruction at the top left, e.g. "Make: B"."""
    text(frame, label, LEFT, TITLE_Y, TITLE)


def draw_word(frame, prefix, word, index):
    """A word in the title spot: finished letters green, current white, rest gray."""
    text(frame, prefix, LEFT, TITLE_Y, TITLE)
    x = LEFT + text_width(prefix, TITLE)
    for i, ch in enumerate(word):
        color = GREEN if i < index else WHITE if i == index else GRAY
        text(frame, ch, x, TITLE_Y, TITLE, color)
        x += text_width(ch, TITLE) + 6


def draw_progress(frame, fraction):
    """The green bar that fills while the right sign is held (0.0 to 1.0)."""
    fraction = min(max(fraction, 0.0), 1.0)
    cv2.rectangle(frame, (LEFT, BAR_Y), (LEFT + BAR_W, BAR_Y + BAR_H), BAR_EDGE, 2)
    cv2.rectangle(frame, (LEFT, BAR_Y), (LEFT + int(BAR_W * fraction), BAR_Y + BAR_H), GREEN, -1)


def draw_seen(frame, guess):
    text(frame, f"I see: {guess or '?'}", LEFT, SEEN_Y, SEEN)


def draw_tip(frame, tip):
    text(frame, tip, LEFT, TIP_Y, TIP)


def draw_info(frame, info):
    text(frame, info, LEFT, frame.shape[0] - INFO_FROM_BOTTOM, INFO)


def draw_help(frame, help_text):
    text(frame, help_text, LEFT, frame.shape[0] - HELP_FROM_BOTTOM, HELP)


def draw_correct(frame, message="Correct!"):
    """The big green message in the middle of the screen."""
    h, w = frame.shape[:2]
    size, color, thick = CORRECT
    while text_width(message, (size, color, thick)) > w - 40 and size > 0.8:
        size -= 0.1   # long messages shrink to fit
    style = (size, color, thick)
    text(frame, message, (w - text_width(message, style)) // 2, h // 2, style)


def draw_hand(frame, hand):
    """MediaPipe's 21 hand points as green dots."""
    h, w = frame.shape[:2]
    for p in hand:
        cv2.circle(frame, (int(p.x * w), int(p.y * h)), 4, GREEN, -1)


def motion_tip(letter):
    if letter == "J":
        return "Move: draw a J with your pinky"
    return "Move: draw a Z with your index finger"


def draw_menu(canvas, title, options, help_text):
    """A start menu: options is a list of (key, label) like ("1", "Letter practice")."""
    canvas[:] = BACKGROUND
    text(canvas, title, LEFT + 20, 110, TITLE)
    y = 200
    for key, label in options:
        text(canvas, f"[{key}]", LEFT + 20, y, SEEN, GREEN)
        text(canvas, label, LEFT + 100, y, SEEN, WHITE)
        y += 60
    draw_help(canvas, help_text)
