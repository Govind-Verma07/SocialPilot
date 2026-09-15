import subprocess
import time
import re
import os

print("Starting Pinggy SSH tunnel...")
cmd = ["ssh", "-p", "443", "-R0:localhost:8000", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30", "a.pinggy.io"]

log_file = open("pinggy.log", "w", encoding="utf-8")
proc = subprocess.Popen(
    cmd,
    stdout=log_file,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
)

print(f"Pinggy process PID: {proc.pid}. Waiting for tunnel URL...")
found_url = None
for _ in range(30):
    time.sleep(1)
    if os.path.exists("pinggy.log"):
        with open("pinggy.log", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            # Look for https://...pinggy... or similar
            matches = re.findall(r"https://[a-zA-Z0-9\.\-]+\.run\.pinggy[a-zA-Z0-9\.\-]+", content)
            if not matches:
                matches = re.findall(r"https://[a-zA-Z0-9\.\-]+\.pinggy\.[a-z]+", content)
            if matches:
                found_url = matches[0]
                print(f"Found Pinggy URL: {found_url}")
                break
            # Also check any https url
            any_https = re.findall(r"https://[a-zA-Z0-9\.\-]+\.[a-zA-Z]{2,}", content)
            if any_https:
                print(f"Output: {content[:300]}")

if found_url:
    print(f"SUCCESS: {found_url}")
else:
    print("Could not find Pinggy URL yet. Contents of pinggy.log:")
    with open("pinggy.log", "r", encoding="utf-8", errors="ignore") as f:
        print(f.read())
