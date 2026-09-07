"""
Long-running server for the CareerOps Telegram bot.

Render.com (and similar PaaS providers) require the process to bind to a
port to prove it's healthy. We start a minimal HTTP server on PORT
(default 10000) that responds with "ok" to any request, then run the
Telegram polling loop in a background thread.

The main thread is the HTTP server (so Render sees an open port and keeps
the process alive); the worker thread polls Telegram every 2 seconds for
near-instant responses.
"""
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from main import (
    TelegramSaaSClient,
    load_state,
    save_state,
    process_telegram_inbox,
    inject_save_fn,
)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"CareerOps bot is running.\n")

    def log_message(self, format, *args):
        # Suppress per-request logs; Render's own logging is enough
        return


def start_http_server(port: int):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"[HTTP] Listening on 0.0.0.0:{port}")
    server.serve_forever()


def telegram_loop(bot: TelegramSaaSClient, poll_interval: int = 2):
    """Poll Telegram every `poll_interval` seconds for instant replies."""
    print(f"[Bot] Long-poll starting — checking Telegram every {poll_interval}s")
    while True:
        try:
            state = load_state()
            inject_save_fn(save_state)
            process_telegram_inbox(bot, state)
            save_state(state)
        except Exception as e:
            print(f"[Bot] Error in cycle: {e}")
        time.sleep(poll_interval)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    bot = TelegramSaaSClient()

    # Start HTTP server in main thread (keeps Render happy)
    http_thread = threading.Thread(target=start_http_server, args=(port,), daemon=True)
    http_thread.start()

    # Run Telegram polling in worker thread
    telegram_loop(bot, poll_interval=2)
