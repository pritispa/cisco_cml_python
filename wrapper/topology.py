from wrapper.nodegroup import *
from cml.node import *
from enum import Enum
from typing import Any
from cml.colors import print_warning, print_error

class ValidTopology(Enum):
   FULL_MESH_N_N = "FULL_MESH_N_N"
   CLOS_N_N = "CLOS_N_N"
   SQUARE_2_2 = "SQUARE_2_2"
   STAR_1_N = "STAR_1_N"
   STRAIGHT_N_N = "STRAIGHT_N_N"
   INTRA_GROUP_B2B_N = "INTRA_GROUP_B2B_N"
   INTRA_GROUP_B2B2_N = "INTRA_GROUP_B2B2_N"
   VPC_N_N = "VPC_N_N"
   def __contains__(self: type[Any], value: object) -> bool:
      return super().__contains__(value)

class Topology:
    def __init__(self,
                 node_group1: NodeGroup,
                 node_group2: NodeGroup = None,
                 exclude_interfaces: list = [],
                 topology_type: str = "CLOS_N_N",
                 existing_link_counts: dict = None,
    ) -> None:
        if topology_type.upper() not in ValidTopology:
            print_error(f"Topology type {topology_type} is not valid. Exiting...")
            sys.exit()
        self.topology_type = topology_type
        self.topology_type_enum = ValidTopology(topology_type.upper())
        self.node_group1 = node_group1
        self.node_group2 = node_group2
        self.exclude_interfaces = exclude_interfaces
        self.existing_link_counts = existing_link_counts
    
    # Calling build everytime will add additional cabling apart from any existing one.
    def build(self):
        match self.topology_type_enum:
            case ValidTopology.CLOS_N_N:
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for CLOS_N_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                for node1 in self.node_group1.nodes:
                    for node2 in self.node_group2.nodes:
                        add_link_between_nodes(
                            node1=node1,
                            node2=node2,
                            exclude_interfaces = self.exclude_interfaces,
                            existing_link_counts = self.existing_link_counts,
                        )
            case ValidTopology.SQUARE_2_2:
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for SQUARE_2_2 topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                if self.node_group1.group_node_count !=2 or self.node_group1.group_node_count !=2:
                    print_warning("Warning! Square topology can only form between 2 nodes from each group, that is total 4 nodes.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name} and {self.node_group2.group_name}")
                    return
                add_link_between_nodes(
                    node1=self.node_group1.nodes[0],
                    node2=self.node_group2.nodes[0],
                    exclude_interfaces = self.exclude_interfaces,
                    existing_link_counts = self.existing_link_counts,
                )
                add_link_between_nodes(
                    node1=self.node_group1.nodes[0],
                    node2=self.node_group1.nodes[1],
                    exclude_interfaces = self.exclude_interfaces,
                    existing_link_counts = self.existing_link_counts,
                )
                add_link_between_nodes(
                    node1=self.node_group2.nodes[1],
                    node2=self.node_group1.nodes[1],
                    exclude_interfaces = self.exclude_interfaces,
                    existing_link_counts = self.existing_link_counts,
                )
                add_link_between_nodes(
                    node1=self.node_group2.nodes[1],
                    node2=self.node_group2.nodes[0],
                    exclude_interfaces = self.exclude_interfaces,
                    existing_link_counts = self.existing_link_counts,
                )
            case ValidTopology.STAR_1_N:
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for STAR_1_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                if self.node_group1.group_node_count != 1:
                    print_warning("Warning! First node group should only have 1 node in a STAR_1_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name} and {self.node_group2.group_name}")
                    return
                for node2 in self.node_group2.nodes:
                    add_link_between_nodes(
                        node1=self.node_group1.nodes[0],
                        node2=node2,
                        exclude_interfaces = self.exclude_interfaces,
                        existing_link_counts = self.existing_link_counts,
                    )
            case ValidTopology.STRAIGHT_N_N:
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for STRAIGHT_N_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                # Connect all the members of the group1 and group2 one to one, if any group has greater number of nodes, trailing nodes are left out
                for i in range(len(self.node_group1.nodes)):
                    if i < len(self.node_group2.nodes):
                        add_link_between_nodes(
                            node1=self.node_group1.nodes[i],
                            node2=self.node_group2.nodes[i],
                            exclude_interfaces = self.exclude_interfaces,
                            existing_link_counts = self.existing_link_counts,
                        )
            case ValidTopology.INTRA_GROUP_B2B_N:
                # Connect back to back connections between members of group1 like node1-node2, node3-node4 etc
                # in odd number of nodes, last node is left out
                if self.node_group2:
                    print_warning("Warning! Second node group should be empty in INTRA_GROUP_B2B_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                i=0
                while i < len(self.node_group1.nodes) - 1:
                    add_link_between_nodes(
                        node1=self.node_group1.nodes[i],
                        node2=self.node_group1.nodes[i+1],
                        exclude_interfaces = self.exclude_interfaces,
                        existing_link_counts = self.existing_link_counts,
                    )
                    i=i+2
            case ValidTopology.INTRA_GROUP_B2B2_N:
                # same as INTRA_GROUP_B2B_N, but connects 2 links between the nodes
                if self.node_group2:
                    print_warning("Warning! Second node group should be empty in INTRA_GROUP_B2B2_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                i=0
                while i < len(self.node_group1.nodes) - 1:
                    add_link_between_nodes(
                        node1=self.node_group1.nodes[i],
                        node2=self.node_group1.nodes[i+1],
                        exclude_interfaces = self.exclude_interfaces,
                        existing_link_counts = self.existing_link_counts,
                    )
                    add_link_between_nodes(
                        node1=self.node_group1.nodes[i],
                        node2=self.node_group1.nodes[i+1],
                        exclude_interfaces = self.exclude_interfaces,
                        existing_link_counts = self.existing_link_counts,
                    )
                    i=i+2
            case ValidTopology.VPC_N_N:
                # Group1 nodes form vPC pairs: (0,1), (2,3), (4,5), ...
                # Group2 nodes are equally distributed and dual-homed to both nodes in their assigned pair
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for VPC_N_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                if self.node_group1.group_node_count < 2 or self.node_group1.group_node_count % 2 != 0:
                    print_warning("Warning! Group 1 must have an even number of nodes (>=2) for VPC_N_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name} and {self.node_group2.group_name}")
                    return
                num_pairs = len(self.node_group1.nodes) // 2
                num_hosts = len(self.node_group2.nodes)
                hosts_per_pair = num_hosts // num_pairs
                remainder = num_hosts % num_pairs
                host_idx = 0
                for p in range(num_pairs):
                    vpc_node_a = self.node_group1.nodes[p * 2]
                    vpc_node_b = self.node_group1.nodes[p * 2 + 1]
                    # First 'remainder' pairs get one extra host for even distribution
                    count = hosts_per_pair + (1 if p < remainder else 0)
                    for _ in range(count):
                        add_link_between_nodes(
                            node1=vpc_node_a,
                            node2=self.node_group2.nodes[host_idx],
                            exclude_interfaces = self.exclude_interfaces,
                            existing_link_counts = self.existing_link_counts,
                        )
                        add_link_between_nodes(
                            node1=vpc_node_b,
                            node2=self.node_group2.nodes[host_idx],
                            exclude_interfaces = self.exclude_interfaces,
                            existing_link_counts = self.existing_link_counts,
                        )
                        host_idx += 1
            case ValidTopology.FULL_MESH_N_N:
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for FULL_MESH_N_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return
                super_group = self.node_group1.nodes + self.node_group2.nodes
                for i in range(len(super_group)):
                    for j in range(i+1,len(super_group)):
                        add_link_between_nodes(
                            node1=super_group[i],
                            node2=super_group[j],
                            exclude_interfaces = self.exclude_interfaces,
                            existing_link_counts = self.existing_link_counts,
                        )

            case _:
                print_error(f"Error: Topology:" + str({self.topology_type_enum}) + "type is not supported! Exiting...")
                sys.exit()