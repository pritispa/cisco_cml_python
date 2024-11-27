from wrapper.nodegroup import *
from cml.node import *

class Topology:
    def __init__(self, node_group1: NodeGroup, node_group2: NodeGroup = None, exclude_interfaces: list = [], topology_type: str = "clos_n_n") -> None:
        self.topology_type = topology_type #values: clos_n_n, square_2_2, full_mesh_n_n, star_1_n, straight_n_n, intra_b2b_n
        self.node_group1 = node_group1
        self.node_group2 = node_group2
        self.exclude_interfaces = exclude_interfaces
    
    # Calling build everytime will add additional cabling apart from any existing one.
    def build(self):
        match self.topology_type:
            case "clos_n_n":
                if not self.node_group2:
                    print ("Warning! Both groups are mandatory for clos_n_n topology.")
                    print (f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                for node1 in self.node_group1.nodes:
                    for node2 in self.node_group2.nodes:
                        add_link_between_nodes(
                            node1=node1,
                            node2=node2,
                            exclude_interfaces = self.exclude_interfaces,
                        )
            case "square_2_2":
                if not self.node_group2:
                    print ("Warning! Both groups are mandatory for square_2_2 topology.")
                    print (f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                if self.node_group1.group_node_count !=2 or self.node_group1.group_node_count !=2:
                    print ("Warning! Square topology can only form between 2 nodes from each group, that is total 4 nodes.")
                    print (f"Skipped connecting groups: {self.node_group1.group_name} and {self.node_group2.group_name}")
                    return
                add_link_between_nodes(
                    node1=self.node_group1.nodes[0],
                    node2=self.node_group2.nodes[0],
                    exclude_interfaces = self.exclude_interfaces,
                )
                add_link_between_nodes(
                    node1=self.node_group1.nodes[0],
                    node2=self.node_group1.nodes[1],
                    exclude_interfaces = self.exclude_interfaces,
                )
                add_link_between_nodes(
                    node1=self.node_group2.nodes[1],
                    node2=self.node_group1.nodes[1],
                    exclude_interfaces = self.exclude_interfaces,
                )
                add_link_between_nodes(
                    node1=self.node_group2.nodes[1],
                    node2=self.node_group2.nodes[0],
                    exclude_interfaces = self.exclude_interfaces,
                )
            case "star_1_n":
                if not self.node_group2:
                    print ("Warning! Both groups are mandatory for star_1_n topology.")
                    print (f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                if self.node_group1.group_node_count != 1:
                    print ("Warning! First node group should only have 1 node in a Star topology.")
                    print (f"Skipped connecting groups: {self.node_group1.group_name} and {self.node_group2.group_name}")
                    return
                for node2 in self.node_group2.nodes:
                    add_link_between_nodes(
                        node1=self.node_group1.nodes[0],
                        node2=node2,
                        exclude_interfaces = self.exclude_interfaces,
                    )
            case "straight_n_n":
                if not self.node_group2:
                    print ("Warning! Both groups are mandatory for straight_n_n topology.")
                    print (f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                # Connect all the members of the group1 and group2 one to one, if any group has greater number of nodes, trailing nodes are left out
                for i in range(len(self.node_group1.nodes)):
                    if i < len(self.node_group2.nodes):
                        add_link_between_nodes(
                            node1=self.node_group1.nodes[i],
                            node2=self.node_group2.nodes[i],
                            exclude_interfaces = self.exclude_interfaces,
                        )
            case "intra_b2b_n":
                # Connect back to back connections between members of group1 like node1-node2, node3-node4 etc
                # in odd number of nodes, last node is left out
                if self.node_group2:
                    print ("Warning! Second node group should be empty in intra_b2b_n topology.")
                    print (f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                i=0
                while i < len(self.node_group1.nodes) - 1:
                    add_link_between_nodes(
                        node1=self.node_group1.nodes[i],
                        node2=self.node_group1.nodes[i+1],
                        exclude_interfaces = self.exclude_interfaces,
                    )
                    i=i+2
            case "intra2_b2b_n":
                # same as intra_b2b_n, but connects 2 links between the nodes
                if self.node_group2:
                    print ("Warning! Second node group should be empty in intra2_b2b_n topology.")
                    print (f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                i=0
                while i < len(self.node_group1.nodes) - 1:
                    add_link_between_nodes(
                        node1=self.node_group1.nodes[i],
                        node2=self.node_group1.nodes[i+1],
                        exclude_interfaces = self.exclude_interfaces,
                    )
                    add_link_between_nodes(
                        node1=self.node_group1.nodes[i],
                        node2=self.node_group1.nodes[i+1],
                        exclude_interfaces = self.exclude_interfaces,
                    )
                    i=i+2
            case "full_mesh_n_n":
                if not self.node_group2:
                    print ("Warning! Both groups are mandatory for full_mesh_n_n topology.")
                    print (f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                super_group = self.node_group1.nodes + self.node_group2.nodes
                for i in range(len(super_group)):
                    for j in range(i+1,len(super_group)):
                        add_link_between_nodes(
                            node1=super_group[i],
                            node2=super_group[j],
                            exclude_interfaces = self.exclude_interfaces,
                        )

            case _:
                print (f"Error: Topology: {self.topology_type} type is not supported! Exiting...")
                sys.exit()