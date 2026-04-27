# CML Lab Builder

A Python automation tool for building and managing Cisco Modeling Labs (CML) topologies from declarative YAML definitions. Define your lab's node groups, connections, and management configuration in YAML and let the tool handle node creation, interface wiring, and intelligent updates.

## Features

- **Declarative YAML** — Define entire lab topologies (nodes, links, management IPs) in simple YAML files.
- **Topology Types** — CLOS, Star, Straight, Full Mesh, Square, vPC dual-homing, and intra-group back-to-back.
- **Auto Layout** — Automatic hierarchical positioning of node groups on the CML canvas.
- **Update Mode** — When `update_existing_lab` is `true`, existing labs are intelligently updated: only changed nodes are modified, only missing links are created.
- **Management IP Generation** — Automatic per-node management IP assignment via Jinja2 templates.
- **Node Group Defaults** — Reduce repetition by defining shared parameters once.
- **Colorized Output** — Terminal output is color-coded: green (create), orange (update), red (error/delete), blue (warning).

## Requirements

- Python 3.10+ (uses `match`/`case` syntax)
- A running Cisco CML controller accessible via HTTPS
- Python packages: `requests`, `pyyaml`, `jinja2`, `urllib3`

Install dependencies:
```bash
pip install requests pyyaml jinja2 urllib3
```

## Quick Start

```bash
# 1. Edit config.yml with your settings
# 2. Create a lab YAML file (see examples below)
# 3. Run
python3 main.py

# Override config path via environment variable
CML_CONFIG_FILE=./my_config.yml python3 main.py
```

---

## Configuration Reference

### `config.yml`

The main configuration file controls global paths, flags, and which lab files to process.

```yaml
paths:
  conf_files_directory: "./default_configs"   # Directory containing base node configs (.conf)
  jinja_directory: "./j2"                     # Directory containing Jinja2 mgmt templates (.j2)

flags:
  # If true, existing labs are updated to match the YAML (nodes and links are added/modified).
  # If false, existing labs are skipped entirely.
  update_existing_lab: true

  # Only relevant when update_existing_lab is true.
  # If true, all existing nodes and links are deleted first, then rebuilt fresh from YAML.
  # If false, incremental update mode is used (existing cabling is kept, missing links added).
  # Ignored when update_existing_lab is false.
  delete_existing_nodes: false

lab_files:
  - "./examples/VXLAN_EVPN_LARGE.yml"
  - "./examples/VXLAN_EVPN_TINY_MULTISITE.yml"
  - "./examples/BGP_ROUTED_5STAGE.yml"
  - "./examples/CLASSIC_3TIER.yml"
```

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `paths.conf_files_directory` | string | Yes | Path to directory containing `<node_definition>.conf` base config files. |
| `paths.jinja_directory` | string | Yes | Path to directory containing `<node_definition>.j2` Jinja2 management config templates. |
| `flags.update_existing_lab` | bool | Yes | When `true`, existing labs enter update mode. When `false`, existing labs are **skipped**. |
| `flags.delete_existing_nodes` | bool | Yes | When `true` (and `update_existing_lab` is also `true`), all existing nodes/links are wiped and rebuilt fresh. Ignored when `update_existing_lab` is `false`. |
| `lab_files` | list | Yes | Ordered list of lab YAML file paths to process. |

### Flag Behavior Matrix

| `update_existing_lab` | `delete_existing_nodes` | Lab Exists? | Result |
|:---------------------:|:-----------------------:|:-----------:|--------|
| `true` | `false` | Yes | **Incremental update** — existing nodes are compared and patched, missing links are created, existing cabling is preserved. |
| `true` | `true` | Yes | **Full rebuild** — all existing nodes and links are deleted first, then everything is created fresh from the YAML. Use this when you want the lab to match the YAML exactly with no leftover nodes or cabling. |
| `false` | *(ignored)* | Yes | **Skip** — lab is left untouched. |
| *(any)* | *(any)* | No | **Create** — new lab is created from scratch. |

### Incremental Update Mode (`update_existing_lab: true`, `delete_existing_nodes: false`)

When the lab already exists on CML:

1. Existing nodes are fetched and compared parameter-by-parameter against the YAML.
2. **No changes needed** — node is skipped entirely.
3. **`node_definition` changed** — node is stopped, wiped, deleted, and recreated (cannot be patched via API).
4. **`image_definition` or interface count changed** — node is stopped and wiped, then patched.
5. **Only `configuration` or position changed** — node is patched in-place without stop/wipe.
6. Existing links are counted by node pair; only **missing links are created**, existing ones are preserved.
7. Existing cabling that is not in the YAML is **not deleted** — it is left as-is.

---

## Lab YAML Reference

Each lab YAML file has two top-level sections: `CML` (connection details) and `labs` (list of labs to build).

### `CML` Section

```yaml
CML:
  hostname: 10.10.10.10       # CML controller IP or hostname
  username: admin              # CML username
  password: "my_password"      # CML password
```

### `labs` Section

Each entry in the `labs` list defines a complete lab topology.

```yaml
labs:
  - title: My Lab                    # Lab title (used to identify existing labs)
    auto_location: true              # Enable automatic hierarchical layout
    update_existing_lab: true        # Per-lab override (optional, falls back to config.yml)
    node_group_defaults: { ... }     # Shared defaults for all node groups
    node_groups: [ ... ]             # List of node group definitions
    topology: [ ... ]                # List of link/topology definitions
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `title` | string | `"Untitled Lab"` | Lab name on CML. Used for existence checks. |
| `auto_location` | bool | `false` | Automatically compute x/y positions and intraspace for groups. |
| `update_existing_lab` | bool | *(from config.yml)* | Per-lab override for the global `update_existing_lab` flag. |
| `node_group_defaults` | dict | `{}` | Default values inherited by all node groups. Per-group values take precedence. |
| `node_groups` | list | `[]` | Ordered list of node group definitions. |
| `topology` | list | `[]` | List of topology/link definitions connecting node groups. |

### Node Group Parameters

Each node group defines a set of identical nodes.

```yaml
node_groups:
  - group_name: spines
    group_node_definition: nxosv9000
    group_image_definition: nxosv9300-10-6-2-f
    group_node_names_prefix: spine
    group_node_count: 4
    interfaces_per_node: 20
    group_spread: horizontal
    group_intraspace: 120
    group_extra_configuration: ""
    group_location:
      x: 100
      y: 0
    adjacent_to_group: null
    group_mgmt_start_ip: 198.18.1.21
    group_mgmt_subnet: 198.18.0.0/16
    group_mgmt_gw_ip: 198.18.1.1
    delete_existing_nodes: false
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `group_name` | string | **required** | Unique name used to reference this group in topology definitions. |
| `group_node_definition` | string | **required** | CML node definition (e.g. `nxosv9000`, `server`, `external_connector`, `unmanaged_switch`). |
| `group_node_names_prefix` | string | **required** | Prefix for auto-generated node labels. Nodes are named `<prefix>1`, `<prefix>2`, etc. |
| `group_node_count` | int | **required** | Number of nodes to create in this group. |
| `group_image_definition` | string | `""` | CML image definition. Use `""` for nodes that don't require images (e.g. `server`, `external_connector`). |
| `interfaces_per_node` | int | `10` | Number of physical interfaces per node. Slot 0 through slot N-1. |
| `group_spread` | string | `"horizontal"` | Layout direction: `"horizontal"` or `"vertical"`. |
| `group_intraspace` | int | `80` | Pixel spacing between nodes. Must be >= 40 and a multiple of 40. |
| `group_extra_configuration` | string | `""` | Additional configuration appended after the base config. For `external_connector`, set to bridge name (e.g. `bridge1`). |
| `group_location` | dict | `{x: 0, y: 0}` | Starting position `{x, y}` for the group. Overridden by `auto_location`. |
| `adjacent_to_group` | string | `null` | Name of another group. This group's position is computed relative to that group's last node. |
| `group_mgmt_start_ip` | string | `""` | First management IP. Subsequent nodes increment from this. Set to `""` to skip mgmt config. |
| `group_mgmt_subnet` | string | `""` | Management subnet in CIDR notation (e.g. `198.18.0.0/16`). |
| `group_mgmt_gw_ip` | string | `""` | Management default gateway IP. |
| `delete_existing_nodes` | bool | *(from flags)* | Per-group override for the global `delete_existing_nodes` flag. |

> **Node naming**: Nodes are labeled `<prefix><N>` where N starts at 1. For example, `group_node_names_prefix: spine` with `group_node_count: 4` produces: `spine1`, `spine2`, `spine3`, `spine4`.

> **Groups with > 20 nodes**: Nodes automatically wrap into rows of 20, spaced vertically by 80px.

### Topology Parameters

Each topology entry defines how two node groups (or one group internally) are connected.

```yaml
topology:
  - node_group1: leafs
    node_group2: spines
    topology_type: CLOS_N_N
    exclude_interfaces: ["mgmt0"]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_group1` | string | **required** | Name of the first node group. |
| `node_group2` | string | `""` | Name of the second node group. Required for most topology types. Not used for `INTRA_GROUP_*`. |
| `topology_type` | string | `"CLOS_N_N"` | Wiring pattern. Must be one of the valid types listed below. |
| `exclude_interfaces` | list | `[]` | Interface labels to skip when allocating links (e.g. `["mgmt0"]`). |

---

## Supported Topology Types

There are **8** valid topology types. Using any other value will cause the tool to exit with an error.

### `CLOS_N_N` — Full Mesh Between Two Groups

**Requires**: `node_group1` + `node_group2`

Every node in group1 connects to **every** node in group2. This is the standard leaf-spine or spine-superspine wiring.

```
Group1 (leafs):    leaf1    leaf2    leaf3
                    / \      / \      / \
                   /   \    /   \    /   \
Group2 (spines): spine1  spine2  spine1  spine2 ...
                 (each leaf connects to EVERY spine)
```

**Example** — 4 leafs to 2 spines (produces 8 links):
```yaml
topology:
  - node_group1: leafs        # 4 nodes
    node_group2: spines        # 2 nodes
    topology_type: CLOS_N_N
    exclude_interfaces: ["mgmt0"]
```
Result: `leaf1↔spine1`, `leaf1↔spine2`, `leaf2↔spine1`, `leaf2↔spine2`, `leaf3↔spine1`, `leaf3↔spine2`, `leaf4↔spine1`, `leaf4↔spine2`.

---

### `STRAIGHT_N_N` — One-to-One Index-Matched

**Requires**: `node_group1` + `node_group2`

Connects nodes by index: node1↔node1, node2↔node2, etc. If groups have different sizes, extra nodes in the larger group are left unconnected.

```
Group1: A1 ── B1  :Group2
        A2 ── B2
        A3 ── B3
        A4   (unconnected, group2 only has 3)
```

**Example** — 2 pod spines to 2 super spines (1:1 uplink):
```yaml
topology:
  - node_group1: pod1_spines   # 2 nodes
    node_group2: super_spines   # 2 nodes
    topology_type: STRAIGHT_N_N
    exclude_interfaces: ["mgmt0"]
```
Result: `p1spine1↔sspine1`, `p1spine2↔sspine2`.

**Example** — Each access switch to its own host:
```yaml
topology:
  - node_group1: access_switches  # 4 nodes
    node_group2: hosts             # 4 nodes
    topology_type: STRAIGHT_N_N
    exclude_interfaces: ["mgmt0"]
```

---

### `STAR_1_N` — Hub-and-Spoke

**Requires**: `node_group1` (exactly 1 node) + `node_group2`

The single node in group1 (hub) connects to every node in group2 (spokes). Commonly used for OOB management switches or hub routers.

```
             hub1 (group1)
           / | | | \
          /  | | |  \
        s1  s2 s3 s4 s5  (group2)
```

**Example** — OOB management switch to all leafs:
```yaml
topology:
  - node_group1: unmanaged switch  # 1 node
    node_group2: leafs              # N nodes
    topology_type: STAR_1_N
```

**Example** — ISN router connecting to border gateways in both sites:
```yaml
topology:
  - node_group1: msite_isn    # 1 node
    node_group2: s1bgw         # 1 node
    topology_type: STAR_1_N
    exclude_interfaces: ["mgmt0"]
  - node_group1: msite_isn
    node_group2: s2bgw
    topology_type: STAR_1_N
    exclude_interfaces: ["mgmt0"]
```

---

### `SQUARE_2_2` — Four-Node Ring

**Requires**: `node_group1` (exactly 2 nodes) + `node_group2` (exactly 2 nodes)

Creates a ring of 4 links: A1↔B1, A1↔A2, B2↔A2, B2↔B1.

```
  A1 ────── B1
  |          |
  A2 ────── B2
```

**Example**:
```yaml
topology:
  - node_group1: pair_a   # 2 nodes
    node_group2: pair_b    # 2 nodes
    topology_type: SQUARE_2_2
    exclude_interfaces: ["mgmt0"]
```

---

### `FULL_MESH_N_N` — Full Mesh Across Both Groups Combined

**Requires**: `node_group1` + `node_group2`

Merges all nodes from both groups into one super-group and creates a link between **every** pair. With N total nodes, this produces N*(N-1)/2 links.

```
  A1 ─── A2
  |\ \  /| 
  | \ \/  |
  | / /\  |
  |/ /  \ |
  B1 ─── B2
  (every node connects to every other node)
```

**Example** — 3 WAN core + 3 branch routers fully meshed (15 links):
```yaml
topology:
  - node_group1: wan_core    # 3 nodes
    node_group2: branches     # 3 nodes
    topology_type: FULL_MESH_N_N
    exclude_interfaces: ["mgmt0"]
```

---

### `VPC_N_N` — vPC Dual-Homing

**Requires**: `node_group1` (even count >= 2) + `node_group2`

Group1 nodes form vPC pairs by index: (node1, node2), (node3, node4), etc. Group2 nodes (hosts) are **evenly distributed** across pairs and each host connects to **both** nodes of its assigned pair.

```
vPC Pair 0:  leaf1 ──┬── host1    (host1 dual-homed to leaf1 AND leaf2)
             leaf2 ──┘── host2    (host2 dual-homed to leaf1 AND leaf2)

vPC Pair 1:  leaf3 ──┬── host3
             leaf4 ──┘── host4
```

If hosts don't divide evenly, the first pairs get one extra host each.

**Example** — 4 leafs (2 vPC pairs) with 8 dual-homed hosts (4 hosts per pair):
```yaml
topology:
  # vPC peer-links between pairs (leaf1↔leaf2, leaf3↔leaf4)
  - node_group1: leafs
    topology_type: INTRA_GROUP_B2B2_N
    exclude_interfaces: ["mgmt0"]
  # Dual-homed hosts distributed across vPC pairs
  - node_group1: leafs       # 4 nodes (2 pairs)
    node_group2: hosts         # 8 nodes
    topology_type: VPC_N_N
    exclude_interfaces: ["mgmt0"]
```
Result: hosts 1-4 dual-homed to leaf1+leaf2, hosts 5-8 dual-homed to leaf3+leaf4.

---

### `INTRA_GROUP_B2B_N` — Back-to-Back Pairs (1 Link)

**Requires**: `node_group1` only (no `node_group2`)

Pairs nodes within a single group sequentially: node1↔node2, node3↔node4, etc. Creates **1 link per pair**. An odd last node is left unconnected.

```
  node1 ── node2     node3 ── node4     node5 (unconnected)
```

**Example** — Back-to-back pairs in a group of 6:
```yaml
topology:
  - node_group1: routers    # 6 nodes
    topology_type: INTRA_GROUP_B2B_N
    exclude_interfaces: ["mgmt0"]
```
Result: `router1↔router2`, `router3↔router4`, `router5↔router6`.

---

### `INTRA_GROUP_B2B2_N` — Back-to-Back Pairs (2 Links)

**Requires**: `node_group1` only (no `node_group2`)

Same pairing as `INTRA_GROUP_B2B_N` but creates **2 links per pair**. This is the standard wiring for **vPC peer-links** where redundancy requires dual connections.

```
  node1 ══ node2     node3 ══ node4     (══ means 2 links)
```

**Example** — vPC peer-links for 4 leaf switches:
```yaml
topology:
  - node_group1: leafs    # 4 nodes
    topology_type: INTRA_GROUP_B2B2_N
    exclude_interfaces: ["mgmt0"]
```
Result: `leaf1↔leaf2` (x2 links), `leaf3↔leaf4` (x2 links).

---

## Auto Layout

When `auto_location: true`, the tool automatically computes (x, y) positions for each node group using a hierarchical algorithm:

1. **Hierarchy inference**: Topology types determine parent-child relationships (e.g. `CLOS_N_N` places group2 above group1).
2. **Layer assignment**: BFS from root nodes assigns vertical layers.
3. **Subtree-based positioning**: Children are centered horizontally under their parent.
4. **Infrastructure isolation**: `external_connector` and `unmanaged_switch` nodes are placed above the data-plane tree.

Groups with explicit `group_location` or `adjacent_to_group` are **not** overridden by auto-layout.

---

## Management Configuration

Management IPs are auto-generated when `group_mgmt_start_ip`, `group_mgmt_subnet`, and `group_mgmt_gw_ip` are provided. The tool:

1. Loads a base config from `<conf_files_directory>/<node_definition>.conf`.
2. Renders a Jinja2 template from `<jinja_directory>/<node_definition>.j2` with variables: `hostname`, `ip_address`, `mask`, `gw`.
3. Appends the rendered config to each node's configuration.

IPs are allocated sequentially from `group_mgmt_start_ip` within the given subnet, across all groups sharing the same subnet.

### Example Jinja2 Template (`j2/nxosv9000.j2`)

```jinja2
{% if hostname is defined %}
hostname {{ hostname }}
{% endif -%}
{% if gw is defined -%}
vrf context management
  ip route 0.0.0.0/0 {{ gw }}
{% endif -%}
{% if ip_address is defined -%}
interface mgmt 0
  ip address {{ ip_address }}/{{ mask }}
  no cdp enable
{% endif %}
```

---

## Directory Structure

```
cml/
├── config.yml                 # Main configuration
├── main.py                    # Entry point
├── cml/                       # CML API layer
│   ├── client.py              # REST client (auth, requests)
│   ├── lab.py                 # Lab CRUD operations
│   ├── node.py                # Node CRUD, update, stop, wipe
│   ├── link.py                # Link creation
│   ├── position.py            # Position helper
│   └── colors.py              # Colorized terminal output
├── wrapper/                   # Higher-level abstractions
│   ├── nodegroup.py           # NodeGroup: batch node creation
│   ├── topology.py            # Topology: wiring patterns
│   └── mgmt.py                # Management IP & config generation
├── default_configs/           # Base node configs (.conf files)
├── j2/                        # Jinja2 mgmt templates (.j2 files)
└── examples/                  # Example lab YAML files
```

---

## Examples

Full example files are available in the [`examples/`](examples/) directory. Below is a summary of each.

### 1. VXLAN EVPN Large (`examples/VXLAN_EVPN_LARGE.yml`)

A single-site VXLAN EVPN fabric with 4 spines, 12 leafs (6 vPC pairs), 2 border leafs, 2 WAN routers, and 150 dual-homed hosts.

**Topology types used**:
- `CLOS_N_N` — leafs to spines, border leafs to spines
- `INTRA_GROUP_B2B2_N` — vPC peer-links between leaf pairs and border leaf pair
- `VPC_N_N` — 150 hosts dual-homed to 6 vPC leaf pairs (25 per pair)
- `STRAIGHT_N_N` — WAN routers to border leafs (1:1), WAN routers to WAN hosts (1:1)
- `STAR_1_N` — OOB management switch to all managed groups

### 2. VXLAN EVPN Tiny Multisite (`examples/VXLAN_EVPN_TINY_MULTISITE.yml`)

Two small VXLAN EVPN sites connected via a multisite ISN router. Each site has 1 spine, 2 leafs, 1 border leaf, 1 BGW, 1 WAN router, and hosts.

**Topology types used**:
- `CLOS_N_N` — leafs/bleaf/bgw to spine (per site)
- `STRAIGHT_N_N` — WAN to border leaf, leafs to hosts, WAN to WAN host
- `STAR_1_N` — ISN to BGWs (inter-site), OOB switch to all managed groups

### 3. BGP Routed 5-Stage (`examples/BGP_ROUTED_5STAGE.yml`)

A 5-stage CLOS fabric with 2 super spines, 2 border leafs, and 2 pods (each with 2 spines, 2 leafs, and 2 hosts).

**Topology types used**:
- `STRAIGHT_N_N` — pod spines to super spines (1:1 uplink per spine, **not** full mesh)
- `CLOS_N_N` — border leafs to super spines, intra-pod leaf-spine
- `INTRA_GROUP_B2B2_N` — vPC peer-links for pod leafs and border leafs
- `STRAIGHT_N_N` — leafs to hosts
- `STAR_1_N` — OOB management

### 4. Classic 3-Tier (`examples/CLASSIC_3TIER.yml`)

Traditional core/aggregation/access architecture with vPC at aggregation layer.

**Topology types used**:
- `INTRA_GROUP_B2B2_N` — core redundant links, aggregation vPC peer-links
- `CLOS_N_N` — aggregation to core, access to aggregation
- `STRAIGHT_N_N` — access to hosts
- `STAR_1_N` — OOB management

---

## License

This project is provided as-is for lab automation purposes.
