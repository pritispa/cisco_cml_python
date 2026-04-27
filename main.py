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
REQUIRED_PATH_KEYS = ("conf_files_directory", "jinja_directory")
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

    def _group_width(name):
        info = groups[name]
        nodes_in_row = min(info["node_count"], MAX_NODES_PER_ROW)
        return max(0, nodes_in_row - 1) * info["intraspace"]

    def _group_height(name):
        info = groups[name]
        rows = (info["node_count"] + MAX_NODES_PER_ROW - 1) // MAX_NODES_PER_ROW
        return max(0, rows - 1) * ROW_SPACING

    # Build primary-parent children map (each child under exactly one parent)
    primary_children = {}
    assigned = set()
    for parent, child in above_edges:
        if child not in assigned:
            primary_children.setdefault(parent, []).append(child)
            assigned.add(child)
    for parent in primary_children:
        primary_children[parent].sort(key=lambda c: group_order.index(c))

    # Compute y per layer based on parent chain (not uniform layer height)
    parent_map = {}
    for parent, child in above_edges:
        parent_map.setdefault(child, []).append(parent)

    layer_y = {}
    for layer in sorted_layers:
        if layer == sorted_layers[0]:
            layer_y[layer] = 0
            continue
        max_y = 0
        for name in layer_groups[layer]:
            for p in parent_map.get(name, []):
                p_y = layer_y[layers[p]]
                p_h = _group_height(p)
                max_y = max(max_y, p_y + p_h + LAYER_GAP)
        if max_y == 0:
            prev_layer = sorted_layers[sorted_layers.index(layer) - 1]
            prev_h = max(_group_height(n) for n in layer_groups[prev_layer])
            max_y = layer_y[prev_layer] + prev_h + LAYER_GAP
        layer_y[layer] = max_y

    # Compute subtree widths bottom-up (for horizontal allocation)
    _stw_cache = {}
    def _subtree_width(name):
        if name in _stw_cache:
            return _stw_cache[name]
        own_w = _group_width(name)
        children = primary_children.get(name, [])
        if not children:
            _stw_cache[name] = own_w
            return own_w
        children_w = sum(_subtree_width(c) for c in children) \
                     + max(0, len(children) - 1) * GROUP_GAP
        result = max(own_w, children_w)
        _stw_cache[name] = result
        return result

    # Top-down recursive positioning
    positions = {}
    def _position_subtree(name, alloc_left, alloc_right):
        own_w   = _group_width(name)
        alloc_w = alloc_right - alloc_left
        x = alloc_left + (alloc_w - own_w) // 2
        y = layer_y[layers[name]]
        positions[name] = {"x": x, "y": y, "intraspace": groups[name]["intraspace"]}
        children = primary_children.get(name, [])
        if not children:
            return
        child_stws     = [_subtree_width(c) for c in children]
        total_child_w  = sum(child_stws) + max(0, len(children) - 1) * GROUP_GAP
        child_start    = alloc_left + (alloc_w - total_child_w) // 2
        cx = child_start
        for i, child in enumerate(children):
            _position_subtree(child, cx, cx + child_stws[i])
            cx += child_stws[i] + GROUP_GAP

    # Position data-plane roots and their subtrees
    root_stws     = [_subtree_width(r) for r in roots]
    total_roots_w = sum(root_stws) + max(0, len(roots) - 1) * GROUP_GAP
    cx = 0
    for i, root in enumerate(roots):
        _position_subtree(root, cx, cx + root_stws[i])
        cx += root_stws[i] + GROUP_GAP

    # Position infrastructure nodes centered above the data tree
    canvas_w = max(total_roots_w, 1)
    for name in infra_names:
        own_w = _group_width(name)
        x = (canvas_w - own_w) // 2
        y = layer_y[layers[name]]
        positions[name] = {"x": x, "y": y, "intraspace": groups[name]["intraspace"]}

    # Position any orphan groups not reached by the tree traversal
    for name in group_order:
        if name not in positions:
            positions[name] = {"x": 0, "y": layer_y.get(layers[name], 0),
                               "intraspace": groups[name]["intraspace"]}

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
            group_configuration = ng.get("group_extra_configuration", ""),
            group_location = loc,
            adjacent_to_position = adj_pos,
            group_spread = ng.get("group_spread", None),
            group_intraspace = ng.get("group_intraspace", 80),
            group_mgmt_start_ip = ng.get("group_mgmt_start_ip", ""),
            group_mgmt_subnet = ng.get("group_mgmt_subnet", ""),
            group_mgmt_gw_ip = ng.get("group_mgmt_gw_ip", ""),
            group_image_definition = ng.get("group_image_definition", ""),
            delete_existing_nodes = ng.get("delete_existing_nodes", delete_existing_nodes),
            cml_lab = lab,
        )
        node_groups.append(ng_instance)
        ng_instance.build(existing_nodes_by_label=existing_nodes_by_label)
    return node_groups

def create_topology (topology_list: list, node_groups: list, lab: CMLLab,
                     existing_link_counts: dict = None) -> list:
    topologies = []
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
        topologies.append(tp_instance)
        tp_instance.build()
    return topologies

# ---------------------------------------------------------------------------
# Single lab build
# ---------------------------------------------------------------------------

def build_single_lab(lab_raw: dict, my_cml: CMLRESTClient, flags: dict) -> bool:
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
    
    logger.info(f"Lab '{lab_title}' does not exist or update_existing_lab=false. Creating new lab.")
    lab_created = my_lab.create_lab(lab_title=lab_title, delete_existing_nodes=delete_existing_nodes)
    node_group_defaults = lab_raw.get("node_group_defaults", {})
    node_groups_list_raw = lab_raw.get("node_groups", [])
    topology_list_raw = lab_raw.get("topology", [])

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
    create_topology(
        topology_list=topology_list_raw, node_groups=node_groups, lab=my_lab,
        existing_link_counts=existing_link_counts,
    )
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
    mgmt_module.CONF_FILES_DIRECTORY = paths["conf_files_directory"]
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
                build_single_lab(lab_raw, my_cml, flags)
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