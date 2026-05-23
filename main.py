import sys
import os

# Make sure we can find our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db
from tracker import AppTracker
from ui import UsageApp


def main():
    init_db()
    tracker = AppTracker()
    tracker.start()

    app = UsageApp(tracker)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
