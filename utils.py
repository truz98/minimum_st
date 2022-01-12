import yaml

from items import Edge, Node, NodeState, EdgeState


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
        nodes.append(Node(n['id'], n['address'], NodeState.SLEEP))

    # Add all neighbours
    for n in nodes:
        yaml_node = next(filter(lambda x: x["id"] == n.id, data))
        edges = []
        for neighbour in yaml_node["neighbours"]:
            # Id is 1->n and list is 0->n-1
            edges.append(Edge(dest=next(filter(lambda x: x.id == neighbour["id"], nodes)),
                              weight=neighbour["edge_weight"], state=EdgeState.BASIC))

        n.edges = edges

    return nodes
