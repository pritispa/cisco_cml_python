import sys
from cml.position import CMLPosition
from cml.lab import CMLLab
from cml.link import CMLLink
from cml.colors import print_create, print_update, print_delete, print_warning, print_error

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
            print_error(f"Error: Failed to create the node with name {label}. It already exists in lab {self.cml_lab.lab_title}!")
            sys.exit()
        if node_exists and force_delete:
            print_delete(f"Deleting the existing node, force delete is set to true.")
            target_uri = f"/labs/{self.cml_lab.id}/nodes/{node_exists}"
            r = self.cml_lab.client.cml_rest_req(
                target_uri = target_uri,
                method ="DELETE"
            )
            if not r:
                print_error(f"Failed to delete already existing node: {label} - {node_exists} in lab {self.cml_lab.id}. Exiting...")
                sys.exit()
            # Update the lab data structure to refresh the existing node ids
            self.cml_lab.existing_node_ids_list = CMLLab.list_lab_node_ids(lab_id=self.cml_lab.id,cml_rest_client=self.cml_lab.client)

        print_create(f"Creating Node {label}...")
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
            print_error(f"Failed to create the node {label}. Exiting...")
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
                print_warning(f"Failed to get node details, for already existing node: {node_id}. Ignoring...")
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
            print_error(f"Failed to add interfaces to the node {self.label}. Exiting...")
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
            print_error(f"Failed to refresh interface-status of the node {self.label}. Exiting...")
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
                print_warning(f"Failed to fetch interface details for interface {intf_id} of the node {self.label}. Ignoring.")
                continue
        #Flush interfaces status
        self.interfaces = []
        for interface_parameter in interfaces_parameters:
            interface = CMLInterface()
            interface.set_interface_parameters(interface_parameter)
            self.interfaces.append(interface)
    
    def load_from_existing(self, node_data: dict):
        self.id = node_data["id"]
        self.label = node_data["label"]
        self.node_definition = node_data.get("node_definition", "")
        self.image_definition = node_data.get("image_definition") or ""
        self.configuration = node_data.get("configuration") or ""
        self.position = CMLPosition(x=node_data.get("x", 0), y=node_data.get("y", 0))
        self.refresh_node_interfaces_status()

    def stop_node(self):
        target_uri = f"/labs/{self.cml_lab.id}/nodes/{self.id}/state/stop"
        r = self.cml_lab.client.cml_rest_req(
            target_uri = target_uri,
            method ="PUT"
        )
        if not r:
            print_warning(f"Warning: Failed to stop node {self.label} (may already be stopped).")
        else:
            print_update(f"Node {self.label} stopped.")

    def wipe_node(self):
        target_uri = f"/labs/{self.cml_lab.id}/nodes/{self.id}/wipe_disks"
        r = self.cml_lab.client.cml_rest_req(
            target_uri = target_uri,
            method ="PUT"
        )
        if not r:
            print_warning(f"Warning: Failed to wipe node {self.label}.")
        else:
            print_update(f"Node {self.label} wiped.")

    def update_node(self, patch_payload: dict):
        target_uri = f"/labs/{self.cml_lab.id}/nodes/{self.id}"
        r = self.cml_lab.client.cml_rest_req(
            target_uri = target_uri,
            method ="PATCH",
            payload_data = patch_payload
        )
        if not r:
            print_error(f"Failed to update node {self.label}. Exiting...")
            sys.exit()
        print_update(f"Node {self.label} updated.")

    def delete_node(self):
        target_uri = f"/labs/{self.cml_lab.id}/nodes/{self.id}"
        r = self.cml_lab.client.cml_rest_req(
            target_uri = target_uri,
            method ="DELETE"
        )
        if not r:
            print_error(f"Failed to delete existing node {self.label}. Exiting...")
            sys.exit()
        self.cml_lab.existing_node_ids_list = CMLLab.list_lab_node_ids(
            lab_id=self.cml_lab.id, cml_rest_client=self.cml_lab.client)

    def adjust_interfaces(self, current_count: int, desired_count: int):
        if desired_count > current_count:
            target_uri = f"/labs/{self.cml_lab.id}/interfaces"
            rest_payload = {
                "node": self.id,
                "slot": desired_count - 1
            }
            r = self.cml_lab.client.cml_rest_req(
                target_uri = target_uri,
                method ="POST",
                payload_data = rest_payload
            )
            if not r:
                print_error(f"Failed to add interfaces to node {self.label}. Exiting...")
                sys.exit()
            interfaces_parameters = r.json()
            for interface_parameter in interfaces_parameters:
                interface = CMLInterface()
                interface.set_interface_parameters(interface_parameter)
                self.interfaces.append(interface)
            print_update(f"Node {self.label}: interfaces increased from {current_count} to {desired_count}.")
        elif desired_count < current_count:
            physical_intfs = sorted(
                [i for i in self.interfaces if i.type == "physical"],
                key=lambda x: x.slot, reverse=True
            )
            to_delete = current_count - desired_count
            for idx in range(to_delete):
                intf = physical_intfs[idx]
                if intf.is_connected:
                    print_warning(f"Warning: Interface {intf.label} on {self.label} is connected, cannot delete. Skipping interface reduction.")
                    return
                target_uri = f"/labs/{self.cml_lab.id}/interfaces/{intf.id}"
                r = self.cml_lab.client.cml_rest_req(
                    target_uri = target_uri,
                    method ="DELETE"
                )
                if not r:
                    print_warning(f"Warning: Failed to delete interface {intf.label} from node {self.label}.")
            self.refresh_node_interfaces_status()
            print_update(f"Node {self.label}: interfaces reduced from {current_count} to {desired_count}.")

    def create_or_update_node(
            self,
            label: str,
            position: CMLPosition,
            image_definition: str = "",
            configuration: str = "",
            node_definition: str = "nxosv9000",
            interface_count: int = 10,
            existing_node_data: dict = None,
        ) -> str:
        if existing_node_data is None:
            self.create_node(
                label=label, position=position,
                image_definition=image_definition, configuration=configuration,
                node_definition=node_definition, interface_count=interface_count,
                force_delete=False,
            )
            return "created"

        self.load_from_existing(existing_node_data)

        # node_definition cannot be updated via PATCH — must delete and recreate
        if self.node_definition != node_definition:
            print_delete(f"Node {label}: node_definition changed ({self.node_definition} -> {node_definition}), recreating...")
            self.stop_node()
            self.wipe_node()
            self.delete_node()
            self.__init__(self.cml_lab)
            self.create_node(
                label=label, position=position,
                image_definition=image_definition, configuration=configuration,
                node_definition=node_definition, interface_count=interface_count,
                force_delete=False,
            )
            return "recreated"

        needs_stop_wipe = False
        patch_payload = {}

        # image_definition
        existing_img = self.image_definition or ""
        desired_img = image_definition or ""
        if existing_img != desired_img:
            needs_stop_wipe = True
            patch_payload["image_definition"] = desired_img if desired_img else None

        # interface count
        physical_count = len([i for i in self.interfaces if i.type == "physical"])
        intf_changed = (physical_count != interface_count)
        if intf_changed:
            needs_stop_wipe = True

        # configuration
        existing_cfg = self.configuration or ""
        desired_cfg = configuration or ""
        if existing_cfg != desired_cfg:
            patch_payload["configuration"] = desired_cfg

        # position
        if self.position.x != position.x or self.position.y != position.y:
            patch_payload["x"] = position.x
            patch_payload["y"] = position.y

        if not needs_stop_wipe and not patch_payload:
            print_update(f"Node {label}: parameters match, skipping.")
            return "unchanged"

        if needs_stop_wipe:
            print_update(f"Node {label}: requires stop and wipe for update.")
            self.stop_node()
            self.wipe_node()

        if patch_payload:
            self.update_node(patch_payload)

        if intf_changed:
            self.adjust_interfaces(physical_count, interface_count)

        return "updated"

    def set_node_interfaces_connected_status(self, intf_id: str, is_connected: bool):
        for interface in self.interfaces:
            if interface.id == intf_id:
                interface.is_connected = is_connected
                return
        print_warning(f"Warning: Interface {intf_id} not found on node {self.label} its connection status was not updated.")
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

def add_link_between_nodes(node1: CMLNode, node2: CMLNode, exclude_interfaces: list, existing_link_counts: dict = None):
    # In update mode, check if a link between these two nodes already exists
    if existing_link_counts is not None:
        pair_key = frozenset([node1.id, node2.id])
        if existing_link_counts.get(pair_key, 0) > 0:
            existing_link_counts[pair_key] -= 1
            print_update(f"Link between {node1.label} and {node2.label} already exists, skipping.")
            return "existing"

    node1_intf = node1.get_next_free_node_interface_id(avoid_interfaces = exclude_interfaces)
    node2_intf = node2.get_next_free_node_interface_id(avoid_interfaces = exclude_interfaces)
    if node1_intf == None:
        print_error(f"No free interface found on {node1.label}")
        print_error(f"Could not create link between node {node1.label} and {node2.label}")
        return None
    if node2_intf == None:
        print_error(f"No free interface found on {node2.label}")
        print_error(f"Could not create link between node {node2.label} and {node2.label}")
        return None
    if node1.cml_lab.id != node2.cml_lab.id:
        print_error(f"Can not connect 2 nodes present in different labs. Node1: {node1.label}, Node2: {node2.label}")
    link = CMLLink()
    intf_tuple = (node1_intf, node2_intf)
    link_id = link.connect_link(node1.cml_lab, intf_tuple)
    if link_id:
        print_create(f"Link connected between {node1.label}, {node2.label}!")
        node1.set_node_interfaces_connected_status(intf_id = node1_intf, is_connected = True)
        node2.set_node_interfaces_connected_status(intf_id = node2_intf, is_connected = True)
        return link_id
    return None