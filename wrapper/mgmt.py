import jinja2
import ipaddress
import yaml
from cml.colors import print_warning, print_error

# This default is overridden at runtime by main.py from config.yml
JINJA_DIRECTORY = "./j2"

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
        print_error(f"The start IP address {start_ip} is not within the subnet {subnet}")
        return None
    next_ip = ip
    while True:
        if next_ip not in network:
            print_error(f"There is no next IP available within the subnet {subnet}")
            return None
        if MgmtIps.check_if_ip_used(str(next_ip), subnet):
            next_ip = next_ip + 1
            continue
        MgmtIps.update_used_ip(str(next_ip), subnet)
        return str(next_ip)

def derive_node_configuration(
        node_definition: str,
        hostname: str,
        group_mgmt_subnet: str = "",
        group_mgmt_start_ip: str = "",
        group_mgmt_gw_ip: str = "",
        group_mgmt_dhcp: bool = False,
        extra_configuration: str = "",
    ) -> tuple:
    """Render j2 template for node_definition, parse YAML result into list of config file dicts.

    Returns a tuple (config_list, mgmt_ip) where config_list is a list of
    {"name": ..., "content": ...} dicts (or None), and mgmt_ip is the
    allocated IP string, "DHCP", or "".
    """
    template_vars = {"hostname": hostname}

    mgmt_ip = ""

    if group_mgmt_dhcp:
        # DHCP mode: ignore static IP/subnet/gw, just flag for templates
        template_vars["dhcp"] = True
        mgmt_ip = "DHCP"
    elif group_mgmt_start_ip and group_mgmt_subnet:
        # Static IP mode
        if not is_valid_ip(group_mgmt_start_ip):
            print_warning(f"group_mgmt_start_ip: {group_mgmt_start_ip} is not a valid ip. Mgmt config will not be generated")
        elif not is_valid_subnet(group_mgmt_subnet):
            print_warning(f"group_mgmt_subnet: {group_mgmt_subnet} is not a valid subnet. Mgmt config will not be generated")
        elif group_mgmt_gw_ip and not is_valid_ip(group_mgmt_gw_ip):
            print_warning(f"group_mgmt_gw_ip: {group_mgmt_gw_ip} is not a valid ip. Mgmt config will not be generated")
        else:
            ip_address = get_next_unused_ip(group_mgmt_start_ip, group_mgmt_subnet)
            if ip_address:
                mgmt_ip = ip_address
                template_vars["ip_address"] = ip_address
                template_vars["mask"] = group_mgmt_subnet.split("/")[1]
                if group_mgmt_gw_ip:
                    template_vars["gw"] = group_mgmt_gw_ip

    if extra_configuration:
        template_vars["extra_configuration"] = extra_configuration

    env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    try:
        config_template = env.get_template(JINJA_DIRECTORY + "/" + node_definition + ".j2")
    except jinja2.exceptions.TemplateNotFound:
        # No j2 template for this node definition
        if extra_configuration:
            return [{"name": "Main", "content": extra_configuration}], mgmt_ip
        return None, mgmt_ip

    rendered = config_template.render(template_vars)
    try:
        config_list = yaml.safe_load(rendered)
    except yaml.YAMLError as e:
        print_error(f"Failed to parse rendered configuration YAML for {node_definition}: {e}")
        return None, mgmt_ip

    if config_list is None:
        return None, mgmt_ip
    if isinstance(config_list, dict):
        config_list = [config_list]
    if not isinstance(config_list, list):
        print_error(f"Configuration template for {node_definition} must render to a YAML list of dicts")
        return None, mgmt_ip

    return config_list, mgmt_ip