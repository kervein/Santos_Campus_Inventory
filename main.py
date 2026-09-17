"""Application launcher for EquipTrack.

The complete Flask application lives in app.py. This module remains the
documented entry point so the project can be started with ``python main.py``.
"""

import threading
import webbrowser

from app import app, prepare_database


if __name__ == "__main__":
    prepare_database()
    browser_timer = threading.Timer(
        1.0, lambda: webbrowser.open_new("http://127.0.0.1:5000")
    )
    browser_timer.daemon = True
    browser_timer.start()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)