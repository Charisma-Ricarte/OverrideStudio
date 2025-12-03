import asyncio, json, os, time
from transport.lossy_shim import LossySocket
from app.ftp_client import FTPClient
from app.ftp_server import main as start_server

TEST_FILES_DIR = "./tests/files"
os.makedirs(TEST_FILES_DIR, exist_ok=True)

async def run_profile(profile_name, profile_config):
    print(f"\n=== Running profile: {profile_name} ===")
    # Start server in background
    server_task = asyncio.create_task(start_server())

    await asyncio.sleep(1)  # let server start

    client = FTPClient(loss_rate=profile_config['loss_rate'])
    await client.start()

    # Create a test file to upload
    test_file = os.path.join(TEST_FILES_DIR, f"upload_{profile_name}.bin")
    with open(test_file, "wb") as f:
        f.write(os.urandom(256*1024))  # 256 KB test file

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
    except:
        pass

async def main():
    with open("tests/profiles.json") as f:
        profiles = json.load(f)
    for name, cfg in profiles.items():
        await run_profile(name, cfg)

if __name__ == "__main__":
    asyncio.run(main())
