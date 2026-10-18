# SignLingo design rules

Read this before adding or changing any screen. It applies to people and to AI
coding assistants alike: whatever tool you use, the app must keep one look.

## The look

SignLingo is a full camera window with the game drawn on the video (the style
of the SignLingo Mac app's letter practice):

| Slot | What goes there | Helper in `ui_style.py` |
|---|---|---|
| Top left, big white | The instruction: `Make: B`, `Spell: CAT` | `draw_target`, `draw_word` |
| Under it | Green bar that fills while the right sign is held | `draw_progress` |
| Under the bar, yellow | What the app sees: `I see: B` | `draw_seen` |
| Under that, accent | A tip, e.g. how to move for J or Z | `draw_tip`, `motion_tip` |
| Middle, big green | Success: `Correct!`, `Spelled CAT!` | `draw_correct` |
| Bottom left, accent | Progress info: score, focus count, words spelled | `draw_info` |
| Bottom line, light gray | Key reminders: `SPACE = skip   ESC = menu` | `draw_help` |
| Hand | Green dots on the 21 hand points | `draw_hand` |
| Menu | Dark background, big white title, green `[1]` keys | `draw_menu` |

Words on screen: sentence case (`Letter practice`), short, and key reminders in
the form `KEY = action`.

## Rules

1. **Never pick a font, color, size or position inside a screen.** Screens
   only call the helpers in `ui_style.py`. No `cv2.putText`, color tuples or
   pixel positions for text in game files.
2. **Need something new** (a sidebar, a settings panel, a badge)? Add one helper
   to `ui_style.py` built from the existing constants (`FONT`, `WHITE`,
   `GREEN`, `TITLE`, `SEEN`, `HELP`...), then use it. Never restyle an existing
   helper just for your screen. Changing a shared value changes every screen,
   so agree on it with the team first.
3. **One window:** always `cv2.imshow(ui.WINDOW, frame)`.
4. **Keys are the same everywhere:** `SPACE` skips, `ESC` goes back to the
   menu, letter keys pick a letter where that makes sense.
5. **J and Z** always show `ui.motion_tip(letter)` while they are the target.

## Adding a new screen (for example settings or a new game)

1. Make a new file, e.g. `settings.py`, that runs its loop at the top level
   like `practice.py` and `words.py`, and ends its loop on `ESC`.
2. Add it to `MODES` in `main.py` so the menu shows it.
3. Add its module name to `hiddenimports` in `SignLingo.spec`, or the built
   app can't open it.
4. Work on your own git branch. Before merging into `main`, post a screenshot
   so a teammate can check it against this page.

## Mac and Windows

The same code runs on both. Build on each system (PyInstaller can't build a
Windows app on a Mac or the other way round):

- Mac: `./build_app.sh` makes `dist/SignLingo.app` and `SignLingo-mac.zip`.
- Windows: `pip install pyinstaller`, then `pyinstaller --noconfirm SignLingo.spec`
  makes `dist\SignLingo\SignLingo.exe`. Zip the whole `dist\SignLingo` folder to share it.
