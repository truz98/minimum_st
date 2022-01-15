import yaml

from items import Edge, Node, Neighbour
import threading  # :(
from threading import Lock

s_print_lock = Lock()


def s_print(*a, **b):
    """Thread safe print function"""
    with s_print_lock:
        print(*a, **b)


# visualgo.net
# {"vl":{"0":{"x":100,"y":40},"1":{"x":200,"y":220},"2":{"x":280,"y":40},"3":{"x":420,"y":240},"4":{"x":480,"y":60},"5":{"x":560,"y":260},"6":{"x":640,"y":60},"7":{"x":760,"y":240}},"el":{"0":{"u":0,"v":1,"w":3},"1":{"u":0,"v":2,"w":2},"2":{"u":1,"v":2,"w":2},"3":{"u":1,"v":3,"w":3},"4":{"u":1,"v":4,"w":4},"5":{"u":2,"v":5,"w":4},"6":{"u":4,"v":5,"w":3},"7":{"u":4,"v":6,"w":2},"8":{"u":4,"v":7,"w":4},"9":{"u":5,"v":7,"w":3},"10":{"u":6,"v":7,"w":3}}}

def read_files(all_files_path):
    # Read content of all files and return data contained inside each file
    data = []
    for f in all_files_path:
        try:
            # Open and read file
            with open(f) as file:
                yaml_node = yaml.load(file, Loader=yaml.FullLoader)
                data.append(yaml_node)

            # Close file
            file.close()
        except Exception as e:
            print(e)
            exit()

    # Create all nodes, without neighbours. Return all nodes
    nodes = []
    for n in data:
        nodes.append(Node(n['id'], n['address']))

    # Add all neighbours
    all_edge = {}
    for n in nodes:
        yaml_node = next(filter(lambda x: x["id"] == n.id, data))
        edges = []
        for neighbour in yaml_node["neighbours"]:
            key = (min([n.id, neighbour["id"]]), max([n.id, neighbour["id"]]))

            if key not in all_edge:
                e = Edge(weight=neighbour["edge_weight"])
                all_edge[key] = e

            edges.append(Neighbour(edge=all_edge[key], node=next(filter(lambda x: x.id == neighbour["id"], nodes))))

        n.neighbours = edges
        n.to_mwoe = n

    return nodes


def find_least_weighted_edge(edges):
    return min(edges, key=lambda x: x[0].weight)


def find_edge_of_node(edges, node):
    for e in edges:
        if e[1] == node:
            return e[0]

    raise Exception


class WaitGroup(object):
    def __init__(self):
        self.count = 0
        self.cv = threading.Condition()

    def add(self, n):
        self.cv.acquire()
        self.count += n
        self.cv.release()

    def done(self):
        self.cv.acquire()
        self.count -= 1
        if self.count == 0:
            self.cv.notify_all()
        self.cv.release()

    def wait(self):
        self.cv.acquire()
        while self.count > 0:
            self.cv.wait()
        self.cv.release()
