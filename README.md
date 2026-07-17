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
- **Compact view toggle** — a held key becomes hundreds of repeated events and mouse
  motion becomes thousands of samples. Tick **Compact view** to collapse each run of
  same-kind events into a single row (e.g. `⊞ Hold key 'a' ×512`), so a simple macro
  reads as a short list. It's display-only — deleting/reordering a collapsed row acts
  on the whole run, and playback is byte-for-byte identical. Untick it to see every
  individual event.
- **Save / load** macros and trigger sets as JSON.
- **Vision triggers** — watch a screen region and fire an action:
  - **Template match** — snapshot a reference image (e.g. a buff icon); fire when it
    is **present** or **absent** (absent = "buff ran out").
  - **Color ratio** — measure how much of a region falls inside an HSV color band
    (e.g. red); fire when the ratio goes **above**/**below** a threshold (HP low).
  - Action = press a key, or run a saved macro. Each trigger has a **cooldown** so it
    doesn't fire every poll tick.
- **Routines** — chain small recorded macros into a full sequence (e.g. a daily):
  play section A → wait → *wait until the screen shows X* → play section B, with
  per-step vision timeouts, reordering, per-step enable, looping, and save/load.
- **Buff groups** — watch one region (a buff bar) for **several buff icons at once**.
  Each icon is searched for *anywhere* in the region, so it keeps working even when
  buffs **shift or reorder** as they expire. Per buff: a captured icon, a
  present/absent condition, its own key/macro, and a cooldown. Includes a **thumbnail
  preview** and a **Test** readout (detected? + match score) so you can verify before
  relying on it.
- **Auto inputs (timed repeaters)** — a simple auto-clicker / auto-presser: fire a
  key/combo, **type a string**, a click, or a whole macro on a repeating **interval**
  (with optional random **jitter**). Independent of recording — several can run at
  once, each on its own timer.
- **Keys & combos everywhere** — every action-key field (triggers, buffs, auto inputs)
  takes a full keystroke: single keys, special keys (Esc/Backspace/F-keys), lone
  modifiers (Alt/Ctrl), and combos (Ctrl+C, Alt+F4) — captured by pressing them.
- **No typing coordinates** — *Add Click*, click positions, and region/trigger setup
  let you pick positions by clicking directly on the screen.

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

## Build a double-clickable `.exe` (no VS Code needed)

On **Windows**, just **double-click `build_exe.bat`** in Explorer. It installs the
dependencies, bundles everything with [PyInstaller](https://pyinstaller.org/), and
produces a single file:

```
dist\MacroEngine.exe
```

Running it from a **terminal** instead? The command depends on which shell you have:

```powershell
.\build_exe.bat     # PowerShell (VS Code's default) — the .\ is required
```
```bat
build_exe.bat       # Command Prompt (cmd.exe)
```

(PowerShell won't run a script from the current folder by name without the leading
`.\` — that's normal, not an error.)

Double-click that to launch the app — no Python or editor required. Right-click ▸
**Run as administrator** if you need to control games that run elevated.

> The `.exe` must be built **on Windows** — PyInstaller is not a cross-compiler, so it
> can't be produced from macOS/Linux. Build it once per machine (or share the produced
> `dist\MacroEngine.exe`).

### Custom exe icon (optional)

Drop any image at **`assets/icon_source.png`** and `build_exe.bat` will automatically
convert it to a proper multi-size `.ico` and use it as the exe's icon. To convert
manually: `python tools/make_icon.py assets/icon_source.png`. See `assets/README.md`.

### Recorder
1. Set **Loops** (0 = forever) and optionally untick *Record mouse moves*.
2. Click **Record** (or press `F9`), perform your inputs, then `F9` again to stop.
3. Click **Play** (or `F10`) to replay. `Esc` stops immediately.
4. Edit rows in the table — delete/reorder, edit a delay inline, **Add Key Tap…**, or
   **Add Click (pick on screen)…** which lets you *click where you want the macro to
   click* instead of typing coordinates. Select rows and **Copy** (`Ctrl+C`) to copy
   them — as readable text for any editor, and pasteable back in with **Paste**
   (`Ctrl+V`) to duplicate steps. Use **Macro ▸ Save As…** to keep it.

### Vision triggers (single watcher)
1. In the panel click **Add Trigger**.
2. **Select Region…** and drag a rectangle over the area to watch (e.g. the HP bar).
3. Choose detection:
   - *Template* → **Capture Snapshot from Region** (a **thumbnail of the captured
     reference** appears), then pick **absent**/**present**.
   - *Color* → set the HSV band + ratio threshold and **above**/**below**.
   Use **Test now** in the *Live preview & test* box to grab the region right now —
   it shows the live image and reports whether the condition fires (present/absent +
   match score for template, or the color match ratio) so you can confirm before
   relying on it.
4. Choose the action — press a key/combo, run a macro, or **Click on the found
   image** (template mode: left-clicks wherever the reference currently is inside
   the region, even if it moves) — and a cooldown. The key field has a **Capture**
   button — press the actual key/combo (incl. Esc, Alt, Ctrl+C…) instead of typing
   its name.
5. Click **Start monitoring**. `Esc` stops it.

### Buff groups (watch several buffs on one bar)
Best when your buff icons **shift/reorder** as buffs expire — each icon is matched
*anywhere* inside the region.
1. In the panel click **Add Buff Group**, give it a name, and **Select buff-bar
   region…** — drag a box around the *whole* buff bar.
2. Click **Add buff…**, then **Box the buff icon on screen…** and drag a tight box
   around **one** buff icon (while that buff is active). You'll see a thumbnail.
3. Set the buff's **Condition** (*Absent → act* = react when the buff runs out;
   *Present → act* = react when it appears), its **key/macro**, **cooldown**, and
   optionally tune the **match threshold**. Hit **Test now** — it reports
   *DETECTED ✓ / not found ✗* with a score so you can confirm it works.
4. Repeat **Add buff…** for each buff. Use **Test all** to check them together.
5. **OK**, then **Start monitoring**. When a watched buff disappears (or appears), its
   key/macro fires, throttled by its cooldown. `Esc` stops.

Save/restore your triggers *and* buff groups together via **Watchers ▸ Save As… /
Open…**.

### Routines (chain small macros into a daily)
Recording a whole daily in one take is hard — record **small sections** instead and
chain them on the **Routine** tab:
1. Record and save each section as its own macro (e.g. `walk-to-npc.json`,
   `turn-in.json`).
2. On the **Routine** tab, build the step list top-to-bottom:
   - **+ Macro…** — play a saved macro file (optionally loop it ×N). Steps reference
     the *file*, so re-recording a section automatically updates the routine.
   - **+ Wait…** — pause N seconds (± jitter) before the next step.
   - **+ Vision wait…** — poll a screen region until a condition holds (icon
     present/absent or color ratio — same editor as vision triggers, including
     capture, thumbnail, and **Test now**). Each has a **timeout** that either
     **stops the routine** (it names the failing step) or **continues anyway**.
     Tick **Click where the image was found** to left-click the reference once it
     appears — e.g. *wait for the "Accept" button, then click it* — even if the
     button isn't always in the same place.
3. Reorder with Move Up/Down, untick a step to skip it, set routine **Loops**
   (0 = forever), then **Run routine**. The current step highlights while running;
   `Esc` stops everything instantly.
4. **Save to library** — the routine is stored in your per-user routines folder and
   shown in the **Saved routines** list on the left. Select one and **Open** (or
   double-click) to load it, or **Open & Run** to launch it in one click. **Routine ▸
   Save As… / Open…** still lets you use arbitrary file locations.

Each tab has a one-line explainer at the top and a tooltip on hover describing what
it's for.

### Auto inputs (timed repeaters)
An **auto-clicker / auto-presser**: fire a single action on a repeating timer,
independent of recorded macros and vision. Several can run at once, each on its own
interval.
1. In the **Auto inputs** panel click **Add**.
2. Pick the action:
   - **Press key / combo** — click **Capture** and press the key you want; works for
     letters/digits, special keys (**Esc, Backspace, Tab, Enter, F1–F12**), lone
     modifiers (**Alt, Ctrl, Shift**), and combos (**Ctrl+C, Alt+F4**). You can also
     type the spec directly, e.g. `ctrl+shift+a`.
   - **Type text** — types a whole string in one go (e.g. `123asd`, or a chat message).
   - **Click at position** (pick the spot on screen — no typing coordinates).
   - **Run macro**.
3. Set the **Interval** (seconds; supports fractions like `0.1`) and optional
   **Jitter ±** — a random amount added to each interval so the timing isn't perfectly
   robotic.
4. Click **Start auto inputs**. `Esc` stops them (and everything else) instantly.

Every list row (triggers, buff groups, individual buffs inside a group, auto inputs)
has a **checkbox** — untick it to pause just that item without deleting it. Toggling
works live, even while monitoring / auto inputs are running.

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
