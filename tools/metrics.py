# tools/metrics.py
import statistics

class Metrics:
    def __init__(self):
        self.delays = []
        self.bytes_sent = 0
        self.retransmissions = 0
        self.checksum_errors = 0
        self.goodputs = []

    def record_delay(self, delay_ms):
        self.delays.append(delay_ms)

    def record_bytes(self, n):
        self.bytes_sent += n

    def record_retransmissions(self, n=1):
        self.retransmissions += n

    def record_checksum_errors(self, n=1):
        self.checksum_errors += n

    def record_goodput(self, bps):
        self.goodputs.append(bps)

    def report(self):
        if not self.delays:
            p95 = 0
            avg = 0
        else:
            # use statistics.quantiles for p95
            qs = statistics.quantiles(self.delays, n=100)
            p95 = qs[94] if len(qs) >= 95 else max(self.delays)
            avg = statistics.mean(self.delays)
        return {
            "total_bytes": self.bytes_sent,
            "retransmissions": self.retransmissions,
            "avg_latency_ms": avg,
            "p95_latency_ms": p95,
            "checksum_errors": self.checksum_errors,
            "avg_goodput_Bps": statistics.mean(self.goodputs) if self.goodputs else 0
        }
