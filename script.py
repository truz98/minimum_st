"""
    Algorithm : Constructing a Minimum Spanning Tree
"""
import copy
import os
import queue
import sys
import threading
from typing import List, Optional

from items import Node, Message, MessageType, Neighbour, EdgeState, NodeState
from utils import read_files, bcolors, neighbour_from_node, get_neighbour_of_parent, neighbour_from_id, \
    find_least_weighted_neighbour
from print_ts import s_print

nodes = []  # Contains all nodes


# Retrieve node from ip
def get_node_from_ip(ip):
    # Retrieve node from ip. Return node
    for neigh in nodes:
        if neigh.address == ip:
            return neigh



# Initialize all nodes
def initialize(node: Node):
    node.barrier = len(node.neighbours)
    for neigh in node.neighbours:
        if neigh.edge.state == EdgeState.BASIC:
            node.send(Message(MessageType.TEST, []), copy.copy(neigh.node))


# Manage the case when Node A and B sent both a CONNEXION request
def connexions_manager(node, node_from):
    if node_from.id in node.received_connexion and node_from.id in node.sent_connection:
        if node.id != node_from.id:
            node.children.add(node_from.id)
        neighbour_from = neighbour_from_node(node_from, node.neighbours)
        neighbour_from.edge.state = EdgeState.MEMBER

        if node.fragment != node.id:
            parent_neighbour = get_neighbour_of_parent(node)

            parent_neighbour.edge.state = EdgeState.MEMBER
            if node.id != node.parent:
                node.children.add(node.parent)
            node.fragment = node.id
            node.parent = node.id

        node.sent_connection.remove(node_from.id)
        node.received_connexion.remove(node_from.id)

        s_print("Node {} new fragment and becomes root".format(node.id))
        node.send(Message(MessageType.NEW_FRAGMENT, []), copy.copy(node))


# Function used in thread to listen to the socket and store the message in the queue
def process_receiver(node: Node, q: queue.Queue, kill: threading.Event):
    while not kill.wait(1):
        q.put(node.receive())


def process(node, b_init: threading.Barrier):
    # Set up the queue and the receiver thread
    q_work = queue.Queue()
    kill = threading.Event()
    receive_t = threading.Thread(target=process_receiver, args=(node, q_work, kill))
    receive_t.start()

    b_init.wait()

    # Run until the node has terminated
    while not node.terminated:

        if node.id in node.children:
            node.children.remove(node.id)

        # If there is a message in the queue
        if not q_work.empty():
            # Get the message
            node_from_address, message = q_work.get()

            node_from = get_node_from_ip(node_from_address)
            message_type = message.message_type
            s_print("Node {} receives a {} from node {}".format(node.id, message_type, node_from.id))

            match message_type:
                case MessageType.INIT:
                    initialize(node)
                case MessageType.NEW_FRAGMENT:
                    # Adopt the node_from fragment
                    node.fragment = node_from.fragment
                    node.ack = 0
                    node.min_weight = sys.maxsize

                    if node.id != node_from.fragment:
                        if node.id != node.parent:
                            # Place the parent in the children if one
                            parent_neighbour = get_neighbour_of_parent(node)
                            if parent_neighbour:
                                parent_neighbour.edge.state = EdgeState.MEMBER
                                if node.parent != node.id:
                                    node.children.add(node.parent)

                        # Get neighbour corresponding to the node_from
                        neighbour_from = neighbour_from_node(node_from, node.neighbours)

                        neighbour_from.edge.state = EdgeState.MEMBER
                        # My parent becom my child
                        if neighbour_from.node.id in node.children and node.id != node_from.id:
                            node.children.remove(node_from.id)

                        node.parent = neighbour_from.node.id

                    temp = node.received_connexion.copy()
                    for nd_id in temp:
                        if node.parent != nd_id:
                            node.received_connexion.remove(nd_id)

                            if node.id != node_from.id:
                                node.children.add(node_from.id)

                            neighbour_from = neighbour_from_id(nd_id, node.neighbours)
                            if neighbour_from:
                                neighbour_from.edge.state = EdgeState.MEMBER
                            else:
                                s_print("!!!!!!!! Node {} has not node {} as neighbour".format(node.id, nd_id))

                    # Send NEW_FRAGMENT message to children
                    tmp = node.children.copy()
                    for c_id in tmp:
                        node.ack += 1
                        child_neighbour = neighbour_from_id(c_id, node.neighbours)
                        if child_neighbour:
                            node.send(Message(MessageType.NEW_FRAGMENT, []), copy.copy(child_neighbour.node))
                        else:
                            s_print("!!!!!!!! Node {} has not  {} as child".format(node.id, c_id))

                    # if no child, send ACK to parent
                    if len(node.children) == 0:
                        if node.id == node.parent:
                            node.send(Message(MessageType.ACK, []), copy.copy(node))
                        else:
                            node.send(Message(MessageType.ACK, []),
                                      copy.copy(neighbour_from_id(node.parent, node.neighbours)))

                case MessageType.CONNECT:
                    node.received_connexion.add(node_from.id)

                    connexions_manager(node, node_from)

                case MessageType.MERGE:
                    # if i'm the root
                    if node.to_mwoe == node:
                        # find the minimal weighted neighbour and send a connect to it
                        least_neighbour = find_least_weighted_neighbour(node.neighbours)
                        node.sent_connection.add(least_neighbour.node.id)
                        node.send(Message(MessageType.CONNECT, []), copy.copy(least_neighbour.node))

                        connexions_manager(node, least_neighbour.node)

                    else:
                        node.send(Message(MessageType.MERGE, []), copy.copy(node.to_mwoe))

                case MessageType.TEST:
                    if node_from.fragment != node.fragment:
                        node.send(Message(MessageType.ACCEPT, []), copy.copy(node_from))
                    else:
                        node.send(Message(MessageType.REJECT, []), copy.copy(node_from))

                case MessageType.ACCEPT:
                    node.accepted.append(node_from)
                    if node_from in node.rejected:
                        node.rejected.remove(node_from)

                    neighbour_from = neighbour_from_node(node_from, node.neighbours)
                    try:
                        if neighbour_from.edge.weight < node.min_weight:
                            node.min_weight = neighbour_from.edge.weight
                            node.to_mwoe = node
                    except Exception:
                        print(f"{bcolors.WARNING}{node}{node_from}{bcolors.ENDC}")

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
                            if node.id == node.parent:
                                node.send(Message(MessageType.ACK, []), copy.copy(node))
                            else:
                                node.send(Message(MessageType.ACK, []),
                                          copy.copy(neighbour_from_id(node.parent, node.neighbours)))

                        else:
                            node.send(Message(MessageType.DOTEST, []), copy.copy(node))

                case MessageType.DOTEST:
                    node.barrier = 0
                    for neigh in node.neighbours:
                        if neigh.edge.state == EdgeState.BASIC:
                            node.barrier += 1
                            node.send(Message(MessageType.TEST, []), copy.copy(neigh.node))
                        elif neigh.node.id in node.children:
                            node.barrier += 1
                            node.send(Message(MessageType.DOTEST, []), copy.copy(neigh.node))

                case MessageType.TERMINATE:
                    node.terminated = True
                    s_print("Node {} terminated".format(node.id))
                    kill.set()
                    receive_t.join()
                    print(f"{bcolors.OKGREEN}{node.id}terminated{bcolors.ENDC}")

            if node.barrier == 0:
                s_print("Node {} passed barrier".format(node.id))
                if node.state == NodeState.OUT:
                    node.count = len(node.neighbours)

                node.barrier -= 1

                # The node is the root
                if node.fragment == node.id:
                    s_print("Node {} his min. weight = {}".format(node.id, node.min_weight))
                    if node.min_weight == sys.maxsize:
                        node.terminated = True
                        s_print("Node {} terminated".format(node.id))
                        kill.set()
                        receive_t.join()
                        print(f"{bcolors.OKGREEN}{node.id}terminated{bcolors.ENDC}")

                    else:
                        # merge down
                        node.send(Message(MessageType.MERGE, []), copy.copy(node.to_mwoe))
                else:
                    # report up
                    if node.id == node.parent:
                        node.send(Message(MessageType.REPORT, []), copy.copy(node))
                    else:
                        node.send(Message(MessageType.REPORT, []),
                                  copy.copy(neighbour_from_id(node.parent, node.neighbours)))

    for c_id in node.children:
        child_neighbour = neighbour_from_id(c_id, copy.copy(node.neighbours))
        node.send(Message(MessageType.TERMINATE, []), copy.copy(child_neighbour.node))


if __name__ == "__main__":

    directory = "Neighbours_simple"

    all_files_path = [
        os.path.join(directory, "node-1.yaml"),
        os.path.join(directory, "node-2.yaml"),
        os.path.join(directory, "node-3.yaml"),
        # os.path.join(directory, "node-4.yaml"),
        # os.path.join(directory, "node-5.yaml"),
        # os.path.join(directory, "node-6.yaml"),
        # os.path.join(directory, "node-7.yaml"),
        # os.path.join(directory, "node-8.yaml"),
        # os.path.join(directory, "node-9.yaml"),
    ]

    # Read nodes from files
    nodes = read_files(all_files_path)
    nb_nodes = len(nodes)

    # Used to wait for all thread to set up their queue and message processing
    barrier_init = threading.Barrier(nb_nodes)

    # Start each node in a thread
    threads = []
    for nd_ in nodes:
        x = threading.Thread(target=process, args=(nd_, barrier_init))
        x.start()
        threads.append(x)

    # Dummy thread to send the a INIT message to all the nodes to begin the algorithm
    init_node = Node(0, "127.0.0.1")
    nodes.append(init_node)

    for nd_ in nodes[:-1]:
        init_node.send(Message(MessageType.INIT, []), nd_)

    # Wait for the threads to finish
    for t in threads:
        t.join()
