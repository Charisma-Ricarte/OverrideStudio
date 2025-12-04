# Mini-FTP: Reliable File Transfer over Custom Go-Back-N Transport
A simplified FTP system built on top of a custom reliable UDP transport layer.
Supports LIST, GET, PUT, resume, fast retransmit, SACK-lite, metrics, and GUI client.

---

## Features

### ✔ File Transfer Commands
- `LIST` — list files on server  
- `GET <file>` — download a file  
- `PUT <file>` — upload a file  
- Supports files up to **25 MB**

### ✔ Transport Layer (Custom Reliable UDP)
- Go-Back-N sliding window  
- MSS = 1200 bytes  
- Per-packet ACK  
- Fast retransmit on 3 duplicate ACKs  
- Optional SACK-lite  
- Timeout-based retransmissions  
- Ordered delivery  
- Handles packet loss, jitter, and reordering

### ✔ File Integrity
- Chunking (16 KB)
- Per-chunk CRC32 checksums
- Corruption detection & recovery

### ✔ Metrics Collected
- Completion time (PUT / GET)
- Goodput (bytes delivered to app)
- Retransmissions per KB
- Checksum errors detected
- 95th-percentile chunk delivery delay

### ✔ Bonus Features Implemented
- Resume from offset (**yes**)
- Fast retransmit (**yes**)
- SACK-lite (**yes**)
- GUI client (**yes**)
- Directory listing sidebar (**yes**)
- (Optional) File deletion

---

## Project Structure
app/
  ftp_server.py
  ftp_client.py
  fileops.py
gui/
  main.py
  widgets.py
transport/
  transport.py
  header.py
server_files/
server_storge/
tools/
  metrics.py
  utils.py
test/
profiles.json
run_test.py
tests/
README.md


---

## Installation

### 1. Clone the repo
git clone https://github.com/Charisma-Ricarte/OverrideStudio/tree/UPDATED
cd OverrideStudio

### 2. Create and activate a virtual environment

#### Windows:
python -m venv venv
venv\Scripts\activate

#### Mac / Linux:
python3 -m venv venv
source venv/bin/activate
python3 -m venv venv

### 3. Install required packages
pip install -r requirements.txt
pip install PySide6-stubs
---

## Running the Program

### Start the FTP Server
Run in one terminal:
python -m app.ftp_server
Output: [Transport] Listening on port 9000            
[Server] Running...
---

### Start the Client
In a second terminal:
python -m gui.main




This opens the Mini-FTP GUI.

---

### Using the GUI
Click LIST to view server files

Click Select Local File to pick a file

Enter a remote filename (or leave to auto-fill)

Click PUT to upload

Click GET to download

Click DELETE to remove file from server

---

## Running Automated Tests
This runs:
- clean network
- random loss
- bursty loss  
and verifies file integrity.

