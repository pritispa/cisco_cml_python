import sys

from cml.lab import CMLLab
from cml.position import CMLPosition
from cml.node import CMLNode
from wrapper.mgmt import *

class NodeGroup:
    def __init__(
            self,
            # Group name is an arbitary name
            group_name: str,
            # This prefix will be used to create the unique node name in CML with a suffix of node number
            group_node_names_prefix: str,
            group_spread: str,
            group_node_count: int,
            cml_lab: CMLLab,
            group_node_definition: str,
            group_intraspace: int = 80,
            group_image_definition: str = "",
            group_configuration: str = "",
            interfaces_per_node: int = 10,
            group_mgmt_subnet: str = "",
            group_mgmt_start_ip: str = "",
            group_mgmt_gw_ip: str = "",
            # It is recommended to keep delete_existing_nodes = true, since any existing nodes will not be cabled/connected
            delete_existing_nodes: bool = True,
            group_location: CMLPosition = None,
            adjacent_to_position: CMLPosition = None, # specify a position to be adjacent to
            group_first_node_position: CMLPosition = None, #automatically populated
            group_last_node_position: CMLPosition = None, #automatically populated
    ) -> None:
        self.group_name = group_name
        if not group_location:
            self.group_location = CMLPosition(x=0, y=0)
        else:
            self.group_location = group_location
        if group_intraspace % 40 != 0:
            print ("Error, creating group. group interspace should be a multiple of 40. Exiting...")
            sys.exit()
        self.group_intraspace = group_intraspace
        spread = ("horizontal","vertical")
        if group_spread not in spread:
            print ("Error, creating group. group spread can either be horizontal or vertical. Exiting...")
            sys.exit()
        self.group_spread = group_spread #horizontal or vertical
        if adjacent_to_position:
            if group_spread == "horizontal":
                self.group_location.x = adjacent_to_position.x + self.group_intraspace
                self.group_location.y = adjacent_to_position.y
            else:
                self.group_location.y = adjacent_to_position.y - self.group_intraspace
                self.group_location.x = adjacent_to_position.x
        self.group_node_count = group_node_count
        self.group_node_names_prefix = group_node_names_prefix
        self.cml_lab = cml_lab
        self.group_node_definition = group_node_definition
        self.group_image_definition = group_image_definition
        self.group_mgmt_subnet = group_mgmt_subnet
        self.group_mgmt_start_ip = group_mgmt_start_ip
        self.group_mgmt_gw_ip = group_mgmt_gw_ip
        base_config = get_node_base_config(group_node_definition)
        if group_configuration:
            self.group_configuration = base_config + group_configuration
        else:
            self.group_configuration = base_config
        self.interfaces_per_node = interfaces_per_node
        self.delete_existing_nodes = delete_existing_nodes
        self.nodes = []
    
    def build(self):
        # flush any existing nodes
        self.nodes = []
        mgmt_config_push = False
        mgmt_config = ""
        if self.group_mgmt_subnet or self.group_mgmt_start_ip or self.group_mgmt_gw_ip:
            mgmt_config_push = True
        for i in range (self.group_node_count):
            node = CMLNode(self.cml_lab)
            if mgmt_config_push:
                mgmt_config = derive_mgmt_config(
                self.group_node_definition,
                self.group_mgmt_subnet,
                self.group_mgmt_start_ip,
                self.group_mgmt_gw_ip,
                self.get_node_name(i),
            )
            node.create_node(
                label=self.get_node_name(i),
                position = self.get_node_coordinates(i),
                image_definition = self.group_image_definition,
                configuration = self.group_configuration + mgmt_config,
                node_definition = self.group_node_definition,
                interface_count= self.interfaces_per_node,
                force_delete=self.delete_existing_nodes,
            )
            self.nodes.append(node)
            if i == 0:
                self.group_first_node_position = self.get_node_coordinates(i)
            if i == self.group_node_count - 1:
                self.group_last_node_position = self.get_node_coordinates(i)
        return
    
    def get_node_coordinates(self, i: int):
        if self.group_spread == "horizontal":
            x_pos = self.group_location.x + i*self.group_intraspace
            y_pos = self.group_location.y
        else:
            x_pos = self.group_location.x
            y_pos = self.group_location.y - i*self.group_intraspace
        cml_pos = CMLPosition(x=x_pos, y=y_pos)
        return cml_pos
    
    def get_node_name(self, i: int):
        return self.group_node_names_prefix + str(i+1)