"""
    Algorithm : Constructing a Minimum Spanning Tree
"""
import pickle
import os
import socket
import sys
import threading
import time
from typing import List, Optional
from threading import Lock

from items import Node, Message, MessageType, Neighbour, EdgeState
from utils import read_files, WaitGroup

nodes = []  # Contains all nodes
PORT = 9783
s_print_lock = Lock()


def s_print(*a, **b):
    """Thread safe print function"""
    with s_print_lock:
        print(*a, **b)


def get_node_from_ip(ip):
    # Retrieve node from ip. Return node
    for n in nodes:
        if n.address == ip:
            return n


def receive(node):
    # Wait until a packet is received. Return sender's node and the message received

    # Create socket to receive data
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind((node.address, PORT))
    serversocket.listen()

    # Receive data
    clientsocket, address = serversocket.accept()

    # Retrieve node source from ip
    node_src = get_node_from_ip(address[0])

    # Get message
    message = pickle.loads(clientsocket.recv(4096))

    return node_src, message


def send(message: Message, node_src: Node, node_dst: Node):
    # Send a packet to another node

    # Create socket, bind and connect
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((node_src.address, PORT))
    s.connect((node_dst.address, PORT))

    # Send
    s_print("Node {} ({}) send <{}> to node {} ({})".format(node_src.id, node_src.address, message, node_dst.id,
                                                            node_dst.address))
    s.send(pickle.dumps(message))

    # Close socket
    s.close()


def find_least_weighted_neighbour(neighbours: List[Neighbour]):
    least_weighted = neighbours[0]
    for n in neighbours[1:]:
        if n.edge.weight < least_weighted.edge.weight:
            least_weighted = n

    return least_weighted


def get_neighbour_of_parent(node: Node) -> Optional[Neighbour]:
    for n in node.neighbours:
        if n.node.parent == node.parent:
            return n

    return None


def neighbour_from_node(node: Node, neighbors: List[Neighbour]) -> Neighbour:
    for n in neighbors:
        if n.node == node:
            return n


def initialize(node):
    node.barrier = len(node.neighbours)
    for n in node.neighbours:
        if n.edge.state == EdgeState.BASIC:
            send(Message(MessageType.TEST, [node.id]), node, n.node)


def process(node, wait_group):
    # Run until the node has terminated
    while not node.terminated:

        # wait_group.done()
        # wait_group.wait()

        # Wait for message
        s_print("Node {} wait for a message".format(node.id))
        (node_from, message) = receive(node)
        message_type = message.message_type
        params = message.param

        match message_type:

            case MessageType.INIT:
                initialize(node)
            case MessageType.NEW_FRAGMENT:
                fragment = params[0]

                # Adopt the node_from fragment
                node.fragment = node_from.fragment
                node.ack = 0

                if node.id != fragment:
                    if node.id != node.parent.id:
                        # Place the parent in the children if one
                        parent_neighbour = get_neighbour_of_parent(node)
                        if parent_neighbour:
                            parent_neighbour.edge.state = EdgeState.MEMBER
                            node.children.append(parent_neighbour.node)

                    # Change the parent to node_from
                    node.parent = node_from

                    # Get neighbour corresponding to the node_from
                    neighbour_from = neighbour_from_node(node_from, node.neighbours)

                    neighbour_from.edge.state = EdgeState.MEMBER
                    # My parent becom my child
                    node.children.remove(neighbour_from.node)
                    node.parent = neighbour_from.node

                for n in node.received_connexion:
                    if node.parent != n:
                        node.children.add(n)
                        neighbour_from_node(n, node.neighbours).edge.state = EdgeState.MEMBER
                        node.received_connexion.remove(n)

                # Send NEW_FRAGMENT message to children
                for c in node.children:
                    node.ack += 1
                    send(Message(MessageType.NEW_FRAGMENT, [node.fragment]), node, c)

                # if no child, send ACK to parent
                if len(node.children) == 0:
                    send(Message(MessageType.ACK, []), node, node.parent)

            case MessageType.CONNECT:
                neighbour_from = neighbour_from_node(node_from, node.neighbours)

                node.received_connexion.append(neighbour_from)

                # connectHandler

            case MessageType.MERGE:
                if node.to_mwoe == node:
                    least_neighbour = find_least_weighted_neighbour(node.neighbours)
                    node.sent_connection.add(least_neighbour)
                    send(Message(MessageType.CONNECT, []), node, least_neighbour.node)
                    # connectHandler
                else:
                    send(Message(MessageType.MERGE, []), node, node.to_mwoe)

            case MessageType.TEST:
                if node_from.fragment != node.fragment:
                    send(Message(MessageType.ACCEPT, []), node, node_from)
                else:
                    send(Message(MessageType.REJECT, []), node, node_from)

            case MessageType.ACCEPT:
                node.rejected.append(node_from)
                if node_from in node.accepted:
                    node.accepted.remove(node_from)
                neighbour_from = neighbour_from_node(node_from, node.neighbours)
                if neighbour_from.edge.weight < node.min_weight:
                    node.min_weight = neighbour_from.edge.weight

                node.barrier -= 1

            case MessageType.REJECT:
                node.barrier -= 1

                node.rejected.append(node_from)
                if node_from in node.accepted:
                    node.accepted.remove(node_from)

            case MessageType.REPORT:
                neighbour_from = neighbour_from_node(node_from, node.neighbours)

                node.barrier -= 1

                if neighbour_from.edge.weight < node.min_weight:
                    node.to_mwoe = node_from
                    node.min_weight = neighbour_from.edge.weight

            case MessageType.ACK:
                if node.ack == 0:
                    # report to parent if not the root
                    if node.fragment != node.id:
                        send(Message(MessageType.ACK, []), node, node.parent)
                    else:
                        send(Message(MessageType.DOTEST, []), node, node)

            case MessageType.DOTEST:
                node.barrier = 0
                for n in node.neighbours:
                    if n.edge.state == EdgeState.BASIC and n.node not in node.children:
                        node.barrier += 1
                        send(Message(MessageType.TEST, []), node, n.node)
                    elif n.edge.state == EdgeState.BASIC and n.node in node.children:
                        node.barrier += 1
                        send(Message(MessageType.DOTEST, []), node, n.node)

            case MessageType.TERMINATE:
                node.terminated = True

        if node.barrier == 0:
            if node.fragment == node.id:
                if node.min_weight == sys.maxsize:
                    node.terminated = True
                else:
                    # merge down
                    send(Message(MessageType.MERGE, []), node, node.to_mwoe)
            else:
                # report up
                send(Message(MessageType.REPORT, []), node, node.parent)

    for c in node.children:
        send(Message(MessageType.TERMINATE, []), node, c)

    s_print("Node {} terminated".format(node.id))


if __name__ == "__main__":
    # Declare all files path here
    all_files_path = [
        os.path.join("Neighbours", "node-1.yaml"),
        os.path.join("Neighbours", "node-2.yaml"),
        os.path.join("Neighbours", "node-3.yaml"),
        os.path.join("Neighbours", "node-4.yaml"),
        os.path.join("Neighbours", "node-5.yaml"),
        os.path.join("Neighbours", "node-6.yaml"),
        os.path.join("Neighbours", "node-7.yaml"),
        os.path.join("Neighbours", "node-8.yaml"),
    ]
    # Read data from files
    nodes = read_files(all_files_path)
    nb_nodes = len(nodes)

    waitgroup = WaitGroup()
    waitgroup.add(nb_nodes)

    # Start each node in a thread, except root node
    for n in nodes:
        x = threading.Thread(target=process, args=(n, waitgroup))
        x.start()
        # print("Node {} has started with ip {}.".format(n.id, n.address))

    time.sleep(1)

    for n in nodes:
        send(Message(MessageType.INIT, []), Node(0, "127.0.1.0"), n)

