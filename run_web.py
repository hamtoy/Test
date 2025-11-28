"""Run the Gemini QA System Web Server."""

import webbrowser
from threading import Timer

import uvicorn


def open_browser() -> None:
    """Open browser after server starts."""
    webbrowser.open("http://localhost:8000/qa")


if __name__ == "__main__":
    # Open browser after 1 second delay
    Timer(1.0, open_browser).start()

    # Run the server
    uvicorn.run("src.web.api:app", host="0.0.0.0", port=8000, reload=True)
