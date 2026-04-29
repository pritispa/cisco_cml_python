import csv
import logging
import os
import urllib3
import yaml
import sys
from collections import deque

from cml.client import *
from cml.lab import *
from cml.position import *
from wrapper.nodegroup import *
from wrapper.topology import *

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CONFIG_FILE = os.environ.get("CML_CONFIG_FILE", "./config.yml")

# ---------------------------------------------------------------------------
# Config loading & validation
# ---------------------------------------------------------------------------

REQUIRED_CONFIG_KEYS = ("paths", "flags", "lab_files")
REQUIRED_PATH_KEYS = ("jinja_directory",)
REQUIRED_FLAG_KEYS = ("delete_existing_nodes", "update_existing_lab")

def read_from_yml(file_path: str) -> Any:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            # Load the YAML content
            data = yaml.safe_load(file)
            return data
    except FileNotFoundError:
        logger.error(f"The file '{file_path}' was not found.")
    except PermissionError:
        logger.error(f"Permission denied when trying to read '{file_path}'.")
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML file '{file_path}'. Details: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
    return None

def load_and_validate_config(config_path: str) -> dict:
    config = read_from_yml(config_path)
    if not config:
        logger.error(f"Failed to load configuration from {config_path}. Exiting...")
        sys.exit(1)
    for key in REQUIRED_CONFIG_KEYS:
        if key not in config:
            logger.error(f"Missing required config key: '{key}' in {config_path}. Exiting...")
            sys.exit(1)
    for key in REQUIRED_PATH_KEYS:
        if key not in config["paths"]:
            logger.error(f"Missing required path key: 'paths.{key}' in {config_path}. Exiting...")
            sys.exit(1)
    for key in REQUIRED_FLAG_KEYS:
        if key not in config["flags"]:
            logger.error(f"Missing required flag key: 'flags.{key}' in {config_path}. Exiting...")
            sys.exit(1)
    if not isinstance(config["lab_files"], list) or len(config["lab_files"]) == 0:
        logger.error(f"'lab_files' must be a non-empty list in {config_path}. Exiting...")
        sys.exit(1)
    return config

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_cml_pos(pos: dict) -> CMLPosition :
    if not pos:
        return None
    return CMLPosition(x = pos["x"], y = pos["y"])

def get_node_group_by_name(nglist: list, ng_name: str) -> NodeGroup:
    for ng in nglist:
        if ng.group_name == ng_name:
            return ng
    return None

def validate_topology_ports(node_groups_raw: list, topology_raw: list,
                            node_group_defaults: dict = None) -> bool:
    """Validate that each node group has enough interfaces for all topology connections.

    Prints a colour-coded summary table and returns True when every group has
    sufficient ports, False otherwise.
    """
    BOLD  = "\033[1m"
    _RED   = "\033[91m"
    _GREEN = "\033[92m"
    _RESET = "\033[0m"

    # ---- build effective group properties (merge defaults) ----
    groups = {}
    group_order = []
    for ng_raw in node_groups_raw:
        if node_group_defaults:
            ng = {**node_group_defaults, **{k: v for k, v in ng_raw.items() if v is not None}}
        else:
            ng = dict(ng_raw)
        name = ng.get("group_name")
        groups[name] = {
            "node_count": ng.get("group_node_count", 1),
            "node_definition": ng.get("group_node_definition", ""),
            "image_definition": ng.get("group_image_definition", ""),
            "interfaces_per_node": ng.get("interfaces_per_node", 10),
            "prefix": ng.get("group_node_names_prefix", ""),
            "mgmt_start_ip": ng.get("group_mgmt_start_ip", ""),
            "mgmt_subnet": ng.get("group_mgmt_subnet", ""),
            "mgmt_dhcp": ng.get("group_mgmt_dhcp", False),
        }
        group_order.append(name)

    # ---- per-node connection counts ----
    connections = {name: [0] * groups[name]["node_count"] for name in group_order}

    for topo in (topology_raw or []):
        g1 = topo.get("node_group1")
        g2 = topo.get("node_group2")
        ttype = (topo.get("topology_type") or "").upper()

        if not g1 or g1 not in groups:
            continue
        g1_count = groups[g1]["node_count"]
        g2_count = groups[g2]["node_count"] if g2 and g2 in groups else 0

        if ttype == "CLOS_N_N":
            for i in range(g1_count):
                connections[g1][i] += g2_count
            for j in range(g2_count):
                connections[g2][j] += g1_count

        elif ttype == "VPC_N_N":
            if g1_count >= 2 and g2_count > 0:
                num_pairs = g1_count // 2
                hpp = g2_count // num_pairs
                rem = g2_count % num_pairs
                for p in range(num_pairs):
                    c = hpp + (1 if p < rem else 0)
                    connections[g1][p * 2] += c
                    connections[g1][p * 2 + 1] += c
                for j in range(g2_count):
                    connections[g2][j] += 2

        elif ttype == "SQUARE_2_2":
            for i in range(min(2, g1_count)):
                connections[g1][i] += 2
            if g2 and g2 in groups:
                for j in range(min(2, g2_count)):
                    connections[g2][j] += 2

        elif ttype == "STAR_1_N":
            if g1_count >= 1 and g2_count > 0:
                connections[g1][0] += g2_count
                for j in range(g2_count):
                    connections[g2][j] += 1

        elif ttype == "STRAIGHT_N_N":
            if g2 and g2 in groups:
                for i in range(min(g1_count, g2_count)):
                    connections[g1][i] += 1
                    connections[g2][i] += 1

        elif ttype == "INTRA_GROUP_B2B_N":
            for i in range(0, g1_count - 1, 2):
                connections[g1][i] += 1
                connections[g1][i + 1] += 1

        elif ttype == "INTRA_GROUP_B2B2_N":
            for i in range(0, g1_count - 1, 2):
                connections[g1][i] += 2
                connections[g1][i + 1] += 2

        elif ttype == "FULL_MESH_N_N":
            if g2 and g2 in groups:
                total = g1_count + g2_count
                for i in range(g1_count):
                    connections[g1][i] += total - 1
                for j in range(g2_count):
                    connections[g2][j] += total - 1

    # ---- build table rows ----
    any_failure = False
    rows = []
    for name in group_order:
        info = groups[name]
        count = info["node_count"]
        prefix = info["prefix"]
        specified = info["interfaces_per_node"]

        max_conn = max(connections[name]) if connections[name] else 0
        min_ports = max_conn

        # Device names
        devices = f"{prefix}1" if count == 1 else f"{prefix}1 - {prefix}{count}"

        # Mgmt IPs
        if info["mgmt_dhcp"]:
            mgmt_ips = "DHCP"
        elif info["mgmt_start_ip"]:
            mgmt_ips = info["mgmt_start_ip"] if count == 1 else f"{info['mgmt_start_ip']} (+{count})"
        else:
            mgmt_ips = "-"

        passed = min_ports <= specified
        if not passed:
            any_failure = True

        rows.append({
            "group": name,
            "devices": devices,
            "mgmt_ips": mgmt_ips,
            "image": info["image_definition"] or "-",
            "node_type": info["node_definition"] or "-",
            "specified": str(specified),
            "min_ports": str(min_ports),
            "passed": passed,
        })

    # ---- print table ----
    headers = ["Node Group", "Devices", "Mgmt IPs", "Image", "Node Type",
               "Ports (cfg)", "Min Ports Req"]
    col_keys = ["group", "devices", "mgmt_ips", "image", "node_type",
                "specified", "min_ports"]
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, key in enumerate(col_keys):
            col_widths[i] = max(col_widths[i], len(row[key]))

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    def _fmt_row(vals, color_last=None):
        parts = []
        for i, v in enumerate(vals):
            if i == len(vals) - 1 and color_last:
                parts.append(f"{color_last}{v:<{col_widths[i]}}{_RESET}")
            else:
                parts.append(f"{v:<{col_widths[i]}}")
        return "| " + " | ".join(parts) + " |"

    print(f"\n{BOLD}Port Validation Summary{_RESET}")
    print(sep)
    print(_fmt_row(headers))
    print(sep)
    for row in rows:
        vals = [row[k] for k in col_keys]
        color = _GREEN if row["passed"] else _RED
        print(_fmt_row(vals, color_last=color))
    print(sep)
    print()

    if any_failure:
        print_error("Port validation FAILED. One or more node groups do not have enough interfaces.")
        print_error("Please redesign the topology or increase interfaces_per_node for the affected groups.\n")
    return not any_failure

def _auto_intraspace(node_count: int, node_definition: str) -> int:
    """Compute optimal intra-group spacing (always a multiple of 40, minimum 40)."""
    if node_definition in ("external_connector", "unmanaged_switch"):
        return 80
    if node_definition == "server":
        return 40
    if node_count <= 4:
        return 200
    if node_count <= 8:
        return 120
    if node_count <= 20:
        return 80
    return 40

def compute_auto_layout(node_groups_raw: list, topology_raw: list, node_group_defaults: dict = None) -> dict:
    """
    Compute automatic (x, y) positions and intra-group spacing for node groups
    based on topology connections.  Uses a hierarchical layout algorithm:
      1. Infer directed parent/child hierarchy from topology types
      2. BFS layer assignment from root nodes
      3. Same-level merging for peer connections (STRAIGHT between non-hosts)
      4. Re-propagate to fix any ordering violations
      5. Center each layer horizontally, with variable vertical spacing
         that accounts for multi-row groups (>20 nodes wrap into rows)
    Returns dict mapping group_name -> {"x": int, "y": int, "intraspace": int}
    """
    # ---- build effective group properties (merge defaults) ----
    groups = {}
    group_order = []
    for ng_raw in node_groups_raw:
        if node_group_defaults:
            ng = {**node_group_defaults, **{k: v for k, v in ng_raw.items() if v is not None}}
        else:
            ng = dict(ng_raw)
        name = ng.get("group_name")
        node_count = ng.get("group_node_count", 1)
        node_def   = ng.get("group_node_definition", "")
        auto_space = _auto_intraspace(node_count, node_def)
        groups[name] = {
            "node_count": node_count,
            "node_definition": node_def,
            "intraspace": auto_space,
        }
        group_order.append(name)

    # ---- infer hierarchy edges from topology definitions ----
    above_edges     = []    # (parent, child) — parent is visually above
    same_level      = []    # (a, b) — peers on the same layer
    straight_defer  = []    # STRAIGHT between non-server groups, resolved in 2nd pass
    INFRA_DEFS      = ("external_connector", "unmanaged_switch")

    for topo in (topology_raw or []):
        g1    = topo.get("node_group1")
        g2    = topo.get("node_group2")
        ttype = (topo.get("topology_type") or "").upper()

        if not g1 or g1 not in groups:
            continue
        if ttype in ("INTRA_GROUP_B2B_N", "INTRA_GROUP_B2B2_N"):
            continue                                    # same group, no hierarchy
        if not g2 or g2 not in groups:
            continue

        g1_def = groups[g1]["node_definition"]
        g2_def = groups[g2]["node_definition"]

        # Management links to infrastructure don't define data-plane hierarchy
        if g1_def in INFRA_DEFS or g2_def in INFRA_DEFS:
            continue

        if ttype == "CLOS_N_N":
            above_edges.append((g2, g1))            # group2 (spines) above group1 (leafs)
        elif ttype == "VPC_N_N":
            above_edges.append((g1, g2))            # group1 (leafs) above group2 (hosts)
        elif ttype == "STAR_1_N":
            above_edges.append((g1, g2))            # hub above satellites
        elif ttype == "STRAIGHT_N_N":
            if g2_def == "server":
                above_edges.append((g1, g2))
            elif g1_def == "server":
                above_edges.append((g2, g1))
            else:
                straight_defer.append((g1, g2))     # resolved after definitive edges
        elif ttype in ("SQUARE_2_2", "FULL_MESH_N_N"):
            same_level.append((g1, g2))

    # ---- resolve deferred STRAIGHT pairs using existing hierarchy ----
    # A group that already has a parent (is embedded in the hierarchy) acts as
    # the anchor; the other group is placed below it.
    definitive_child_set = {child for _, child in above_edges}
    for g1, g2 in straight_defer:
        g1_has_parent = g1 in definitive_child_set
        g2_has_parent = g2 in definitive_child_set
        if g2_has_parent and not g1_has_parent:
            above_edges.append((g2, g1))            # g2 is anchored above, g1 hangs below
        elif g1_has_parent and not g2_has_parent:
            above_edges.append((g1, g2))            # g1 is anchored above, g2 hangs below
        else:
            same_level.append((g1, g2))             # both or neither anchored — peers

    # ---- separate infrastructure / data nodes ----
    infra_names = [n for n in group_order if groups[n]["node_definition"] in INFRA_DEFS]
    data_names  = [n for n in group_order if n not in infra_names]

    children_map = {}
    child_set    = set()
    for parent, child in above_edges:
        children_map.setdefault(parent, []).append(child)
        child_set.add(child)

    roots = [n for n in data_names if n not in child_set]

    # ---- BFS layer assignment ----
    layers = {}
    for i, name in enumerate(infra_names):
        layers[name] = -(len(infra_names) - i)         # infrastructure at negative layers

    queue = deque()
    for r in roots:
        layers[r] = 0
        queue.append(r)
    while queue:
        node = queue.popleft()
        for child in children_map.get(node, []):
            new_layer = layers[node] + 1
            if child not in layers or layers[child] < new_layer:
                layers[child] = new_layer
                queue.append(child)

    # ---- same-level merging (push both to the deeper layer) ----
    for a, b in same_level:
        if a in layers and b in layers:
            target = max(layers[a], layers[b])
            layers[a] = target
            layers[b] = target
        elif a in layers:
            layers[b] = layers[a]
        elif b in layers:
            layers[a] = layers[b]

    # ---- re-propagate hierarchy after merging ----
    changed = True
    while changed:
        changed = False
        for parent, child in above_edges:
            if parent in layers and child in layers and layers[child] <= layers[parent]:
                layers[child] = layers[parent] + 1
                changed = True

    # ---- handle any remaining unplaced nodes ----
    max_layer_val = max(layers.values()) if layers else 0
    for name in group_order:
        if name not in layers:
            max_layer_val += 1
            layers[name] = max_layer_val

    # ---- group nodes by layer (preserve YAML order within each layer) ----
    layer_groups  = {}
    for name in group_order:
        layer_groups.setdefault(layers[name], []).append(name)
    sorted_layers = sorted(layer_groups.keys())

    # ---- compute (x, y) positions via subtree-based layout ----
    LAYER_GAP = 120     # vertical gap between a parent's bottom and its children
    GROUP_GAP = 120     # horizontal gap between sibling subtrees
    MAX_ROW_NODES = 30  # max first-row nodes across sibling groups in one visual row

    def _group_width(name):
        info = groups[name]
        nodes_in_row = min(info["node_count"], MAX_NODES_PER_ROW)
        return max(0, nodes_in_row - 1) * info["intraspace"]

    def _group_height(name):
        info = groups[name]
        rows = (info["node_count"] + MAX_NODES_PER_ROW - 1) // MAX_NODES_PER_ROW
        return max(0, rows - 1) * ROW_SPACING

    def _first_row_nodes(name):
        """Number of nodes in the first visual row of a group."""
        return min(groups[name]["node_count"], MAX_NODES_PER_ROW)

    # Build primary-parent children map (each child under exactly one parent)
    primary_children = {}
    assigned = set()
    for parent, child in above_edges:
        if child not in assigned:
            primary_children.setdefault(parent, []).append(child)
            assigned.add(child)
    for parent in primary_children:
        primary_children[parent].sort(key=lambda c: group_order.index(c))

    def _pack_children_into_subrows(children):
        """Pack children into sub-rows so each has <= MAX_ROW_NODES first-row nodes."""
        subrows = []
        current_row = []
        current_count = 0
        for child in children:
            child_nodes = _first_row_nodes(child)
            if current_count + child_nodes > MAX_ROW_NODES and current_row:
                subrows.append(current_row)
                current_row = [child]
                current_count = child_nodes
            else:
                current_row.append(child)
                current_count += child_nodes
        if current_row:
            subrows.append(current_row)
        return subrows

    # Compute subtree widths bottom-up (accounts for sub-row wrapping)
    _stw_cache = {}
    def _subtree_width(name):
        if name in _stw_cache:
            return _stw_cache[name]
        own_w = _group_width(name)
        children = primary_children.get(name, [])
        if not children:
            _stw_cache[name] = own_w
            return own_w
        subrows = _pack_children_into_subrows(children)
        max_subrow_w = max(
            sum(_subtree_width(c) for c in sr) + max(0, len(sr) - 1) * GROUP_GAP
            for sr in subrows
        )
        result = max(own_w, max_subrow_w)
        _stw_cache[name] = result
        return result

    # Compute subtree total heights (for vertical sub-row stacking)
    _sth_cache = {}
    def _subtree_total_height(name):
        if name in _sth_cache:
            return _sth_cache[name]
        own_h = _group_height(name)
        children = primary_children.get(name, [])
        if not children:
            _sth_cache[name] = own_h
            return own_h
        subrows = _pack_children_into_subrows(children)
        children_h = 0
        for sr in subrows:
            children_h += LAYER_GAP + max(_subtree_total_height(c) for c in sr)
        result = own_h + children_h
        _sth_cache[name] = result
        return result

    # Top-down recursive positioning (Y computed from parent, sub-rows stacked vertically)
    positions = {}
    def _position_subtree(name, alloc_left, alloc_right, y):
        own_w   = _group_width(name)
        alloc_w = alloc_right - alloc_left
        x = alloc_left + (alloc_w - own_w) // 2
        positions[name] = {"x": x, "y": y, "intraspace": groups[name]["intraspace"]}
        children = primary_children.get(name, [])
        if not children:
            return
        subrows = _pack_children_into_subrows(children)
        child_y = y + _group_height(name) + LAYER_GAP
        for sr in subrows:
            sr_stws = [_subtree_width(c) for c in sr]
            total_sr_w = sum(sr_stws) + max(0, len(sr) - 1) * GROUP_GAP
            child_start = alloc_left + (alloc_w - total_sr_w) // 2
            cx = child_start
            for i, child in enumerate(sr):
                _position_subtree(child, cx, cx + sr_stws[i], child_y)
                cx += sr_stws[i] + GROUP_GAP
            sr_max_h = max(_subtree_total_height(c) for c in sr)
            child_y += sr_max_h + LAYER_GAP

    # Position data-plane roots and their subtrees
    root_stws     = [_subtree_width(r) for r in roots]
    total_roots_w = sum(root_stws) + max(0, len(roots) - 1) * GROUP_GAP
    cx = 0
    for i, root in enumerate(roots):
        _position_subtree(root, cx, cx + root_stws[i], 0)
        cx += root_stws[i] + GROUP_GAP

    # Position infrastructure nodes centered above the data tree
    canvas_w = max(total_roots_w, 1)
    infra_y_cursor = 0
    for name in reversed(infra_names):
        infra_y_cursor -= (_group_height(name) + LAYER_GAP)
        own_w = _group_width(name)
        x = (canvas_w - own_w) // 2
        positions[name] = {"x": x, "y": infra_y_cursor, "intraspace": groups[name]["intraspace"]}

    # Position any orphan groups not reached by the tree traversal
    for name in group_order:
        if name not in positions:
            positions[name] = {"x": 0, "y": 0, "intraspace": groups[name]["intraspace"]}

    logger.debug("Auto-layout layers: %s",
                 {layer: layer_groups[layer] for layer in sorted_layers})
    return positions

def create_node_groups(ngroups: list, lab: CMLLab, delete_existing_nodes: bool,
                       node_group_defaults: dict = None,
                       existing_nodes_by_label: dict = None) -> list:
    node_groups = []
    for ng_raw in ngroups:
        # Merge defaults with per-group values; per-group values take precedence
        if node_group_defaults:
            ng = {**node_group_defaults, **{k: v for k, v in ng_raw.items() if v is not None}}
        else:
            ng = ng_raw
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
            group_extra_configuration = ng.get("group_extra_configuration", ""),
            group_location = loc,
            adjacent_to_position = adj_pos,
            group_spread = ng.get("group_spread", None),
            group_intraspace = ng.get("group_intraspace", 80),
            group_mgmt_start_ip = ng.get("group_mgmt_start_ip", ""),
            group_mgmt_subnet = ng.get("group_mgmt_subnet", ""),
            group_mgmt_gw_ip = ng.get("group_mgmt_gw_ip", ""),
            group_mgmt_dhcp = ng.get("group_mgmt_dhcp", False),
            group_image_definition = ng.get("group_image_definition", ""),
            delete_existing_nodes = ng.get("delete_existing_nodes", delete_existing_nodes),
            group_delete_existing = ng.get("group_delete_existing", False),
            cml_lab = lab,
        )
        node_groups.append(ng_instance)
        ng_instance.build(existing_nodes_by_label=existing_nodes_by_label)
    return node_groups

def create_topology (topology_list: list, node_groups: list, lab: CMLLab,
                     existing_link_counts: dict = None) -> list:
    all_records = []
    for tp in topology_list:
        ng_name1 = tp.get("node_group1","")
        ng_name2 = tp.get("node_group2","")
        if ng_name1 == "":
            logger.error("node_group1 parameter in topology items is mandatory. Skipping entry...")
            continue
        ng_obj1 = get_node_group_by_name(nglist = node_groups, ng_name = ng_name1)
        ng_obj2 = get_node_group_by_name(nglist = node_groups, ng_name = ng_name2)
        tp_instance = Topology(
            node_group1= ng_obj1,
            node_group2= ng_obj2,
            exclude_interfaces= tp.get("exclude_interfaces",[]),
            topology_type= tp.get("topology_type","CLOS_N_N"),
            existing_link_counts= existing_link_counts,
        )
        records = tp_instance.build()
        if records:
            all_records.extend(records)
    return all_records

def print_connectivity_table(records: list):
    """Print a formatted connectivity matrix table to the terminal."""
    if not records:
        print("\nNo new links were created.\n")
        return

    BOLD  = "\033[1m"
    _RESET = "\033[0m"

    headers = ["Device A", "Mgmt IP A", "Port A", "Device B", "Mgmt IP B", "Port B"]
    keys    = ["node_a",  "node_a_mgmt_ip", "port_a", "node_b",  "node_b_mgmt_ip", "port_b"]

    col_widths = [len(h) for h in headers]
    for rec in records:
        for i, key in enumerate(keys):
            col_widths[i] = max(col_widths[i], len(str(rec.get(key, ""))))

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    def _fmt(vals):
        return "| " + " | ".join(f"{v:<{col_widths[i]}}" for i, v in enumerate(vals)) + " |"

    print(f"\n{BOLD}Connectivity Matrix ({len(records)} links){_RESET}")
    print(sep)
    print(_fmt(headers))
    print(sep)
    for rec in records:
        print(_fmt([str(rec.get(k, "")) for k in keys]))
    print(sep)
    print()

def save_connectivity_csv(records: list, lab_yaml_file: str):
    """Save the connectivity matrix to a CSV file derived from the lab YAML filename."""
    if not records:
        return
    base = os.path.splitext(lab_yaml_file)[0]
    csv_path = f"{base}_gen_matrix.csv"

    headers = ["Device A", "Mgmt IP A", "Port A", "Device B", "Mgmt IP B", "Port B"]
    keys    = ["node_a",  "node_a_mgmt_ip", "port_a", "node_b",  "node_b_mgmt_ip", "port_b"]

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for rec in records:
            writer.writerow([str(rec.get(k, "")) for k in keys])
    logger.info(f"Connectivity matrix saved to {csv_path}")

# ---------------------------------------------------------------------------
# Single lab build
# ---------------------------------------------------------------------------

def build_single_lab(lab_raw: dict, my_cml: CMLRESTClient, flags: dict,
                     lab_yaml_file: str = "") -> bool:
    lab_title = lab_raw.get("title", "Untitled Lab")
    update_existing_lab = lab_raw.get("update_existing_lab", flags["update_existing_lab"])
    delete_existing_nodes = flags["delete_existing_nodes"]

    my_lab = CMLLab(my_cml)

    # Check if this lab already exists on CML
    existing_lab = CMLLab.check_lab_exists(lab_title, my_cml)

    # Determine operating mode
    update_mode = False
    if existing_lab and update_existing_lab:
        update_mode = True
        logger.info(f"Lab '{lab_title}' exists, update_existing_lab=true. Entering update mode.")

    if not update_mode and existing_lab:
        logger.info(f"Lab '{lab_title}' already exists and update_existing_lab=false. Skipping this lab build.")
        return True
    
    node_group_defaults = lab_raw.get("node_group_defaults", {})
    node_groups_list_raw = lab_raw.get("node_groups", [])
    topology_list_raw = lab_raw.get("topology", [])

    # Validate topology port requirements before creating anything on CML
    if not validate_topology_ports(node_groups_list_raw, topology_list_raw, node_group_defaults):
        return False

    lab_created = my_lab.create_lab(lab_title=lab_title, delete_existing_nodes=delete_existing_nodes)

    # ---- Update mode: fetch existing nodes & links ----
    existing_nodes_by_label = None
    existing_link_counts = None
    if update_mode:
        # Ignore delete_existing_nodes in update mode
        delete_existing_nodes = False
        # Fetch all existing nodes with full data
        existing_nodes_list = CMLLab.list_lab_nodes_data(
            lab_id=my_lab.id, cml_rest_client=my_cml)
        existing_nodes_by_label = {n["label"]: n for n in existing_nodes_list}
        logger.info(f"Update mode: found {len(existing_nodes_by_label)} existing nodes.")
        # Fetch all existing links with full data and build pair counts
        existing_links_list = CMLLab.list_lab_links_data(
            lab_id=my_lab.id, cml_rest_client=my_cml)
        existing_link_counts = {}
        for lnk in existing_links_list:
            pair_key = frozenset([lnk["node_a"], lnk["node_b"]])
            existing_link_counts[pair_key] = existing_link_counts.get(pair_key, 0) + 1
        logger.info(f"Update mode: found {len(existing_links_list)} existing links.")

    # Auto-layout: compute positions and spacing for groups that lack explicit values
    auto_location = lab_raw.get("auto_location", False)
    if auto_location:
        auto_positions = compute_auto_layout(node_groups_list_raw, topology_list_raw, node_group_defaults)
        for ng_raw in node_groups_list_raw:
            name = ng_raw.get("group_name")
            if name not in auto_positions:
                continue
            pos = auto_positions[name]
            has_explicit_loc = ng_raw.get("group_location") is not None
            has_adjacent     = ng_raw.get("adjacent_to_group") is not None
            if not has_explicit_loc and not has_adjacent:
                ng_raw["group_location"] = {"x": pos["x"], "y": pos["y"]}
            if ng_raw.get("group_intraspace") is None:
                ng_raw["group_intraspace"] = pos["intraspace"]
            logger.info(f"Auto-layout '{name}': pos=({pos['x']}, {pos['y']}), intraspace={pos['intraspace']}")

    node_groups = create_node_groups(
        ngroups=node_groups_list_raw, lab=my_lab,
        delete_existing_nodes=delete_existing_nodes,
        node_group_defaults=node_group_defaults,
        existing_nodes_by_label=existing_nodes_by_label,
    )
    connectivity_records = create_topology(
        topology_list=topology_list_raw, node_groups=node_groups, lab=my_lab,
        existing_link_counts=existing_link_counts,
    )
    print_connectivity_table(connectivity_records)
    if lab_yaml_file:
        save_connectivity_csv(connectivity_records, lab_yaml_file)
    logger.info(f"Lab '{lab_title}' built successfully.")
    return True

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    config = load_and_validate_config(CONFIG_FILE)

    paths = config["paths"]
    flags = config["flags"]
    lab_files = config["lab_files"]

    # Expose paths for mgmt.py via module-level globals (replaces locations.py)
    import wrapper.mgmt as mgmt_module
    mgmt_module.JINJA_DIRECTORY = paths["jinja_directory"]

    succeeded = []
    failed = []

    for lab_file in lab_files:
        logger.info(f"--- Processing lab file: {lab_file} ---")
        data_from_yaml = read_from_yml(lab_file)
        if not data_from_yaml:
            logger.error(f"No data parsed from '{lab_file}'. Skipping...")
            failed.append(lab_file)
            continue

        if "CML" not in data_from_yaml:
            logger.error(f"Missing 'CML' section in '{lab_file}'. Skipping...")
            failed.append(lab_file)
            continue

        base_uri = f'https://{data_from_yaml["CML"]["hostname"]}/api/v0'
        my_cml = CMLRESTClient(
            base_uri = base_uri,
            username = data_from_yaml["CML"]["username"],
            password = data_from_yaml["CML"]["password"],
        )

        labs_raw = data_from_yaml.get("labs", [])
        if not labs_raw:
            logger.error(f"No 'labs' entries found in '{lab_file}'. Skipping...")
            failed.append(lab_file)
            continue

        file_failed = False
        for lab_raw in labs_raw:
            lab_title = lab_raw.get("title", "Untitled Lab")
            try:
                build_single_lab(lab_raw, my_cml, flags, lab_yaml_file=lab_file)
            except Exception as e:
                logger.error(f"Failed to build lab '{lab_title}' from '{lab_file}': {e}")
                file_failed = True

        if file_failed:
            failed.append(lab_file)
        else:
            succeeded.append(lab_file)

    # Summary
    logger.info("=" * 50)
    logger.info("Build Summary")
    logger.info(f"  Succeeded: {len(succeeded)}/{len(lab_files)} lab files")
    for f in succeeded:
        logger.info(f"    - {f}")
    if failed:
        logger.warning(f"  Failed: {len(failed)}/{len(lab_files)} lab files")
        for f in failed:
            logger.warning(f"    - {f}")

if __name__ == "__main__":
    main()