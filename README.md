# OverrideStudio

1 Team Information

Travis Arguello
Korinna Balderaz
Samuel Mohr-Sanchez
Charisma Ricarte
Josh Torres

Application Project: Mini-FTP 

2 Project Overview

A short summary of your project’s goals and what you intend to demonstrate.
Our projects's goal is to design and implement a reliable file transfer system over UDP using a custome Go-Back-N (GBN) transport ptotocol. We aim for the Mini-FTP application to allow clients to connect to a server and perofmr basic file transfer commands like LIST, GET, PUT, similar to FTP. *Hopefully we will also be able to include a GUI for the user interaction and metrics tracking but it is not our main focus.

3 Transport Protocol Design Plan

We are implementing the Go-Back-N (GBN) protocol over UDP.
Design Detials (Might be changed)
Each packet contains a custom header with:
  Sequence number
  Acknowledment number
  Packet type 
  Payload length
  Checksum for integrity verification
Timers:
  A single retransmission timer is maintained for the oldest unacknowledged packet. If the timer expires before ACK is recived, all unacknowledged packets in the window are retransmitted. 
Flow Conrol:  
  The sender maintains a fixed-sized sliding window (N), which controls the number of packets sent without waiting for ACKs. The receiver tracks the next expected sequence number.
Retransmission logic
  If a timeout occurs or if ACKs are received, the sender retransmits all outstanding packets starting from the earliest unacknowleged sequence number. 
Reliability Handling
  Packet loss: Lost packets are detected through timer expiration and retransmitted.
  Duplication: Duplicate packets are ignored based on their sequence number.
  Reordering: Out-of-order packets are discarded
  Acknowledgment: ACKs are cumulative; if an ACK is lost, the next Ack confirms receipt of earlier packets.
  
4 Application Layer Design Plan

Message Format and Commands
The Mini-FTP uses a simple command-response protocol between client and server.
LIST - Request the lisit of available files on the server.
GET <filename> - Download a file from the server.
PUT <filename> - Upload a file to the server.
Message Format
Each message is serialized as text or binary blocks with a header followed by the payload: 
[HEADER][PAYLOAD]
  The header defines the command type and metadata
  The payload cotains either the command string or file data
  End-of-transfer markers to indicate completion
*GUI Integration
The GUI would provide buttons for each command and a file selector for uploads/downloads. It could also display progress bars and logs transmission status to make it easier to visualize the reliability layer in action. 

5 Testing and Metrics Plan

Testing Setup 
Testing will be done under three network profiles:
  Clean Network: No packet loss (Baseline throughput and correstness)
  Random Loss: Simulated packet loss at random intervals (test retransmission correctness)
  Bursty Loss: Groups of packets are dropped in bursts (test robustness under poor conditions)
Metrics to Measure
Throughput: Number of bytes successfully delivered per second.
Latency: Time taken to transfer files.
Retransmissions: Count of packets resent due to loss or timeout.
Dropped Frames: NUmber of lost of discarded packets.
Stall Time: Periods where the sender is idle waiting for ACKs.
(Results could be visualized in the GUI* or logged for analysis)

6 Progress Summary (Midterm Status)

Implemented So Far*
(Need to be reworked before upload to github, We have them locally but after some test relized that it is not working properly)
GBN sender/receiver skeleton implemented.
Header structure defined with sequence numbers and checksums.
Basic packet send/receive logic operational over UDP.
FTP-like commands (LIST, GET, PUT) stubbed.
Initial client-server communication functional.
Remaining Task 
  Finalize retransmission logic for corner cases (bursty loss).
  Implement timeout tuning and dynamic window size adjustments.
  Complete file handling for PUT/GET operations with integrity checks.
  *Implement A GUI
Evidence of Progress
  Working prototypes of server and client 
