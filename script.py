"""
    Algorithm : Constructing a Minimum Spanning Tree
"""
import pickle
import os
import queue
import socket
import sys
import threading
import time
from typing import List, Optional

from items import Node, Message, MessageType, Neighbour, EdgeState, NodeState
from utils import read_files, WaitGroup
from print_ts import s_print

nodes = []  # Contains all nodes
PORT = 12345


def get_node_from_ip(ip):
    # Retrieve node from ip. Return node
    for neigh in nodes:
        if neigh.address == ip:
            return neigh


def find_least_weighted_neighbour(neighbours: List[Neighbour]):
    least_weighted = neighbours[0]
    for neigh in neighbours[1:]:
        if neigh.edge.weight < least_weighted.edge.weight:
            least_weighted = neigh

    return least_weighted


def get_neighbour_of_parent(node: Node) -> Optional[Neighbour]:
    for neigh in node.neighbours:
        if neigh.node.parent == node.parent:
            return neigh

    return None


def neighbour_from_node(node: Node, neighbors: List[Neighbour]) -> Neighbour:
    for neigh in neighbors:
        if neigh.node == node:
            return neigh


def initialize(node: Node):
    node.barrier = len(node.neighbours)
    for neigh in node.neighbours:
        if neigh.edge.state == EdgeState.BASIC:
            node.send(Message(MessageType.TEST, []), neigh.node)


def try_send(node: Node):
    # while not node.to_send.empty():
    if not node.to_send.empty():
        message, node_to = node.to_send.get()
        s_print("RETRY : Node {} ({}) send <{}> to node {} ({})".format(node.id, node.address, message, node_to.id,
                                                                        node_to.address))
        node.send(message, node_to)


def connection_handler(node, node_from):
    if node_from in node.received_connexion and node_from in node.sent_connection:
        node.children.append(node_from)
        neighbour_from = neighbour_from_node(node_from, node.neighbours)
        neighbour_from.edge.state = EdgeState.MEMBER

        if node.fragment != node.id:
            parent_neighbour = get_neighbour_of_parent(node)

            parent_neighbour.edge.state = EdgeState.MEMBER
            node.children.append(parent_neighbour.node)
            node.fragment = node.id
            node.parent = node

        node.sent_connection.remove(node_from)
        node.received_connexion.remove(node_from)

        node.send(Message(MessageType.NEW_FRAGMENT, []), node, node)


def process(node, wait_group):
    # Run until the node has terminated
    while not node.terminated:

        try_send(node)

        # initialize(node)

        # Wait for message
        wait_group.done()
        wait_group.wait()

        s_print("Node {} : wait for message".format(node.id))
        node_from_address, message = node.receive()
        node_from = get_node_from_ip(node_from_address)
        message_type = message.message_type
        params = message.param

        s_print("Node {} receives a message from node {}".format(node.id, node_from.id))

        match message_type:

            case MessageType.INIT:
                initialize(node)
            case MessageType.NEW_FRAGMENT:
                # Adopt the node_from fragment
                node.fragment = node_from.fragment
                node.ack = 0
                node.min_weight = sys.maxsize

                if node.id != node_from.fragment:
                    if node.id != node.parent.id:
                        # Place the parent in the children if one
                        parent_neighbour = get_neighbour_of_parent(node)
                        if parent_neighbour:
                            parent_neighbour.edge.state = EdgeState.MEMBER
                            node.children.append(parent_neighbour.node)

                    # Change the parent to node_from
                    node.parent = node_from
                    # todo: try to remove above line

                    # Get neighbour corresponding to the node_from
                    neighbour_from = neighbour_from_node(node_from, node.neighbours)

                    neighbour_from.edge.state = EdgeState.MEMBER
                    # My parent becom my child
                    if neighbour_from.node in node.children:
                        node.children.remove(neighbour_from.node)

                    node.parent = neighbour_from.node

                temp = node.received_connexion.copy()
                for nd in temp:
                    if node.parent != nd:
                        node.received_connexion.remove(nd)
                        node.children.add(nd)
                        neighbour_from_node(nd, node.neighbours).edge.state = EdgeState.MEMBER

                # Send NEW_FRAGMENT message to children
                for c in node.children:
                    node.ack += 1
                    node.send(Message(MessageType.NEW_FRAGMENT, []), c)

                # if no child, send ACK to parent
                if len(node.children) == 0:
                    node.send(Message(MessageType.ACK, []), node.parent)

            case MessageType.CONNECT:
                neighbour_from: Neighbour = neighbour_from_node(node_from, node.neighbours)

                node.received_connexion.append(neighbour_from.node)

                connection_handler(node, node_from)

            case MessageType.MERGE:
                # if i'm the root
                if node.to_mwoe == node:
                    # find the minimal weighted neighbour and send a connect to it
                    least_neighbour = find_least_weighted_neighbour(node.neighbours)
                    node.sent_connection.append(least_neighbour)
                    node.send(Message(MessageType.CONNECT, []), least_neighbour.node)

                    connection_handler(node, node_from)

                else:
                    node.send(Message(MessageType.MERGE, []), node.to_mwoe)

            case MessageType.TEST:
                if node_from.fragment != node.fragment:
                    node.send(Message(MessageType.ACCEPT, []), node_from)
                else:
                    node.send(Message(MessageType.REJECT, []), node_from)

            case MessageType.ACCEPT:
                node.rejected.append(node_from)
                if node_from in node.accepted:
                    node.accepted.remove(node_from)

                neighbour_from = neighbour_from_node(node_from, node.neighbours)
                try:

                    if neighbour_from.edge.weight < node.min_weight:
                        node.min_weight = neighbour_from.edge.weight
                        node.to_mwoe = node
                except Exception:
                    s_print(node, node_from)

                node.barrier -= 1

            case MessageType.REJECT:
                node.barrier -= 1
                node.count -= 1

                node.state = NodeState.IN if node.count == 0 else NodeState.OUT

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
                node.ack -= 1
                if node.ack == 0:
                    # report to parent if not the root
                    if node.fragment != node.id:
                        node.send(Message(MessageType.ACK, []), node.parent)
                    else:
                        node.send(Message(MessageType.DOTEST, []), node)

            case MessageType.DOTEST:
                node.barrier = 0
                for neigh in node.neighbours:
                    if neigh.edge.state == EdgeState.BASIC:
                        node.barrier += 1
                        node.send(Message(MessageType.TEST, []), neigh.node)
                    elif neigh.node in node.children:
                        node.barrier += 1
                        node.send(Message(MessageType.DOTEST, []), neigh.node)

            case MessageType.TERMINATE:
                # node.terminated = True
                # todo: uncomment
                # s_print("Node {} terminated".format(node.id))
                pass

        if node.barrier == 0:

            if node.state == NodeState.OUT:
                node.count = len(node.neighbours)

            node.barrier -= 1

            # The node is the root
            if node.fragment == node.id:
                if node.min_weight == sys.maxsize:
                    # node.terminated = True
                    # todo: uncomment
                    # s_print("Node {} terminated".format(node.id))
                    pass

                else:
                    # merge down
                    node.send(Message(MessageType.MERGE, []), node.to_mwoe)
            else:
                # report up
                node.send(Message(MessageType.REPORT, []), node.parent)

    for c in node.children:
        node.send(Message(MessageType.TERMINATE, []), c)


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
    waitgroup.add(nb_nodes + 1)

    # Start each node in a thread, except root node
    for nd_ in nodes:
        x = threading.Thread(target=process, args=(nd_, waitgroup))
        x.start()

    init_node = Node(0, "127.0.0.1")
    nodes.append(init_node)

    waitgroup.done()

    for nd_ in nodes[:-1]:
        init_node.send(Message(MessageType.INIT, []), nd_)
