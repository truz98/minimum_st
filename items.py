import pickle
import queue
import sys
import time
from enum import Enum
from typing import List
import socket

from print_ts import s_print

PORT_IN = 12345
PORT_OUT = 54321


class NodeState(Enum):
    IN = 1
    OUT = 1


class EdgeState(Enum):
    BASIC = 0
    MEMBER = 1
    NON_MEMBER = 2


class Message:
    def __init__(self, message_type: "MessageType", param: List):
        self.message_type = message_type
        self.param = param

    def __str__(self):
        return "Message type" + str(self.message_type) + " with param(s) " + ",".join([str(x) for x in self.param])


class MessageType(Enum):
    NEW_FRAGMENT = 0
    CONNECT = 1
    MERGE = 2
    TEST = 3
    ACCEPT = 4
    REJECT = 5
    REPORT = 6
    ACK = 7
    DOTEST = 8
    TERMINATE = 9
    INIT = 10


class Node:
    id: int  # Use only to print logs - No use in the algorithm
    fragment: int
    address: str  # Address of this node
    to_mwoe: "Node"

    parent: "Node" = None  # Parent
    state: NodeState = NodeState.OUT
    neighbours: List["Neighbour"] = []  # Set of children
    terminated: bool = False  # Use to stop the algorithm
    children: List["Neighbour"] = []
    received_connexion: List["Node"] = []
    sent_connection: List["Node"] = []
    accepted: List["Node"] = []
    rejected: List["Node"] = []
    min_weight: int = sys.maxsize
    ack: int = 0
    barrier: int = 0
    count: int = 0
    to_send = queue.Queue()
    s: socket

    def __init__(self, id, address):
        # Add id and address to all nodes
        self.id = id
        self.address = address
        self.fragment = id

        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind((self.address, PORT_IN))

        self.s.listen()

    def __str__(self):
        return str(self.__dict__)

    def _send(self, message: Message, node_dst: "Node"):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.address, PORT_OUT))

        s.connect((node_dst.address, PORT_IN))
        s.send(pickle.dumps(message))
        s.close()
        s_print("Node {} sent <{}> to node {}".format(self.id, message, node_dst.id))

    def send(self, message: Message, node_dst: "Node"):
        if node_dst not in [neigh.node for neigh in self.neighbours] and len(self.neighbours) > 0:
            s_print("FAIL !!!! {} try to send {} to {}".format(self.id, message.message_type, node_dst.id))
        self._send(message, node_dst)

    def receive(self):
        # Receive data
        clientsocket, address = self.s.accept()
        # Retrieve node source from ip
        node_address = address[0]

        # Get message
        message = pickle.loads(clientsocket.recv(4096))

        clientsocket.close()

        return node_address, message


class Neighbour:
    def __init__(self, edge, node):
        self.edge = edge
        self.node = node

    edge: "Edge"
    node: "Node"

    def __str__(self):
        return str(self.edge) + "-" + str(self.node)


# This class represent a edge
class Edge:
    def __init__(self, weight):
        self.weight = weight
        self.state = EdgeState.BASIC

    weight: int
    state: EdgeState

    def __str__(self):
        return str(self.weight) + "-" + str(self.state)
