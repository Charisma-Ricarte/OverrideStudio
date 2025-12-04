# transport/transport.py
import asyncio
import time
from .header import make_packet, unpack_packet

MSS = 1200
CMD_FLAG = 0x01
ACK_FLAG = 0x02

class GBNTransport(asyncio.DatagramProtocol):
    """
    Go-Back-N style transport using UDP datagrams.
    Application registers callbacks that accept (hdr, payload).
    Use send(data) for data payloads and send_control(data) for control messages.
    """

    def __init__(self, local_port, remote_addr=None, window_size=5, loss_wrapper=None):
        self.local_port = local_port
        self.remote_addr = remote_addr
        self.window_size = window_size
        self.loss_wrapper = loss_wrapper

        # sending state (byte-oriented)
        self.send_base = 0
        self.next_seq = 0  # next sequence number (byte offset)
        self.send_buffer = bytearray()
        self.unacked = {}  # seq -> (packet, timestamp)

        # ack/dup detection
        self.last_ack = 0
        self.dup_ack_counter = 0

        self.timer_handle = None
        self.timer_interval = 0.45

        # receiving state
        self.expected_seq = 0
        self.recv_buffer = {}  # seq -> payload bytes

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()

        self.transport = None

        # FIFO callback queue; callbacks must accept (hdr, payload)
        self._cb_queue = []

        self.retransmissions = 0
        self.sack_enabled = True

    # ------------------ callback API ------------------
    def set_callback(self, cb):
        """Register a callback that accepts (hdr, payload)."""
        if callable(cb):
            self._cb_queue.append(cb)
        else:
            print("[Transport] set_callback: non-callable ignored")

    def clear_callbacks(self):
        self._cb_queue = []

    def _deliver(self, hdr, chunk: bytes):
        """Deliver to first registered callback (FIFO)."""
        if not self._cb_queue:
            return
        cb = self._cb_queue[0]
        try:
            res = cb(hdr, chunk)
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)
        except Exception as e:
            print(f"[Transport] Callback error: {e}")

    # ------------------ lifecycle ------------------
    def connection_made(self, transport):
        self.transport = transport
        print(f"[Transport] Listening on port {self.local_port}")

    def datagram_received(self, data: bytes, addr):
        # set remote if unknown
        if self.remote_addr is None:
            self.remote_addr = addr

        try:
            hdr, payload = unpack_packet(data)
        except Exception:
            # Not our header format -> deliver as raw payload with hdr=None
            self._deliver(None, data)
            return

        # If ACK flag => process ack
        if hdr["flags"] & ACK_FLAG:
            self.handle_ack(hdr["ack"])
            return

        # Normal payload packet: buffer + deliver in-order
        seq = hdr["seq"]
        if seq < self.expected_seq:
            # duplicate, re-ack
            ack_pkt = make_packet(0, ACK_FLAG, hdr["conn_id"], 0, self.expected_seq, 0, b'')
            self.send_raw(ack_pkt, addr)
            return

        self.recv_buffer[seq] = payload
        # deliver all in-order chunks
        while self.expected_seq in self.recv_buffer:
            chunk = self.recv_buffer.pop(self.expected_seq)
            self._deliver(hdr, chunk)
            self.expected_seq += len(chunk)

        # send cumulative ACK
        ack_pkt = make_packet(0, ACK_FLAG, hdr["conn_id"], 0, self.expected_seq, 0, b'')
        self.send_raw(ack_pkt, addr)

    # ------------------ sending ------------------
    def send_raw(self, packet: bytes, addr=None):
        addr = addr or self.remote_addr
        if addr is None:
            # cannot send without remote address
            return
        if self.loss_wrapper:
            self.loss_wrapper.sendto(packet, addr)
        else:
            self.transport.sendto(packet, addr)

    def send_control(self, data: bytes):
        """
        Send a control message reliably — directly craft a packet and record it for retransmit.
        Uses next_seq as sequence number and increments by len(data).
        """
        seq = self.next_seq
        pkt = make_packet(0, CMD_FLAG, 1, seq, 0, len(data), data)
        self.send_raw(pkt)
        self.unacked[seq] = (pkt, time.time())
        # advance next_seq by len(data) (control considered part of byte stream)
        self.next_seq += len(data)
        if not self.timer_handle:
            self.start_timer()

    def send(self, data: bytes):
        """
        Application send: append to send buffer and let try_send packetize into MSS chunks.
        These packets use flags=0 (data).
        """
        self.send_buffer.extend(data)
        self.try_send()

    def try_send(self):
        while (self.next_seq - self.send_base) // MSS < self.window_size and \
                self.next_seq - self.send_base < len(self.send_buffer):
            offset = self.next_seq - self.send_base
            payload = self.send_buffer[offset: offset + MSS]
            seq = self.next_seq
            pkt = make_packet(0, 0, 1, seq, 0, len(payload), payload)
            self.send_raw(pkt)
            self.unacked[seq] = (pkt, time.time())
            if not self.timer_handle:
                self.start_timer()
            self.next_seq += len(payload)

    # ------------------ ACK handling / timer ------------------
    def handle_ack(self, ack_num):
        if ack_num == self.last_ack:
            self.dup_ack_counter += 1
        else:
            self.last_ack = ack_num
            self.dup_ack_counter = 0

        for seq in list(self.unacked.keys()):
            if seq < ack_num:
                self.unacked.pop(seq, None)

        if self.dup_ack_counter >= 3:
            seqs = list(self.unacked.keys())
            if seqs:
                seq0 = seqs[0]
                pkt, _ = self.unacked[seq0]
                self.send_raw(pkt)
                self.retransmissions += 1
            self.dup_ack_counter = 0

        self.send_base = ack_num

        if self.send_base == self.next_seq:
            self.stop_timer()
        else:
            self.start_timer()

        self.try_send()

    def start_timer(self):
        self.stop_timer()
        self.timer_handle = self.loop.call_later(
            self.timer_interval,
            lambda: asyncio.create_task(self.timeout())
        )

    def stop_timer(self):
        if self.timer_handle:
            self.timer_handle.cancel()
            self.timer_handle = None

    async def timeout(self):
        for seq in list(self.unacked.keys()):
            pkt, _ = self.unacked[seq]
            self.send_raw(pkt)
            self.unacked[seq] = (pkt, time.time())
            self.retransmissions += 1
        self.start_timer()
