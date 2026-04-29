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
    
    def _add_link(self, node1, node2):
        """Wrap add_link_between_nodes, collecting connection records."""
        result = add_link_between_nodes(
            node1=node1, node2=node2,
            exclude_interfaces=self.exclude_interfaces,
            existing_link_counts=self.existing_link_counts,
        )
        if isinstance(result, dict):
            self._records.append(result)
        return result

    # Calling build everytime will add additional cabling apart from any existing one.
    def build(self):
        self._records = []
        match self.topology_type_enum:
            case ValidTopology.CLOS_N_N:
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for CLOS_N_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return self._records
                for node1 in self.node_group1.nodes:
                    for node2 in self.node_group2.nodes:
                        self._add_link(node1, node2)
            case ValidTopology.SQUARE_2_2:
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for SQUARE_2_2 topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return self._records
                if self.node_group1.group_node_count !=2 or self.node_group1.group_node_count !=2:
                    print_warning("Warning! Square topology can only form between 2 nodes from each group, that is total 4 nodes.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name} and {self.node_group2.group_name}")
                    return self._records
                self._add_link(self.node_group1.nodes[0], self.node_group2.nodes[0])
                self._add_link(self.node_group1.nodes[0], self.node_group1.nodes[1])
                self._add_link(self.node_group2.nodes[1], self.node_group1.nodes[1])
                self._add_link(self.node_group2.nodes[1], self.node_group2.nodes[0])
            case ValidTopology.STAR_1_N:
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for STAR_1_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return self._records
                if self.node_group1.group_node_count != 1:
                    print_warning("Warning! First node group should only have 1 node in a STAR_1_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name} and {self.node_group2.group_name}")
                    return self._records
                for node2 in self.node_group2.nodes:
                    self._add_link(self.node_group1.nodes[0], node2)
            case ValidTopology.STRAIGHT_N_N:
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for STRAIGHT_N_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return self._records
                # Connect all the members of the group1 and group2 one to one, if any group has greater number of nodes, trailing nodes are left out
                for i in range(len(self.node_group1.nodes)):
                    if i < len(self.node_group2.nodes):
                        self._add_link(self.node_group1.nodes[i], self.node_group2.nodes[i])
            case ValidTopology.INTRA_GROUP_B2B_N:
                # Connect back to back connections between members of group1 like node1-node2, node3-node4 etc
                # in odd number of nodes, last node is left out
                if self.node_group2:
                    print_warning("Warning! Second node group should be empty in INTRA_GROUP_B2B_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return self._records
                i=0
                while i < len(self.node_group1.nodes) - 1:
                    self._add_link(self.node_group1.nodes[i], self.node_group1.nodes[i+1])
                    i=i+2
            case ValidTopology.INTRA_GROUP_B2B2_N:
                # same as INTRA_GROUP_B2B_N, but connects 2 links between the nodes
                if self.node_group2:
                    print_warning("Warning! Second node group should be empty in INTRA_GROUP_B2B2_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return self._records
                i=0
                while i < len(self.node_group1.nodes) - 1:
                    self._add_link(self.node_group1.nodes[i], self.node_group1.nodes[i+1])
                    self._add_link(self.node_group1.nodes[i], self.node_group1.nodes[i+1])
                    i=i+2
            case ValidTopology.VPC_N_N:
                # Group1 nodes form vPC pairs: (0,1), (2,3), (4,5), ...
                # Group2 nodes are equally distributed and dual-homed to both nodes in their assigned pair
                # If a leaf pair runs out of ports, hosts spill to the next available pair.
                # If no pair has capacity (at least one leaf in every pair is full), error out.
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for VPC_N_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return self._records
                if self.node_group1.group_node_count < 2 or self.node_group1.group_node_count % 2 != 0:
                    print_warning("Warning! Group 1 must have an even number of nodes (>=2) for VPC_N_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name} and {self.node_group2.group_name}")
                    return self._records

                def _has_free_port(node):
                    return node.get_next_free_node_interface_id(avoid_interfaces=self.exclude_interfaces) is not None

                num_pairs = len(self.node_group1.nodes) // 2
                num_hosts = len(self.node_group2.nodes)
                hosts_per_pair = num_hosts // num_pairs
                remainder = num_hosts % num_pairs

                # Build initial assignment: list of (pair_index, host_count)
                pair_assignments = []
                for p in range(num_pairs):
                    count = hosts_per_pair + (1 if p < remainder else 0)
                    pair_assignments.append(count)

                host_idx = 0
                for p in range(num_pairs):
                    vpc_node_a = self.node_group1.nodes[p * 2]
                    vpc_node_b = self.node_group1.nodes[p * 2 + 1]
                    count = pair_assignments[p]
                    for _ in range(count):
                        host_node = self.node_group2.nodes[host_idx]
                        # Check if both leaves in this pair have free ports
                        a_free = _has_free_port(vpc_node_a)
                        b_free = _has_free_port(vpc_node_b)
                        if not a_free or not b_free:
                            # Try to find another pair with capacity
                            found_pair = False
                            for alt_p in range(num_pairs):
                                if alt_p == p:
                                    continue
                                alt_a = self.node_group1.nodes[alt_p * 2]
                                alt_b = self.node_group1.nodes[alt_p * 2 + 1]
                                if _has_free_port(alt_a) and _has_free_port(alt_b):
                                    print_warning(f"Leaf pair ({vpc_node_a.label}, {vpc_node_b.label}) has no free ports. "
                                                  f"Spilling host {host_node.label} to pair ({alt_a.label}, {alt_b.label}).")
                                    vpc_node_a = alt_a
                                    vpc_node_b = alt_b
                                    found_pair = True
                                    break
                            if not found_pair:
                                print_error(f"No leaf pair has capacity for a valid vPC connection for host {host_node.label}. "
                                            f"Every leaf pair has at least one leaf with no free ports.")
                                print_error(f"Aborting VPC_N_N topology between {self.node_group1.group_name} and {self.node_group2.group_name}.")
                                return self._records
                        self._add_link(vpc_node_a, host_node)
                        self._add_link(vpc_node_b, host_node)
                        host_idx += 1
            case ValidTopology.FULL_MESH_N_N:
                if not self.node_group2:
                    print_warning("Warning! Both groups are mandatory for FULL_MESH_N_N topology.")
                    print_warning(f"Skipped connecting groups: {self.node_group1.group_name}")
                    return self._records
                super_group = self.node_group1.nodes + self.node_group2.nodes
                for i in range(len(super_group)):
                    for j in range(i+1,len(super_group)):
                        self._add_link(super_group[i], super_group[j])

            case _:
                print_error(f"Error: Topology:" + str({self.topology_type_enum}) + "type is not supported! Exiting...")
                sys.exit()
        return self._records