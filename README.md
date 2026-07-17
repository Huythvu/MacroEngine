# MacroEngine

A Windows macro recorder with **screen-vision triggers** — a Jitbit-style macro
tool combined with lightweight, "cheat-engine"-flavored automation that reacts to
what's on screen.

Record a sequence of keyboard/mouse inputs, edit it, and loop it. Then, separately,
define **watchers** over regions of the screen that fire an input when a condition
is met — e.g. *"when the buff icon disappears, press `1`"* or *"when the HP bar turns
red, press the potion key."*

> Intended for personal automation in single-player / offline games and everyday
> desktop tasks. Respect the terms of service of any online game — many prohibit
> automation.

## Features (Phase 1)

- **Macro recorder** — records keyboard + mouse (moves, clicks, scroll) with real
  timing via [`pynput`](https://pynput.readthedocs.io/). Mouse-move recording is
  throttled and can be turned off so keyboard-only macros stay clean.
- **Playback with looping** — replay a macro N times, or `0` = loop forever until you
  hit the panic key.
- **Editable timeline** — a table of every event: delete, reorder (move up/down),
  insert key taps / clicks, and edit each event's delay inline.
- **Save / load** macros and trigger sets as JSON.
- **Vision triggers** — watch a screen region and fire an action:
  - **Template match** — snapshot a reference image (e.g. a buff icon); fire when it
    is **present** or **absent** (absent = "buff ran out").
  - **Color ratio** — measure how much of a region falls inside an HSV color band
    (e.g. red); fire when the ratio goes **above**/**below** a threshold (HP low).
  - Action = press a key, or run a saved macro. Each trigger has a **cooldown** so it
    doesn't fire every poll tick.

## Global hotkeys

Work even when the game has focus:

| Key   | Action                                   |
|-------|------------------------------------------|
| `F9`  | Start / stop recording                   |
| `F10` | Start / stop playback                    |
| `Esc` | **Panic stop** — halt playback + monitoring |

## Install

Requires **Python 3.10+** on **Windows**.

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m macroengine.main
```

### Recorder
1. Set **Loops** (0 = forever) and optionally untick *Record mouse moves*.
2. Click **Record** (or press `F9`), perform your inputs, then `F9` again to stop.
3. Click **Play** (or `F10`) to replay. `Esc` stops immediately.
4. Edit rows in the table; use **Macro ▸ Save As…** to keep it.

### Vision triggers
1. In the **Vision triggers** panel click **Add**.
2. **Select Region…** and drag a rectangle over the area to watch (e.g. the buff icon
   or the HP bar).
3. Choose detection:
   - *Template* → **Capture Snapshot from Region**, then pick **absent**/**present**.
   - *Color* → set the HSV band + ratio threshold and **above**/**below**.
4. Choose the action (press a key, or run a macro) and a cooldown.
5. Click **Start monitoring**. `Esc` stops it.

## Windows notes / caveats

- **Run as Administrator** to record/inject input for games that run elevated —
  otherwise the OS blocks input into that window.
- `mss` **cannot capture fullscreen-exclusive DirectX**. Run such games in
  **borderless / windowed** mode so the screen grab works.
- Screen coordinates are global. Multi-monitor is supported for region selection, but
  the single primary monitor is the best-tested path.

## Project layout

```
macroengine/
  main.py            entry point
  models/            Event, Macro, Trigger + JSON (no GUI/pynput deps)
  core/              recorder, player, hotkeys, key<->string helpers
  vision/            capture (mss), detector (opencv), monitor loop
  gui/               PySide6 main window, editable table, region selector, dialog
tests/               headless tests for models + vision detector
```

## Testing

The pure logic (serialization + image detection) is covered headlessly:

```bash
pip install pytest numpy opencv-python
python -m pytest tests/ -q
```

Recording, playback, hotkeys and screen capture are OS-level and must be verified
manually on Windows (record into Notepad and replay; snapshot a buff icon and cover
it to fire a key; etc.).

## Roadmap

- **Memory-reading cheat engine** (deferred): read a game process's memory via
  `pymem` to watch a value (HP, buff timer) and react. The trigger system is already a
  *condition → action* design, so this slots in as another condition kind without
  reworking actions or the monitor loop.
