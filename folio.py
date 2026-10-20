#!/usr/bin/env python3
"""Run Folio from this folder:  python3 folio.py [file.folio]"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from folio.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
