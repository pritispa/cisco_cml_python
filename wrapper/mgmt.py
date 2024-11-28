import os
import jinja2
import ipaddress
import glob
from locations import *

class MgmtIps:
    MgmtSubnetsToUsedIps = {}
    @classmethod
    def update_used_ip(cls, used_ip: str, subnet: str):
        if subnet in cls.MgmtSubnetsToUsedIps:
            cls.MgmtSubnetsToUsedIps[subnet].append(used_ip)
        else:
            cls.MgmtSubnetsToUsedIps[subnet] = []
            cls.MgmtSubnetsToUsedIps[subnet].append(used_ip)
    @classmethod
    def check_if_ip_used(cls, candidate_ip: str, subnet: str) -> bool:
        if subnet in cls.MgmtSubnetsToUsedIps:
            if candidate_ip in cls.MgmtSubnetsToUsedIps[subnet]:
                return True
        return False

def is_valid_subnet(subnet_str):
    try:
        ipaddress.ip_network(subnet_str, strict=False)
        return True
    except ValueError:
        return False

def is_valid_ip(ip_str):
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False

def get_next_unused_ip(start_ip: str, subnet: str) -> str:
    network = ipaddress.ip_network(subnet, strict=False)
    ip = ipaddress.ip_address(start_ip)
    if ip not in network:
        print(f"The start IP address {start_ip} is not within the subnet {subnet}")
        return None
    next_ip = ip
    while True:
        if next_ip not in network:
            print(f"There is no next IP available within the subnet {subnet}")
            return None
        if MgmtIps.check_if_ip_used(str(next_ip), subnet):
            next_ip = next_ip + 1
            continue
        MgmtIps.update_used_ip(str(next_ip), subnet)
        return str(next_ip)

def read_conf_files(directory):
    file_contents = {}
    pattern = os.path.join(directory, '*.conf')

    for filepath in glob.glob(pattern):
        filename = os.path.basename(filepath)
        file_key = os.path.splitext(filename)[0]
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
        file_contents[file_key] = content
    return file_contents

def get_node_base_config(node_definition: str) -> str:
    base_configs = read_conf_files(CONF_FILES_DIRECTORY)
    if node_definition not in base_configs:
        print(f"Warning: No base node config found for node definition {node_definition}")
        return ""
    return base_configs[node_definition]

def derive_mgmt_config(
        group_node_definition,
        group_mgmt_subnet,
        group_mgmt_start_ip,
        group_mgmt_gw_ip,
    ):
    config = ""
    if not is_valid_ip (group_mgmt_start_ip) and  group_mgmt_start_ip != "":
        print (f"group_mgmt_start_ip: {group_mgmt_start_ip} is not a valid ip. Mgmt config will not be generated")
        return ""
    if not is_valid_ip (group_mgmt_start_ip) and  group_mgmt_start_ip != "":
        print (f"group_mgmt_gw_ip: {group_mgmt_gw_ip} is not a valid ip. Mgmt config will not be generated")
        return ""
    if not is_valid_subnet (group_mgmt_subnet) and  group_mgmt_subnet != "":
        print (f"group_mgmt_subnet: {group_mgmt_subnet} is not a valid ip subnet. Mgmt config will not be generated")
        return ""
    ip_address = get_next_unused_ip(group_mgmt_start_ip, group_mgmt_subnet)
    gw = group_mgmt_gw_ip
    mask = group_mgmt_subnet.split("/")[1]
    vars = {
        "gw" : gw,
        "ip_address" : ip_address,
        "mask": mask
    }
    env = jinja2.Environment(loader=jinja2.FileSystemLoader((".")))

    try:
        config_template = env.get_template(JINJA_DIRECTORY + "/" + group_node_definition + ".j2")
    except jinja2.exceptions.TemplateNotFound as e:
        print (f"Management config jinja template for node definition {group_node_definition} was not found in {JINJA_DIRECTORY} directory")
        print (f"Management configs will not be generated for nodes of type: {group_node_definition}")
        print (f"TIP: Management config file should be named in the format [group_node_definition].j2 which in this case should be {group_node_definition}.j2")
        return ""
    config = config_template.render(vars)
    return config