import random, threading

class LossySocket:
    def __init__(self, sock, loss_rate=0.05, burst=False, max_delay_ms=50):
        self.sock = sock
        self.loss_rate = loss_rate
        self.burst = burst
        self.max_delay_ms = max_delay_ms

    def sendto(self, data, addr):
        if random.random() < self.loss_rate:
            return  # drop packet
        delay = random.uniform(0, self.max_delay_ms) / 1000
        threading.Timer(delay, lambda: self.sock.sendto(data, addr)).start()
