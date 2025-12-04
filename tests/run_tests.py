# test/run_test.py
import asyncio
import json
import os
import time
from app.ftp_client import FTPClient
from app.ftp_server import main as server_main

ROOT = os.path.dirname(os.path.dirname(__file__))
TEST_FILES_DIR = os.path.join(ROOT, "test_files")
os.makedirs(TEST_FILES_DIR, exist_ok=True)

async def run_profile(profile_name, profile_config):
    print(f"\n=== Running profile: {profile_name} ===")
    # Start server in background
    server_task = asyncio.create_task(server_main())
    await asyncio.sleep(1.0)  # give server a moment to bind

    # Create client with requested loss rate
    client = FTPClient(loss_rate=profile_config.get('loss_rate', 0.0))
    await client.start()

    # Create a test file to upload (256 KB)
    test_file = os.path.join(TEST_FILES_DIR, f"upload_{profile_name}.bin")
    with open(test_file, "wb") as f:
        f.write(os.urandom(256 * 1024))

    remote_name = f"test_{profile_name}.bin"

    # Run PUT with resume enabled
    start_time = time.time()
    await client.put_file(test_file, remote_name, resume=True)
    put_duration = time.time() - start_time

    # Run GET with resume enabled
    download_file = os.path.join(TEST_FILES_DIR, f"download_{profile_name}.bin")
    start_time = time.time()
    await client.get_file(remote_name, download_file, resume=True)
    get_duration = time.time() - start_time

    metrics = client.metrics.report()
    print(f"PUT duration: {put_duration:.2f}s")
    print(f"GET duration: {get_duration:.2f}s")
    print(f"Metrics: {metrics}")

    # Verify integrity
    with open(test_file, "rb") as f1, open(download_file, "rb") as f2:
        original = f1.read()
        downloaded = f2.read()
        if original == downloaded:
            print("[PASS] File integrity verified")
        else:
            print("[FAIL] File mismatch!")

    # Cancel server
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(0.2)

async def main():
    # profiles.json is expected in the test folder next to this script
    cfg_path = os.path.join(os.path.dirname(__file__), "profiles.json")
    if not os.path.exists(cfg_path):
        print("profiles.json not found in test/ — create one similar to the sample.")
        return
    with open(cfg_path, "r") as f:
        profiles = json.load(f)
    for name, cfg in profiles.items():
        await run_profile(name, cfg)

if __name__ == "__main__":
    asyncio.run(main())
