"""Top-level launcher used both for `python run.py` and as the PyInstaller entry
point (a plain script avoids the relative-import problems of running a package
module as __main__)."""

import sys

from macroengine.main import main

if __name__ == "__main__":
    sys.exit(main())
