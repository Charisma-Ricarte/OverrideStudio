import asyncio, time, threading
from .header import make_packet, unpack_packet

MSS = 1200

class GBNTransport(asyncio.DatagramProtocol):
    def __init__(self, local_port, remote_addr=None, window_size=5, loss_wrapper=None):
        self.local_port = local_port
        self.remote_addr = remote_addr
        self.window_size = window_size
        self.loss_wrapper = loss_wrapper

        self.send_base = 0
        self.next_seq = 0
        self.send_buffer = bytearray()
        self.unacked = {}          # seq -> (packet, timestamp)
        self.dup_ack_count = {}    # seq -> duplicate ACKs
        self.timer = None
        self.timer_interval = 0.5

        self.expected_seq = 0
        self.recv_buffer = {}
        self.loop = asyncio.get_event_loop()
        self.transport = None
        self.on_receive_cb = None
        self.retransmissions = 0
        self.sack_enabled = True  # SACK-lite

    # -----------------
    def connection_made(self, transport):
        self.transport = transport
        print(f"[Transport] Listening on port {self.local_port}")

    def datagram_received(self, data, addr):
        try:
            hdr, payload = unpack_packet(data)
        except Exception as e:
            print("Bad packet:", e)
            return

        # Handle ACK
        if hdr['flags'] & 0x02:
            self.handle_ack(hdr['ack'])
            return

        seq = hdr['seq']
        # Drop duplicates
        if seq < self.expected_seq:
            ack_pkt = make_packet(1, 0x02, hdr['conn_id'], 0, self.expected_seq, 4096, b'')
            self.send_raw(ack_pkt, addr)
            return

        # Buffer out-of-order if SACK
        if self.sack_enabled and seq != self.expected_seq:
            self.recv_buffer[seq] = payload
        else:
            self.recv_buffer[seq] = payload
            while self.expected_seq in self.recv_buffer:
                chunk = self.recv_buffer.pop(self.expected_seq)
                if self.on_receive_cb:
                    self.on_receive_cb(chunk)
                self.expected_seq += len(chunk)

        # Send cumulative ACK + optional SACK
        ack_pkt = make_packet(1, 0x02, hdr['conn_id'], 0, self.expected_seq, 4096, b'')
        self.send_raw(ack_pkt, addr)

    # -----------------
    def send_raw(self, packet, addr=None):
        if self.loss_wrapper:
            self.loss_wrapper.sendto(packet, addr or self.remote_addr)
        else:
            self.transport.sendto(packet, addr or self.remote_addr)

    def send(self, data: bytes):
        self.send_buffer.extend(data)
        self.try_send()

    def try_send(self):
        while (self.next_seq - self.send_base)//MSS < self.window_size and \
              self.next_seq - self.send_base < len(self.send_buffer):
            offset = self.next_seq - self.send_base
            payload = self.send_buffer[offset:offset+MSS]
            pkt = make_packet(1, 0, 1, self.next_seq, 0, 4096, payload)
            self.send_raw(pkt)
            self.unacked[self.next_seq] = (pkt, time.time())
            self.dup_ack_count[self.next_seq] = 0
            if not self.timer:
                self.start_timer()
            self.next_seq += len(payload)

    # -----------------
    def handle_ack(self, ack_num):
        remove_seqs = [seq for seq in self.unacked if seq < ack_num]
        for seq in remove_seqs:
            del self.unacked[seq]
            del self.dup_ack_count[seq]
        # Fast retransmit on 3 duplicate ACKs
        for seq in self.unacked:
            if self.dup_ack_count[seq] >= 3:
                print(f"[Transport] Fast retransmit seq {seq}")
                pkt, _ = self.unacked[seq]
                self.send_raw(pkt)
                self.retransmissions += 1
                self.dup_ack_count[seq] = 0

        self.send_base = ack_num
        if self.send_base == self.next_seq:
            self.stop_timer()
        else:
            self.start_timer()
        self.try_send()

    def start_timer(self):
        self.stop_timer()
        self.timer = threading.Timer(self.timer_interval, self.timeout)
        self.timer.start()

    def stop_timer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def timeout(self):
        print("[Transport] Timeout! Retransmitting...")
        for seq, (pkt, _) in self.unacked.items():
            self.send_raw(pkt)
            self.unacked[seq] = (pkt, time.time())
            self.retransmissions += 1
        self.start_timer()
