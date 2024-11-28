import urllib3
import yaml
import sys

from cml.client import *
from cml.lab import *
from cml.position import *
from wrapper.nodegroup import *
from wrapper.topology import *

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def read_from_yml(file_path: str) -> Any:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            # Load the YAML content
            data = yaml.safe_load(file)
            return data
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except PermissionError:
        print(f"Error: Permission denied when trying to read '{file_path}'.")
    except yaml.YAMLError as e:
        print(f"Error: Failed to parse YAML file '{file_path}'.")
        print(f"Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return None

def get_cml_pos(pos: dict) -> CMLPosition :
    if not pos:
        return None
    return CMLPosition(x = pos["x"], y = pos["y"])

def get_node_group_by_name(nglist: list, ng_name: str) -> NodeGroup:
    for ng in nglist:
        if ng.group_name == ng_name:
            return ng
    return None

def create_node_groups(ngroups: list, lab: CMLLab) -> list:
    node_groups = []
    for ng in ngroups:
        loc = get_cml_pos( ng.get("group_location", None) )
        adj_ngroup_name = ng.get("adjacent_to_group", None)
        adj_ngroup = get_node_group_by_name(node_groups, adj_ngroup_name)
        adj_pos = None
        if adj_ngroup:
            if adj_ngroup.group_last_node_position:
                adj_pos = adj_ngroup.group_last_node_position
        ng_instance = NodeGroup(
            group_name = ng.get("group_name", None),
            group_node_definition = ng.get("group_node_definition", None),
            group_node_names_prefix = ng.get("group_node_names_prefix", None),
            group_node_count = ng.get("group_node_count", None),
            interfaces_per_node = ng.get("interfaces_per_node", 10),
            group_configuration = ng.get("group_extra_configuration", ""),
            group_location = loc,
            adjacent_to_position = adj_pos,
            group_spread = ng.get("group_spread", None),
            group_intraspace = ng.get("group_intraspace", 80),
            group_mgmt_start_ip = ng.get("group_mgmt_start_ip", ""),
            group_mgmt_subnet = ng.get("group_mgmt_subnet", ""),
            group_mgmt_gw_ip = ng.get("group_mgmt_gw_ip", ""),
            group_image_definition = ng.get("group_image_definition", ""),
            delete_existing_nodes = ng.get("delete_existing_nodes", True),
            cml_lab = lab,
        )
        node_groups.append(ng_instance)
        ng_instance.build()
    return node_groups

def create_topology (topology_list: list, node_groups: list, lab: CMLLab) -> list:
    topologies = []
    for tp in topology_list:
        ng_name1 = tp.get("node_group1","")
        ng_name2 = tp.get("node_group2","")
        if ng_name1 == "":
            print ("node_group1 parameter in topology items is mandatory. Exiting...")
            sys.exit()
        ng_obj1 = get_node_group_by_name(nglist = node_groups, ng_name = ng_name1)
        ng_obj2 = get_node_group_by_name(nglist = node_groups, ng_name = ng_name2)
        tp_instance = Topology(
            node_group1= ng_obj1,
            node_group2= ng_obj2,
            exclude_interfaces= tp.get("exclude_interfaces",[]),
            topology_type= tp.get("topology_type","CLOS_N_N"),
        )
        topologies.append(tp_instance)
        tp_instance.build()
    return topologies

def main():
    # Read YAML
    data_from_yaml = read_from_yml(LAB_DATA_YAML)
    if not data_from_yaml:
        print ("No data parsed from YAML. Exiting...")
        sys.exit()
    base_uri = f'https://{data_from_yaml["CML"]["hostname"]}/api/v0'
    my_cml = CMLRESTClient(
        base_uri = base_uri,
        username = data_from_yaml["CML"]["username"],
        password = data_from_yaml["CML"]["password"],
    )
    labs_raw = data_from_yaml["labs"]
    for lab_raw in labs_raw:
        my_lab = CMLLab(my_cml)
        my_lab.create_lab(lab_title=lab_raw["title"], force_clean = lab_raw["force_clean"])
        node_groups_list_raw = lab_raw["node_groups"]
        node_groups = create_node_groups(ngroups = node_groups_list_raw, lab = my_lab)
        topology_list_raw = lab_raw["topology"]
        topology = create_topology(topology_list = topology_list_raw, node_groups = node_groups, lab = my_lab)

if __name__ == "__main__":
    main()