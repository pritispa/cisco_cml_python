import urllib3

from cml.client import *
from cml.lab import *
from cml.position import *
from wrapper.nodegroup import *
from wrapper.topology import *

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def main():
    username = "admin"
    password = "test"
    base_uri = "https://172.25.74.154/api/v0"

    my_cml = CMLRESTClient(
        base_uri = base_uri,
        username = username,
        password = password
    )
    # Create lab
    my_lab1 = CMLLab(my_cml)
    my_lab1.create_lab(lab_title="testlab123", force_clean = True)

    # Lab external
    lab_external_conn_group = NodeGroup(
        group_node_definition="external_connector",
        group_name= "lab_ext_connection",
        group_node_names_prefix = "lab_ext",
        group_location = CMLPosition(x=0, y=-440),
        group_spread = "horizontal",
        group_node_count = 1,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=1, # ext connection allows only 1 interface
        delete_existing_nodes= True,
    )
    lab_external_conn_group.build()
    # lab l2 unmanaged switch, will be used for mgmt0 to outside world connectivity
    unmanaged_switch_group = NodeGroup(
        group_node_definition="unmanaged_switch",
        group_name= "unmanaged switches",
        group_node_names_prefix = "un_switch",
        group_spread = "horizontal",
        group_location = CMLPosition(x=0, y=-360),
        group_node_count = 1,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=30,
        delete_existing_nodes= True,
    )
    unmanaged_switch_group.build()
    # unmanged switch to external world connection:
    common_mgmt_topology = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=lab_external_conn_group, 
        topology_type="straight_n_n", # no exclude interfaces are set
    )
    common_mgmt_topology.build()

    # msite isn cloud device
    site12_msite_isn_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site12_msite",
        group_node_names_prefix = "s12msite",
        group_location = CMLPosition(x=520, y=-360),
        group_spread = "horizontal",
        group_node_count = 1,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=10,
        delete_existing_nodes= True,
    )
    site12_msite_isn_group.build()
    


    # Create node groups (and nodes within them)
    site1_leaf_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site1_leafs",
        group_node_names_prefix = "leaf",
        group_mgmt_subnet="192.168.1.0/24",
        group_mgmt_start_ip="192.168.1.112",
        group_mgmt_gw_ip="192.168.1.254",
        group_location = CMLPosition(x=0, y=120),
        group_spread = "horizontal",
        group_node_count = 4,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=10,
        delete_existing_nodes= True,
    )
    site1_leaf_group.build()

    site1_spine_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site1_spines",
        group_node_names_prefix = "spine",
        group_mgmt_subnet="192.168.1.0/24",
        group_mgmt_start_ip="192.168.1.112",
        group_mgmt_gw_ip="192.168.1.254",
        group_location = CMLPosition(x=0, y=0),
        group_spread = "horizontal",
        group_node_count = 2,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=20,
        delete_existing_nodes= True,
    )
    site1_spine_group.build()

    site1_bleaf_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site1_borders",
        group_node_names_prefix = "bleaf",
        group_mgmt_subnet="192.168.1.0/24",
        group_mgmt_start_ip="192.168.1.112",
        group_mgmt_gw_ip="192.168.1.254",
        adjacent_to_position = site1_leaf_group.group_last_node_position,
        group_spread = "horizontal",
        group_node_count = 2,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=10,
        delete_existing_nodes= True,
    )
    site1_bleaf_group.build()

    site1_wan_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site1_wan",
        group_node_names_prefix = "wan",
        group_mgmt_subnet="192.168.1.0/24",
        group_mgmt_start_ip="192.168.1.112",
        group_mgmt_gw_ip="192.168.1.254",
        adjacent_to_position = site1_bleaf_group.group_last_node_position,
        group_spread = "horizontal",
        group_node_count = 2,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=10,
        delete_existing_nodes= True,
    )
    site1_wan_group.build()

    site1_bgw_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site1_bgws",
        group_node_names_prefix = "bgw",
        group_mgmt_subnet="192.168.1.0/24",
        group_mgmt_start_ip="192.168.1.112",
        group_mgmt_gw_ip="192.168.1.254",
        adjacent_to_position = site1_spine_group.group_first_node_position,
        group_spread = "vertical",
        group_node_count = 2,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=10,
        delete_existing_nodes= True,
    )
    site1_bgw_group.build()

    site1_tiny_hosts_group = NodeGroup(
        group_node_definition="server",
        group_name= "tiny_linux_hosts",
        group_node_names_prefix = "host",
        group_mgmt_subnet="192.168.1.0/24",
        group_mgmt_start_ip="192.168.1.112",
        group_mgmt_gw_ip="192.168.1.254",
        group_location = CMLPosition(x=0, y=240),
        group_spread = "horizontal",
        group_node_count = 4,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=5,
        delete_existing_nodes= True,
    )
    site1_tiny_hosts_group.build()

    # Connect nodes and form topology:

    # Form a leaf-spine topology
    site1_leaf_spine_topology = Topology(
        node_group1=site1_leaf_group, 
        node_group2=site1_spine_group, 
        topology_type="clos_n_n",
        exclude_interfaces=["mgmt0"],
    )
    site1_leaf_spine_topology.build()

    # Form bleaf-spine topology
    site1_bleaf_spine_topology = Topology(
        node_group1=site1_bleaf_group, 
        node_group2=site1_spine_group, 
        topology_type="clos_n_n",
        exclude_interfaces=["mgmt0"],
    )
    site1_bleaf_spine_topology.build()

    # Form bgw-spine topology
    site1_bgw_spine_topology = Topology(
        node_group1=site1_bgw_group, 
        node_group2=site1_spine_group, 
        topology_type="clos_n_n",
        exclude_interfaces=["mgmt0"],
    )
    site1_bgw_spine_topology.build()

    # Form bleaf-wan topology
    site1_bleaf_wan_topology = Topology(
        node_group1=site1_bleaf_group, 
        node_group2=site1_wan_group, 
        topology_type="square_2_2",
        exclude_interfaces=["mgmt0"],
    )
    site1_bleaf_wan_topology.build()

    # leafs back 2 back connections
    site1_leaf_b2b_topology = Topology(
        node_group1=site1_leaf_group, 
        topology_type="intra2_b2b_n",
        exclude_interfaces=["mgmt0"],
    )
    site1_leaf_b2b_topology.build()

    # Form hosts to leafs toplogy
    site1_leaf_host_topology = Topology(
        node_group1=site1_leaf_group, 
        node_group2=site1_tiny_hosts_group, 
        topology_type="straight_n_n",
        exclude_interfaces=["mgmt0"],
    )
    site1_leaf_host_topology.build()

    


    # SITE 2:
    # Create node groups (and nodes within them)
    site2_leaf_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site2_leafs",
        group_node_names_prefix = "s2leaf",
        group_location = CMLPosition(x=1080, y=120),
        group_spread = "horizontal",
        group_node_count = 4,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=10,
        delete_existing_nodes= True,
    )
    site2_leaf_group.build()

    site2_spine_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site2_spines",
        group_node_names_prefix = "s2spine",
        group_location = CMLPosition(x=1080, y=0),
        group_spread = "horizontal",
        group_node_count = 2,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=20,
        delete_existing_nodes= True,
    )
    site2_spine_group.build()

    site2_bleaf_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site2_borders",
        group_node_names_prefix = "s2bleaf",
        adjacent_to_position = site2_leaf_group.group_last_node_position,
        group_spread = "horizontal",
        group_node_count = 2,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=10,
        delete_existing_nodes= True,
    )
    site2_bleaf_group.build()

    site2_wan_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site2_wan",
        group_node_names_prefix = "s2wan",
        adjacent_to_position = site2_bleaf_group.group_last_node_position,
        group_spread = "horizontal",
        group_node_count = 2,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=10,
        delete_existing_nodes= True,
    )
    site2_wan_group.build()

    site2_bgw_group = NodeGroup(
        group_node_definition = "nxosv9000",
        group_name= "site2_bgws",
        group_node_names_prefix = "s2bgw",
        adjacent_to_position = site2_spine_group.group_first_node_position,
        group_spread = "vertical",
        group_node_count = 2,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=10,
        delete_existing_nodes= True,
    )
    site2_bgw_group.build()

    site2_tiny_hosts_group = NodeGroup(
        group_node_definition="server",
        group_name= "tiny_linux_hosts",
        group_node_names_prefix = "s2host",
        group_location = CMLPosition(x=1080, y=240),
        group_spread = "horizontal",
        group_node_count = 4,
        cml_lab= my_lab1,
        group_intraspace= 80,
        interfaces_per_node=5,
        delete_existing_nodes= True,
    )
    site2_tiny_hosts_group.build()

    # site2 leaf spine
    site2_leaf_spine_topology = Topology(
        node_group1=site2_leaf_group, 
        node_group2=site2_spine_group, 
        topology_type="clos_n_n",
        exclude_interfaces=["mgmt0"],
    )
    site2_leaf_spine_topology.build()

    # Connection between sites
    site1_bgw_msite_topology = Topology(
        node_group1=site12_msite_isn_group, 
        node_group2=site1_bgw_group, 
        topology_type="star_1_n",
        exclude_interfaces=["mgmt0"],
    )
    site1_bgw_msite_topology.build()
    site2_bgw_msite_topology = Topology(
        node_group1=site12_msite_isn_group, 
        node_group2=site2_bgw_group, 
        topology_type="star_1_n",
        exclude_interfaces=["mgmt0"],
    )
    site2_bgw_msite_topology.build()
    
    
    # Form mgmt0 to unmanged switch topology
    # site1 mgmt connections
    site1_mgmt_topology = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=site1_leaf_group, 
        topology_type="star_1_n", # no exclude interfaces are set
    )
    site1_mgmt_topology2 = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=site1_spine_group, 
        topology_type="star_1_n", # no exclude interfaces are set
    )
    site1_mgmt_topology3 = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=site1_bleaf_group, 
        topology_type="star_1_n", # no exclude interfaces are set
    )
    site1_mgmt_topology4 = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=site1_bgw_group, 
        topology_type="star_1_n", # no exclude interfaces are set
    )
    site1_mgmt_topology5 = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=site1_wan_group, 
        topology_type="star_1_n", # no exclude interfaces are set
    )
    
    site1_mgmt_topology.build()
    site1_mgmt_topology2.build()
    site1_mgmt_topology3.build()
    site1_mgmt_topology4.build()
    site1_mgmt_topology5.build()
    # site2 mgmt connections
    site2_mgmt_topology = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=site2_leaf_group, 
        topology_type="star_1_n", # no exclude interfaces are set
    )
    site2_mgmt_topology2 = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=site2_spine_group, 
        topology_type="star_1_n", # no exclude interfaces are set
    )
    site2_mgmt_topology3 = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=site2_bleaf_group, 
        topology_type="star_1_n", # no exclude interfaces are set
    )
    site2_mgmt_topology4 = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=site2_bgw_group, 
        topology_type="star_1_n", # no exclude interfaces are set
    )
    site2_mgmt_topology5 = Topology(
        node_group1=unmanaged_switch_group, 
        node_group2=site2_wan_group, 
        topology_type="star_1_n", # no exclude interfaces are set
    )

    site2_mgmt_topology.build()
    site2_mgmt_topology2.build()
    site2_mgmt_topology3.build()
    site2_mgmt_topology4.build()
    site2_mgmt_topology5.build()



if __name__ == "__main__":
    main()