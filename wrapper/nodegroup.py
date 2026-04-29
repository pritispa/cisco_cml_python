import sys

from cml.lab import CMLLab
from cml.position import CMLPosition
from cml.node import CMLNode
from cml.colors import print_error
from wrapper.mgmt import *

MAX_NODES_PER_ROW = 30
ROW_SPACING = 80

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
            group_extra_configuration: str = "",
            interfaces_per_node: int = 10,
            group_mgmt_subnet: str = "",
            group_mgmt_start_ip: str = "",
            group_mgmt_gw_ip: str = "",
            group_mgmt_dhcp: bool = False,
            # It is recommended to keep delete_existing_nodes = true, since any existing nodes will not be cabled/connected
            delete_existing_nodes: bool = True,
            group_delete_existing: bool = False,
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
        if group_intraspace < 40 or group_intraspace % 40 != 0:
            print_error("Error, creating group. group_intraspace must be >= 40 and a multiple of 40. Exiting...")
            sys.exit()
        self.group_intraspace = group_intraspace
        spread = ("horizontal","vertical")
        if group_spread not in spread:
            print_error("Error, creating group. group spread can either be horizontal or vertical. Exiting...")
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
        self.group_mgmt_dhcp = group_mgmt_dhcp
        self.group_extra_configuration = group_extra_configuration
        self.interfaces_per_node = interfaces_per_node
        self.delete_existing_nodes = delete_existing_nodes
        self.group_delete_existing = group_delete_existing
        self.nodes = []
    
    def build(self, existing_nodes_by_label: dict = None):
        # flush any existing nodes
        self.nodes = []
        for i in range (self.group_node_count):
            node = CMLNode(self.cml_lab)
            label = self.get_node_name(i)
            configuration, mgmt_ip = derive_node_configuration(
                node_definition=self.group_node_definition,
                hostname=label,
                group_mgmt_subnet=self.group_mgmt_subnet,
                group_mgmt_start_ip=self.group_mgmt_start_ip,
                group_mgmt_gw_ip=self.group_mgmt_gw_ip,
                group_mgmt_dhcp=self.group_mgmt_dhcp,
                extra_configuration=self.group_extra_configuration,
            )
            node.mgmt_ip = mgmt_ip
            if existing_nodes_by_label is not None and label in existing_nodes_by_label and not self.group_delete_existing:
                node.create_or_update_node(
                    label=label,
                    position = self.get_node_coordinates(i),
                    image_definition = self.group_image_definition,
                    configuration = configuration,
                    node_definition = self.group_node_definition,
                    interface_count= self.interfaces_per_node,
                    existing_node_data = existing_nodes_by_label[label],
                )
            else:
                node.create_node(
                    label=label,
                    position = self.get_node_coordinates(i),
                    image_definition = self.group_image_definition,
                    configuration = configuration,
                    node_definition = self.group_node_definition,
                    interface_count= self.interfaces_per_node,
                    force_delete=self.delete_existing_nodes or self.group_delete_existing,
                )
            self.nodes.append(node)
            if i == 0:
                self.group_first_node_position = self.get_node_coordinates(i)
            if i == self.group_node_count - 1:
                self.group_last_node_position = self.get_node_coordinates(i)
        return
    
    def get_node_coordinates(self, i: int):
        row = i // MAX_NODES_PER_ROW
        col = i % MAX_NODES_PER_ROW
        if self.group_spread == "horizontal":
            x_pos = self.group_location.x + col * self.group_intraspace
            y_pos = self.group_location.y + row * ROW_SPACING
        else:
            x_pos = self.group_location.x + row * ROW_SPACING
            y_pos = self.group_location.y - col * self.group_intraspace
        cml_pos = CMLPosition(x=x_pos, y=y_pos)
        return cml_pos
    
    def get_node_name(self, i: int):
        return self.group_node_names_prefix + str(i+1)