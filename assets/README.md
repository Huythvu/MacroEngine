# App icon

To give `MacroEngine.exe` a custom icon:

1. Save your image here as **`assets/icon_source.png`** (a square image works best;
   `.jpg` also works). Any picture is fine.
2. Run **`build_exe.bat`** — it auto-converts your image to `assets/MacroEngine.ico`
   and embeds it in the exe.

Or convert manually at any time:

```
python tools/make_icon.py assets/icon_source.png
```

Notes:
- The image is centered and padded to a square (no stretching) and saved with all the
  sizes Windows needs (16–256 px).
- Windows caches exe icons — if the old icon lingers after a rebuild, refresh Explorer
  or rename the exe once to force an update.
