import itertools
import numpy as np

from node import Node, Sum, Product, Leaf, Bernoulli, Categorical
from utils import gradient_backward, sgd

# SPN structure and parameter learning as proposed by poon et al.
# src: https://arxiv.org/pdf/1202.3732.pdf
def learn_spn(data, variables, epochs=10, lr=0.01):
    spn = generate_dense_spn(variables)
    initialize_weights(spn)

    for e in range(epochs):
        train_ll = 0
        for d in data:
            # TODO: Check if ll is desired here
            ll = spn.value(d, ll=True)
            train_ll += ll
            update_weights(spn, ll, lr=lr, data=d)
        print(f'Epoch {e}\t => train_ll: {train_ll / len(data)}')
    
    spn = prune_zero_weights(spn)
    return spn


def generate_dense_spn(variables) -> Node:
    # A spn is generated by using the RAT-SPN algorithm
    return generate_rat_spn(variables)


def initialize_weights(spn):
    # If spn has no children (leaf node), stop recursion
    if isinstance(spn, Leaf):
        return
    # If spn is a Sum node and is not yet initialized
    if isinstance(spn, Sum) and not spn.initialized:
        # Initialize the weights
        # FIXME: Initialize uniformly for now
        spn.weights = [1.0/len(spn.children) for c in spn.children]
        spn.initialized = True
    # Recursively initialize weights on children
    [initialize_weights(c) for c in spn.children]

def update_weights(spn, ll, lr=0.01, data=None):
    gradient_backward(spn)
    sgd(spn, lr=lr, data=data)


def prune_zero_weights(spn):
    # TODO: Implement
    return spn


# ====================

# The RAT-SPN algorithm as described in the following paper
# src: https://arxiv.org/pdf/1806.01910.pdf
def generate_rat_spn(variables):
    # First construct a region graph
    region_graph = random_region_graph(variables, depth=2, repetitions=2)
    # Convert the region graph to an spn
    return region_graph.to_spn()


class RegionNode():
    # Initialize a region graph node by storing the region {r}
    def __init__(self, r, root=False):
        self.r = sorted(r)
        self.spn_nodes = []
        self.partitions = []
        self.root = root
    
    # Method for initializing the spn nodes of this region graph node
    def init_spn_nodes(self, node_type, number):
        self.spn_nodes = [node_type() for i in range(number)]

    # Method for initializing the spn nodes of this region graph node as a leaf
    def init_spn_leaves(self, number):
        # TODO: Add extra options as leaf nodes besides Bernoulli (e.g. Gaussian)
        # For every rv in r, a leaf node is created
        leaf_nodes = [Bernoulli(p=0.5, scope=s) for s in self.r]
        # Create {number} different product nodes which all have the leaves as children
        self.spn_nodes = [Product(children=leaf_nodes) for i in range(number)]

    # Method for adding a partition to this region node
    # A partition is a tuple of different RegionNode objects
    def add_partition(self, partition):
        self.partitions.append(partition)

    # Method for converting the region node and its children to an spn recursively
    # using the parameters as described in the paper
    def to_spn(self, c=1, s=2, i=3):
        if c > 1:
            raise ValueError('Multiple roots not yet implemented')

        # First, initialize the spn nodes for this region node
        if len(self.partitions) == 0:
            # Leaf node
            self.init_spn_leaves(i)
        elif self.root:
            # Root node
            self.init_spn_nodes(Sum, c)
        else:
            # Internal node
            self.init_spn_nodes(Sum, s)
        
        # Next, convert the child regions in the partitions to spns
        # (recursive step)
        for r1, r2 in self.partitions:
            r1.to_spn(c=c, s=s, i=i)
            r2.to_spn(c=c, s=s, i=i)

        # Finally, add product nodes between the current node and its children
        # based on the created partitions
        for i, (r1, r2) in enumerate(self.partitions):
            # Cartesian product between all spn nodes of both regions
            for n1, n2 in itertools.product(r1.spn_nodes, r2.spn_nodes):
                p = Product(children=[n1, n2])
                for n in self.spn_nodes:
                    n.add_children([p])

        if c == 1:
            return self.spn_nodes[0]
        return self.spn_nodes


# Method for creating a random region graph
def random_region_graph(variables, depth, repetitions) -> Node:
    node = RegionNode(variables, root=True)
    # Create {repetitions} different splits of the original rvs {variables}
    for r in range(repetitions):
        split(node, depth)
    return node

def split(region, depth):
    # Create two random balanced partitions
    r_region = np.random.permutation(region.r)
    P = r1, r2 = RegionNode(r_region[:len(region.r)//2]), RegionNode(r_region[len(region.r)//2:])
    # Insert P in region
    region.add_partition(P)
    if depth > 1:
        if len(r1.r) > 1: split(r1, depth-1)
        if len(r2.r) > 1: split(r2, depth-1)
