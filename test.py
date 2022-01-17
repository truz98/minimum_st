import socket
import time
from threading import Thread, Barrier
from queue import Queue

from print_ts import s_print
from utils import WaitGroup


def rcv(q: Queue, s: socket, barrier: Barrier):
    # wg.done()
    # wg.wait()
    while True:
        # Receive data
        s_print("Ready to receive")
        barrier.wait()
        clientsocket, address = s.accept()
        # Retrieve node source from ip
        node_address = address[0]

        # Get message
        message = clientsocket.recv(4096).decode()

        clientsocket.close()

        q.put(message)


def receiver(id, barrier: Barrier):
    s_print(id)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.1.1", 12345))
    s.listen()

    q = Queue()
    rcv_t = Thread(target=rcv, args=(q, s, barrier))
    rcv_t.start()

    while True:
        if not q.empty():
            message = q.get()
            s_print("Received :", message)


def sender(id, barrier: Barrier):
    s_print(id)
    i = 0
    while True:
        # wg.done()
        # wg.wait()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.1.2", 12345))

        barrier.wait()
        s.connect(("127.0.1.1", 12345))

        msg = ("Message " + str(i))
        s.send(msg.encode())
        s_print("Send :    ", msg)

        # time.sleep(0.1)
        s.close()
        i += 1


if __name__ == "__main__":
    barrier = Barrier(2)

    rec = Thread(target=receiver, args=("1", barrier))
    rec.start()

    sen = Thread(target=sender, args=("2", barrier))
    sen.start()
