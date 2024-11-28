import sys
from cml.position import CMLPosition
from cml.lab import CMLLab
from cml.link import CMLLink

class CMLInterface:
    def __init__(self) -> None:
        self.id = ""
        self.lab_id = ""
        self.node = ""
        self.label = ""
        self.slot = 0
        self.type = ""
        self.mac_address = ""
        self.is_connected = False
        self.state = ""
    
    def set_interface_parameters(self, parameters: dict):
        self.id = parameters["id"]
        self.lab_id = parameters["lab_id"]
        self.node = parameters["node"]
        self.label = parameters["label"]
        self.slot = parameters["slot"]
        self.type = parameters["type"]
        self.mac_address = parameters["mac_address"]
        self.is_connected = parameters["is_connected"]
        self.state = parameters["state"]

class CMLNode:

    def __init__(self, cml_lab: CMLLab) -> None:
        self.id = ""
        self.label = ""
        self.node_definition = ""
        self.image_definition = ""
        self.configuration = ""
        # lab container of this node
        self.cml_lab = cml_lab
        self.position = {}
        self.target_uri=f"/labs/{cml_lab.id}/nodes"
        # Node is created with 10 interfaces by default
        self.interface_count = 10
        self.interfaces = []
    
    def create_node (
            self,
            label: str,
            position: CMLPosition,
            image_definition: str = "",
            configuration: str = "",
            node_definition: str = "nxosv9000",
            interface_count: int = 10,
            force_delete = False,
        ) -> None:
        existing_node_ids = self.cml_lab.existing_node_ids_list
        node_exists = self.check_node_exists(label = label, node_ids = existing_node_ids, lab_id=self.cml_lab.id)
        if node_exists and not force_delete:
            print(f"Error: Failed to create the node with name {label}. It already exists in lab {self.cml_lab.lab_title}!")
            sys.exit()
        if node_exists and force_delete:
            print (f"Deleting the existing node, force delete is set to true.")
            target_uri = f"/labs/{self.cml_lab.id}/nodes/{node_exists}"
            r = self.cml_lab.client.cml_rest_req(
                target_uri = target_uri,
                method ="DELETE"
            )
            if not r:
                print (f"Failed to delete already existing node: {label} - {node_exists} in lab {self.cml_lab.id}. Exiting...")
                sys.exit()
            # Update the lab data structure to refresh the existing node ids
            self.cml_lab.existing_node_ids_list = CMLLab.list_lab_node_ids(lab_id=self.cml_lab.id,cml_rest_client=self.cml_lab.client)

        print(f"Creating Node {label}...")
        #omit empty parameters from payload
        rest_payload = {key: value for key, value in {
                "x": position.x,
                "y": position.y,
                "label": label,
                "node_definition": node_definition,
                "image_definition": image_definition,
                "configuration": configuration,
            }.items() if value or value ==0}
        # DEBUG
        r = self.cml_lab.client.cml_rest_req(
            target_uri = self.target_uri,
            method ="POST",
            payload_data = rest_payload
        )
        if not r:
            print (f"Failed to create the node {label}. Exiting...")
            sys.exit()
        node_dict = r.json()
        self.id = node_dict["id"]
        self.label = label
        self.position = position
        self.node_definition = node_definition
        self.image_definition = image_definition
        self.configuration = configuration
        self.interface_count = interface_count
        self.add_node_interfaces()
    
    def check_node_exists(self, label: str, node_ids: list, lab_id: str) -> str:
        # Check if the node exists:
        for node_id in node_ids:
            target_uri = f"/labs/{lab_id}/nodes/{node_id}"
            r = self.cml_lab.client.cml_rest_req(
                target_uri = target_uri,
                method ="GET"
            )
            if not r:
                print (f"Failed to get node details, for already existing node: {node_id}. Ignoring...")
                continue
            node_det = r.json()
            if node_det["label"] == label:
                return node_id
        return None
    
    def add_node_interfaces (self):
        if self.interface_count == 0:
            return
        target_uri = f"/labs/{self.cml_lab.id}/interfaces"
        rest_payload = {
            "node": self.id,
            #slot: 0 is a valid value and is the only value for external connector node
            "slot": self.interface_count - 1
        }
        r = self.cml_lab.client.cml_rest_req(
            target_uri = target_uri,
            method ="POST",
            payload_data = rest_payload
        )
        if not r:
            print (f"Failed to add interfaces to the node {self.label}. Exiting...")
            sys.exit()
        interfaces_parameters = r.json()
        for interface_parameter in interfaces_parameters:
            interface = CMLInterface()
            interface.set_interface_parameters(interface_parameter)
            self.interfaces.append(interface)
        return
    
    def refresh_node_interfaces_status(self):
        target_uri = f"/labs/{self.cml_lab.id}/nodes/{self.id}/interfaces"
        r = self.cml_lab.client.cml_rest_req(
            target_uri = target_uri,
            method ="GET",
        )
        if not r:
            print (f"Failed to refresh interface-status of the node {self.label}. Exiting...")
            sys.exit()
        intf_list = r.json()
        interfaces_parameters = []
        for intf_id in intf_list:
            target_uri = f"/labs/{self.cml_lab.id}/interfaces/{intf_id}"
            r = self.cml_lab.client.cml_rest_req(
                target_uri = target_uri,
                method ="GET",
            )
            interfaces_parameters.append(r.json())
            if not r:
                print (f"Failed to fetch interface details for interface {intf_id} of the node {self.label}. Ignoring.")
                continue
        #Flush interfaces status
        self.interfaces = []
        for interface_parameter in interfaces_parameters:
            interface = CMLInterface()
            interface.set_interface_parameters(interface_parameter)
            self.interfaces.append(interface)
    
    def set_node_interfaces_connected_status(self, intf_id: str, is_connected: bool):
        for interface in self.interfaces:
            if interface.id == intf_id:
                interface.is_connected = is_connected
                return
        print (f"Warning: Interface {intf_id} not found on node {self.label} its connection status was not updated.")
        return None
    
    def get_next_free_node_interface_id(self, avoid_interfaces: list) -> str:
        #self.refresh_node_interfaces_status()
        for cml_intf in self.interfaces:
            avoid_this = False
            if cml_intf.type != "physical":
                continue
            if cml_intf.is_connected:
                continue
            for avoid_intf in avoid_interfaces:
                if cml_intf.label == avoid_intf:
                    avoid_this = True
                    break
            if avoid_this:
                continue
            return cml_intf.id
        return None

def add_link_between_nodes(node1: CMLNode, node2: CMLNode, exclude_interfaces: list):
    node1_intf = node1.get_next_free_node_interface_id(avoid_interfaces = exclude_interfaces)
    node2_intf = node2.get_next_free_node_interface_id(avoid_interfaces = exclude_interfaces)
    if node1_intf == None:
        print (f"No free interface found on {node1.label}")
        print (f"Could not create link between node {node1.label} and {node2.label}")
        return None
    if node2_intf == None:
        print (f"No free interface found on {node2.label}")
        print (f"Could not create link between node {node2.label} and {node2.label}")
        return None
    if node1.cml_lab.id != node2.cml_lab.id:
        print (f"Can not connect 2 nodes present in different labs. Node1: {node1.label}, Node2: {node2.label}")
    link = CMLLink()
    intf_tuple = (node1_intf, node2_intf)
    link_id = link.connect_link(node1.cml_lab, intf_tuple)
    if link_id:
        print (f"Link connected between {node1.label}, {node2.label}!")
        node1.set_node_interfaces_connected_status(intf_id = node1_intf, is_connected = True)
        node2.set_node_interfaces_connected_status(intf_id = node2_intf, is_connected = True)
        return link_id
    return None