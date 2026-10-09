# --------------------------------------------------------------------------
# Copyright (c) 2026 SUDEEPBOTS. All Rights Reserved.
# PulseMusic — High-Performance Telegram Voice Chat Music & Video Engine
# Licensed under the MIT License. See LICENSE in the project root for details.
# --------------------------------------------------------------------------

import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"PulseMusic is running successfully!")

def keep_alive():
    def run():
        server_address = ('', int(os.environ.get("PORT", 8080)))
        httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
        httpd.serve_forever()
    
    server = threading.Thread(target=run, daemon=True)
    server.start()

def ping_server():
    time.sleep(10)
    while True:
        url = os.environ.get("PING_URL") or os.environ.get("RENDER_URL")
        if url:
            try:
                requests.get(url, timeout=10)
            except Exception:
                pass
        time.sleep(300) # Ping every 5 minutes

def keep_alive_ping():
    keep_alive()
    ping_thread = threading.Thread(target=ping_server, daemon=True)
    ping_thread.start()
