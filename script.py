"""
    Algorithm : Constructing a Minimum Spanning Tree
"""
import pickle
import os
import socket
import sys
import threading
import yaml
from typing import List
from enum import Enum

from items import Node, Edge, EdgeState, NodeState, Message, MessageType
from utils import read_files

nodes = []  # Contains all nodes


# This class represent a node


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
    serversocket.bind((node.address, 8000))
    serversocket.listen(5)

    # Receive data
    (clientsocket, address) = serversocket.accept()

    # Retrieve node source from ip
    node_src = get_node_from_ip(address[0])

    # Get message
    message = pickle.loads(clientsocket.recv(2000))

    return node_src, message


def find_least_weighted_edge(edges):
    return min(edges, key=lambda x: x.weight)


def root_function(node):
    # Priming method of the root node

    # Set parent, get a neighbour
    node.parent = node
    node.state = NodeState.FIND

    # Create and send first socket
    node.state = NodeState.FOUND
    edge = find_least_weighted_edge(node.edges)
    edge.state = EdgeState.BRANCH
    send(Message(MessageType.CONNECT, [0], edge), node_src=node, node_dst=edge.dest)

    # Connect to server
    server(node)


def send(message: Message, node_src: Node, node_dst: Node):
    # Send a packet to another node

    # Create socket, bind and connect
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((node_src.address, 8000))
    s.connect((node_dst.address, 8000))

    # Send
    print("Node {} ({}) send <{}> to node {} ({})".format(node_src.id, node_src.address, message, node_dst.id,
                                                          node_dst.address))
    s.send(pickle.dumps(message))

    # Close socket
    s.close()


def find_edge_of_node(edges, node):
    for e in edges:
        if e.dest == node:
            return e

    raise Exception


def report(node):
    qs = 0
    for e in node.edges:
        if e.state == EdgeState.BRANCH and e != node.parent:
            qs += 1

    if node.rec == qs and node.test_edge is None:
        node.state = NodeState.FOUND
        send(Message(MessageType.REPORT, [node.best_wt], find_edge_of_node(node.edges, node.parent)), node, node.parent)


def find_min(edge, node, node_from):
    if edge in node.edges and edge.state == EdgeState.BASIC:
        node.test_edge = edge
        send(Message(MessageType.TEST, [node.level, node.name], edge), node, node_from)
    else:
        report(node)


def change_root(node):
    if node.best_edge == EdgeState.BRANCH:
        send(Message(MessageType.CHANGEROOT, [], node.best_edge), node, node.best_edge.dest)
    else:
        node.best_edge.state = EdgeState.BRANCH
        send(Message(MessageType.CONNECT, node.level, node.best_edge), node, node.best_edge.dest)


def server(node):
    # Run until the node has terminated
    while not node.terminated:
        # Waiting for a message
        (node_from, message) = receive(node)
        edge = message.edge

        match message.message_type:
            case MessageType.CONNECT:
                level = message.param[0]
                if level < node.level:
                    edge.state = EdgeState.BRANCH
                    send(Message(MessageType.INITIATE, [node.level, node.name, node.state], edge), node, node_from)
                elif edge.state == EdgeState.BASIC:
                    break
                else:
                    send(Message(MessageType.INITIATE, [message.param[0] + 1, node.name, NodeState.FIND], edge), node,
                         node_from)

            case MessageType.INITIATE:
                level, name, state = message.param
                node.level = level
                node.name = name
                node.state = state
                node.parent = node_from

                # bestNode ← φ
                # bestWt ← ∞
                # testNode ← none

                for r in node.edges:
                    if r.state == EdgeState.BRANCH and r != edge:
                        send(Message(MessageType.INITIATE, [level, name, state], r), node, r.dest)

                if node.state == NodeState.FIND:
                    find_min(edge, node, node_from)

            case MessageType.TEST:
                level, name = message
                if level > node.level:
                    # wait
                    break
                elif name == node.name:
                    if edge.state == EdgeState.BASIC:
                        edge.state = EdgeState.REJECT

                    if edge != node.best_edge:
                        send(Message(MessageType.REJECT, [], edge), node, node_from)
                    else:
                        find_min(edge, node, node_from)

                else:
                    send(Message(MessageType.ACCEPT, [], edge), node, node_from)

            case MessageType.ACCEPT:
                node.best_edge = None
                lwe = find_least_weighted_edge(node.edges)
                if lwe.weight < node.best_wt:
                    node.best_wt = lwe
                    node.best_edge = edge

                report(node)

            case MessageType.REJECT:
                if edge.state == EdgeState.BASIC:
                    edge.state = EdgeState.REJECT

                find_min(edge, node, node_from)

            case MessageType.REPORT:
                omega = message.param[0]
                if node_from != node.parent:
                    if omega < node.best_wt:
                        node.best_wt = omega
                        node.best_edge = edge
                    node.rec = node.rec + 1
                    report(node)
                else:
                    if node.state == NodeState.FIND:
                        # wait
                        break
                    elif omega > node.best_wt:
                        change_root(node)
                        pass
                    elif omega == sys.maxsize == node.best_wt:
                        node.terminated = True

            case MessageType.CHANGEROOT:
                change_root(node)


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

    # Start each node in a thread, except root node
    for n in nodes[:-1]:
        x = threading.Thread(target=server, args=(n,))
        x.start()
        print("Node {} has started with ip {}.".format(n.id, n.address))

    # Start root node in another function
    x = threading.Thread(target=root_function, args=(nodes[nb_nodes - 1],))
    x.start()
    print("Node {} has started with ip {}. This is the root node.".format(nodes[nb_nodes - 1].id,
                                                                          nodes[nb_nodes - 1].address))
