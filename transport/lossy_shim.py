# transport/lossy_shim.py
import random

class LossySocket:
    def __init__(self, sock, loss_rate=0.0):
        self.sock = sock
        self.loss_rate = loss_rate

    def sendto(self, packet, addr):
        if self.loss_rate and random.random() < self.loss_rate:
            return
        self.sock.sendto(packet, addr)
