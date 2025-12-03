import statistics
import time

class Metrics:
    def __init__(self):
        self.delays = []
        self.bytes_sent = 0
        self.retransmissions = 0

    def record_delay(self, delay_ms):
        self.delays.append(delay_ms)

    def record_bytes(self, n):
        self.bytes_sent += n

    def record_retransmission(self, n=1):
        self.retransmissions += n

    def report(self):
        if not self.delays:
            p95 = 0
        else:
            p95 = statistics.quantiles(self.delays, n=100)[94]
        return {
            "total_bytes": self.bytes_sent,
            "retransmissions": self.retransmissions,
            "avg_latency_ms": statistics.mean(self.delays) if self.delays else 0,
            "p95_latency_ms": p95
        }
