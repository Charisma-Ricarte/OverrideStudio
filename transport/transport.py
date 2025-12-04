# transport/transport.py
import asyncio
import time
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
        self.unacked = {}

        self.last_ack = 0
        self.dup_ack_counter = 0

        self.timer_handle = None
        self.timer_interval = 0.45

        self.expected_seq = 0
        self.recv_buffer = {}
        self.loop = asyncio.get_event_loop()

        self.transport = None
        self._cb = None        # SAFE callback, private

        self.retransmissions = 0
        self.sack_enabled = True


    # --------------------------
    # SAFE CALLBACK SYSTEM
    # --------------------------
    def set_callback(self, cb):
        """Register receive callback."""
        if callable(cb):
            self._cb = cb
        else:
            print("[Transport] Warning: Tried to set non-callable callback")
            self._cb = None

    def clear_callback(self):
        self._cb = None

    def _deliver(self, chunk):
        """Safely call the registered callback."""
        cb = self._cb
        if cb is None:
            # No callback registered
            return

        try:
            result = cb(chunk)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
        except Exception as e:
            print(f"[Transport] Callback error: {e}")


    # --------------------------
    def connection_made(self, transport):
        self.transport = transport
        print(f"[Transport] Listening on port {self.local_port}")


    def datagram_received(self, data, addr):
        if self.remote_addr is None:
            self.remote_addr = addr

        try:
            hdr, payload = unpack_packet(data)
        except Exception as e:
            print("[Transport] Bad packet:", e)
            return

        # ACK packet?
        if hdr["flags"] & 0x02:
            self.handle_ack(hdr["ack"])
            return

        seq = hdr["seq"]

        # Duplicate old packet → re-ACK
        if seq < self.expected_seq:
            ack_pkt = make_packet(1, 0x02, hdr["conn_id"], 0, self.expected_seq, 0, b'')
            self.send_raw(ack_pkt, addr)
            return

        # Buffer it
        self.recv_buffer[seq] = payload

        # Deliver in-order
        while self.expected_seq in self.recv_buffer:
            chunk = self.recv_buffer.pop(self.expected_seq)
            self._deliver(chunk)
            self.expected_seq += len(chunk)

        # Send ACK after delivering
        ack_pkt = make_packet(1, 0x02, hdr["conn_id"], 0, self.expected_seq, 0, b'')
        self.send_raw(ack_pkt, addr)


    # --------------------------
    def send_raw(self, packet, addr=None):
        addr = addr or self.remote_addr
        if addr is None:
            return

        if self.loss_wrapper:
            self.loss_wrapper.sendto(packet, addr)
        else:
            self.transport.sendto(packet, addr)


    # --------------------------
    def send(self, data: bytes):
        self.send_buffer.extend(data)
        self.try_send()


    def try_send(self):
        while (self.next_seq - self.send_base) // MSS < self.window_size and \
              self.next_seq - self.send_base < len(self.send_buffer):

            offset = self.next_seq - self.send_base
            payload = self.send_buffer[offset: offset + MSS]

            pkt = make_packet(1, 0, 1, self.next_seq, 0, 0, payload)
            self.send_raw(pkt)

            self.unacked[self.next_seq] = (pkt, time.time())

            if not self.timer_handle:
                self.start_timer()

            self.next_seq += len(payload)


    # --------------------------
    def handle_ack(self, ack_num):
        if ack_num == self.last_ack:
            self.dup_ack_counter += 1
        else:
            self.last_ack = ack_num
            self.dup_ack_counter = 0

        for seq in list(self.unacked.keys()):
            if seq < ack_num:
                self.unacked.pop(seq, None)

        # Fast retransmit
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


    # --------------------------
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
