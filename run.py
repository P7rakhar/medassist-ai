"""Start MedAssist AI:  python run.py   ->  opens http://127.0.0.1:8000"""
import os
import threading
import webbrowser

import uvicorn

HOST, PORT = "127.0.0.1", int(os.environ.get("PORT", 8000))

if __name__ == "__main__":
    threading.Timer(1.5, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    print(f"\n  MedAssist AI running at http://{HOST}:{PORT}   (API docs: /docs)   Ctrl+C to stop\n")
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=False)
