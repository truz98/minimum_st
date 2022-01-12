import sys
from enum import Enum
from typing import List


class NodeState(Enum):
    SLEEP = 0
    FIND = 1
    FOUND = 2


class EdgeState(Enum):
    BASIC = 0
    BRANCH = 1
    REJECT = 2


class Message:
    def __init__(self, message_type: "MessageType", param: List, edge: "Edge"):
        self.message_type = message_type
        self.param = param
        self.edge = edge

    def __str__(self):
        return "Message type" + str(self.message_type) + " with param(s) " + ",".join([str(x) for x in self.param])


class MessageType(Enum):
    NEW_FRAG = 0
    CONNECT = 1
    MERGE = 2
    TEST = 3
    ACCEPT = 4
    REJECT = 5
    REPORT = 6
    CHANGEROOT = 7
    AWAKE = 8
    INITIATE = 9


class Node:
    id: int  # Use only to print logs - No use in the algorithm
    parent: "Edge" = None  # Parent
    level: int = 0
    name: int
    state: NodeState = NodeState.SLEEP
    edges: List["Edge"] = []  # Set of children

    terminated: bool = False  # Use to stop the algorithm
    address: str  # Address of this node

    best_wt: int = sys.maxsize
    best_edge: "Edge" = None
    rec: int = 0
    test_edge: "Edge" = None

    def __init__(self, id, address, state):
        # Add id and address to all nodes
        self.id = id
        self.name = id
        self.address = address
        self.state = state

    def __str__(self):
        return str(self.__dict__)


# This class represent a edge
class Edge:
    def __init__(self, dest, weight, state):
        self.dest = dest
        self.weight = weight
        self.state = state

    dest: Node
    weight: int
    state: EdgeState

    def __str__(self):
        return str(self.__dict__)
