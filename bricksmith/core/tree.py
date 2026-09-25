"""Breadth-First Search (BFS) Spanning Tree Codec for BrickSmith."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Union
import numpy as np

from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.connector import ConnectorType, Polarity


@dataclass
class InterfacePortSpec:
    """An available upward interface port on an existing assembly."""
    index: int
    brick_id: int
    part_id: str
    port_id: str
    connector_type: ConnectorType
    world_transform: np.ndarray
    port_frame: np.ndarray


@dataclass
class TreeNode:
    """A node in the BFS assembly spanning tree."""
    step_index: int
    brick_id: int
    part_id: str
    color_id: int
    parent_step_index: Optional[int]    # None for the root baseplate
    parent_port: Optional[str]
    self_port: Optional[str]
    conn_type: Optional[ConnectorType]
    transform: Optional[np.ndarray] = None
    rotation_quarters: int = 0


def _parse_port_index(port_name: str) -> int:
    """Extract flat connector index from a port identifier string."""
    if port_name in ("stud_0", "tube_0"):
        return 0
    if "_" in port_name:
        parts = port_name.split("_")
        if parts[1].isdigit():
            return int(parts[1])
    raise ValueError(f"Cannot parse numeric port index from '{port_name}'")


def _stem_numeric(stem: str) -> int:
    """Lookup the numeric catalog index for a part stem, consulting aliases and pattern variants if needed."""
    import re
    from bricknet.data import load_catalog, load_aliases

    catalog = load_catalog()
    if stem in catalog.stem_to_id:
        return catalog.stem_to_id[stem]
    aliases = load_aliases()
    if stem in aliases:
        canonical = aliases[stem][0]
        if canonical in catalog.stem_to_id:
            return catalog.stem_to_id[canonical]

    # Try resolving prefix/pattern suffixes (e.g. bl_54200pb103 -> 54200)
    s = stem[3:] if stem.startswith("bl_") else stem
    m = re.match(r"^([0-9]+[a-zA-Z]*?)(?:pb|p[0-9]|s[0-9]|d[0-9]).*$", s)
    candidates = [s]
    if m:
        candidates.append(m.group(1))

    for cand in candidates:
        if cand in catalog.stem_to_id:
            return catalog.stem_to_id[cand]
        if cand in aliases:
            canonical = aliases[cand][0]
            if canonical in catalog.stem_to_id:
                return catalog.stem_to_id[canonical]

    raise KeyError(f"Part '{stem}' not found in catalog or aliases")


def _rotation_quarters_tree(parent_transform: np.ndarray, child_transform: np.ndarray) -> int:
    relative = parent_transform[:3, :3].T @ child_transform[:3, :3]
    yaw = float(np.arctan2(relative[0, 2], relative[0, 0]))
    return int(round(np.degrees(yaw) / 90.0)) % 4


def are_connectors_compatible(pm: tuple, cm: tuple) -> tuple[bool, Optional[ConnectorType]]:
    """Determine whether two connectors can legally physically mate based on family, subtype, and polarity."""
    from bricknet.core import _STUD_MATES, _AXLE_MATES
    _EXTRA_AXLE_MATES = frozenset({("axle", "hole"), ("pin", "hole"), ("pin", "clip")})
    all_axle_mates = _AXLE_MATES | _EXTRA_AXLE_MATES

    kp, sp, pol_p = pm[0], pm[1], pm[2]
    kc, sc, pol_c = cm[0], cm[1], cm[2]

    # 1. Stud <-> Hole / Tube family
    if (kp == "stud" and kc == "hole") or (kp == "hole" and kc == "stud"):
        sub_pair = (min(sp, sc), max(sp, sc))
        if sub_pair in _STUD_MATES:
            return True, ConnectorType.STUD
        return False, None

    # 2. Axle family (bars, clips, axles, pins, sockets, holes)
    if kp == "axle" and kc == "axle":
        sub_pair = (min(sp, sc), max(sp, sc))
        if sub_pair in all_axle_mates:
            if "clip" in (sp, sc) or "bar" in (sp, sc):
                return True, ConnectorType.CLIP
            return True, ConnectorType.AXLE
        return False, None

    # 3. Hinge, Ball, Fixed (require identical subtype and opposite polarity: one 'in', one 'on')
    if kp == kc and kp in ("hinge", "ball", "fixed"):
        if sp == sc and pol_p in ("in", "on") and pol_c in ("in", "on") and pol_p != pol_c:
            if kp == "hinge":
                return True, ConnectorType.HINGE
            if kp == "ball":
                return True, ConnectorType.BALL
            return True, ConnectorType.STUD
        return False, None

    return False, None


def _recover_intra_bag_mating(parent_part, child_part, conn_list):
    """Discover exact mating ports and relative yaw that reconstruct child_part from parent_part with < 1e-4 LDU error."""
    try:
        p_num = _stem_numeric(parent_part.part_id)
        c_num = _stem_numeric(child_part.part_id)
    except KeyError:
        return None
    if p_num >= len(conn_list) or c_num >= len(conn_list):
        return None

    # Collision check: overlapping or interpenetrating pieces cannot legally mate
    import os
    from pathlib import Path
    _pkg_root = Path(__file__).resolve().parents[2]
    os.environ.setdefault("BRICKNET_DATA", str(_pkg_root / "data/bricknet-data"))
    from bricknet.collision import colliding_pairs
    if colliding_pairs([p_num, c_num], [parent_part.transform, child_part.transform]):
        return None

    p_conns = conn_list[p_num]
    c_conns = conn_list[c_num]
    from bricksmith.physics.validator import frame
    from bricksmith.generation.sampler import yaw_matrix

    best = None
    best_err = 1e9
    for pi, pm in enumerate(p_conns):
        pf = frame(p_num, pi)
        pw = (parent_part.transform @ pf)[:3, 3]
        for ci, cm in enumerate(c_conns):
            compat, conn_type = are_connectors_compatible(pm, cm)
            if not compat:
                continue
            cf = frame(c_num, ci)
            cw = (child_part.transform @ cf)[:3, 3]
            if np.linalg.norm(pw - cw) > 0.5:
                continue
            for rot_q in (0, 1, 2, 3):
                test_tf = parent_part.transform @ pf @ yaw_matrix(rot_q * 90) @ np.linalg.inv(cf)
                pos_err = np.linalg.norm(test_tf[:3, 3] - child_part.transform[:3, 3])
                rot_err = np.linalg.norm(test_tf[:3, :3] - child_part.transform[:3, :3])
                err = pos_err + rot_err
                if err < 1e-4:
                    return f"port_{pi}", f"port_{ci}", rot_q, 0.0, conn_type
                if err < best_err:
                    best_err = err
                    best = (f"port_{pi}", f"port_{ci}", rot_q, err, conn_type)
    return best


class BFSTreeCodec:
    """Encodes an AssemblyGraph into a BFS spanning tree path sequence,
    and decodes path sequences back into an AssemblyGraph.
    """

    @staticmethod
    def encode(
        graph: AssemblyGraph,
        root_id: Optional[int] = None,
        interface_assembly: Optional[AssemblyGraph] = None,
        interface_ports: Optional[Sequence[InterfacePortSpec]] = None,
        require_anchored: bool = False,
    ) -> List[TreeNode]:
        """Traverse the graph in Breadth-First Search order starting from root_id.
        If interface_assembly or interface_ports are provided, roots attached to prior
        assemblies via interface connections will encode parent_port as 'iface_{index}'
        and derive their rotation_quarters from the interface port.
        If require_anchored is True, only pieces with a verified kinematic attachment
        path to the base anchor (or prior interface assembly) are retained.
        """
        if not graph.parts:
            return []

        if interface_assembly is not None and interface_ports is None:
            interface_ports = get_available_interface_ports(interface_assembly)

        # Map (brick_id, port_id) -> InterfacePortSpec and brick_id -> list[spec]
        iface_map: dict[tuple[int, str], InterfacePortSpec] = {}
        ifaces_by_brick: dict[int, list[InterfacePortSpec]] = {}
        if interface_ports is not None:
            for spec in interface_ports:
                iface_map[(spec.brick_id, spec.port_id)] = spec
                ifaces_by_brick.setdefault(spec.brick_id, []).append(spec)

        # Discover which bricks in this graph connect to the interface
        iface_attachments: dict[int, tuple[str, str, ConnectorType, int]] = {}
        from bricknet.data import load_catalog, load_connector_list
        from bricksmith.physics.validator import frame
        from bricksmith.generation.sampler import yaw_matrix

        catalog = load_catalog()
        conn_list = load_connector_list()
        if iface_map and interface_assembly is not None:
            used_spec_indices = set()
            for c_id, c_part in sorted(graph.parts.items()):
                best_match = None
                for p_id, p_part in sorted(interface_assembly.parts.items()):
                    if np.linalg.norm(p_part.position - c_part.position) > 150:
                        continue
                    m = _recover_intra_bag_mating(p_part, c_part, conn_list)
                    if m and m[3] < 1e-4:
                        p_port, c_port, rot_q, _ = m[:4]
                        conn_type = m[4] if len(m) > 4 else ConnectorType.STUD
                        spec = iface_map.get((p_id, p_port))
                        if spec is not None and spec.index not in used_spec_indices:
                            if best_match is None or spec.index < best_match[0].index:
                                best_match = (spec, c_port, rot_q, conn_type)
                if best_match is not None:
                    spec, c_port, rot_q, conn_type = best_match
                    used_spec_indices.add(spec.index)
                    iface_attachments[c_id] = (f"iface_{spec.index}", c_port, conn_type, rot_q)

        # If require_anchored is requested on a dependent bag with no interface attachments, return empty
        if require_anchored and interface_assembly is not None and not iface_attachments:
            return []

        # Build intra-bag mating adjacency with exact verified kinematics
        intra_adj: dict[int, list[tuple[int, str, str, ConnectorType, int]]] = {}
        for b1, p1 in sorted(graph.parts.items()):
            for b2, p2 in sorted(graph.parts.items()):
                if b1 >= b2:
                    continue
                if np.linalg.norm(p1.position - p2.position) > 150:
                    continue
                m = _recover_intra_bag_mating(p1, p2, conn_list)
                if m and m[3] < 1e-4:
                    conn_type = m[4] if len(m) > 4 else ConnectorType.STUD
                    intra_adj.setdefault(b1, []).append((b2, m[0], m[1], conn_type, m[2]))
                    m_inv = _recover_intra_bag_mating(p2, p1, conn_list)
                    if m_inv and m_inv[3] < 1e-4:
                        inv_conn_type = m_inv[4] if len(m_inv) > 4 else ConnectorType.STUD
                        intra_adj.setdefault(b2, []).append((b1, m_inv[0], m_inv[1], inv_conn_type, m_inv[2]))

        def get_best_grounded_root(candidate_bids: set[int]) -> int:
            comp_visited = set()
            comps = []
            for b in candidate_bids:
                if b not in comp_visited:
                    comp = []
                    q = [b]
                    comp_visited.add(b)
                    while q:
                        curr = q.pop()
                        comp.append(curr)
                        for nbr, _, _, _, _ in intra_adj.get(curr, []):
                            if nbr in candidate_bids and nbr not in comp_visited:
                                comp_visited.add(nbr)
                                q.append(nbr)
                    comps.append(comp)
            best_comp = max(comps, key=len) if comps else list(candidate_bids)
            return max(best_comp, key=lambda bid: (graph.parts[bid].position[1], -bid))

        visited = set()
        tree_nodes: List[TreeNode] = []
        brick_to_step: dict[int, int] = {}
        step = 0

        while len(visited) < len(graph.parts):
            if not visited and root_id is not None and root_id in graph.parts:
                curr_root = root_id
                if curr_root in iface_attachments:
                    p_port, s_port, c_type, rot_q = iface_attachments[curr_root]
                else:
                    p_port, s_port, c_type, rot_q = None, None, None, 0
            elif not visited and interface_assembly is None:
                curr_root = get_best_grounded_root(set(graph.parts.keys()))
                p_port, s_port, c_type, rot_q = None, None, None, 0
            else:
                unvisited_iface = [bid for bid in iface_attachments if bid not in visited]
                if unvisited_iface:
                    curr_root = min(unvisited_iface, key=lambda bid: (iface_attachments[bid][0], bid))
                    p_port, s_port, c_type, rot_q = iface_attachments[curr_root]
                elif require_anchored:
                    # All anchored/interface trees have been visited! Stop traversal.
                    break
                else:
                    unvisited = [bid for bid in graph.parts if bid not in visited]
                    curr_root = max(unvisited, key=lambda bid: (graph.parts[bid].position[1], -bid))
                    p_port, s_port, c_type, rot_q = None, None, None, 0

            if require_anchored and interface_assembly is not None and curr_root not in iface_attachments:
                break

            visited.add(curr_root)
            queue = [(curr_root, None, p_port, s_port, c_type, rot_q)]

            while queue:
                curr_id, parent_step, pp, sp, ct, rq = queue.pop(0)
                part = graph.parts[curr_id]
                brick_to_step[curr_id] = step

                node = TreeNode(
                    step_index=step,
                    brick_id=curr_id,
                    part_id=part.part_id,
                    color_id=part.color_id,
                    parent_step_index=parent_step,
                    parent_port=pp,
                    self_port=sp,
                    conn_type=ct,
                    transform=part.transform.copy(),
                    rotation_quarters=rq,
                )
                tree_nodes.append(node)

                # Discover neighbors: from verified exact kinematic contacts
                curr_step = step
                for nbr_id, my_p, nbr_p, ct_nbr, nbr_rq in intra_adj.get(curr_id, []):
                    if nbr_id not in visited and nbr_id not in iface_attachments:
                        visited.add(nbr_id)
                        queue.append((nbr_id, curr_step, my_p, nbr_p, ct_nbr, nbr_rq))

                # Fallback to declared connections for abstract/non-geometric graphs without kinematic contacts
                if not intra_adj and not iface_attachments and not require_anchored:
                    for conn in graph.connections:
                        nbr = None
                        mp = None
                        np_port = None
                        if conn.source_brick_id == curr_id:
                            nbr = conn.target_brick_id
                            mp = conn.source_port_id
                            np_port = conn.target_port_id
                        elif conn.target_brick_id == curr_id:
                            nbr = conn.source_brick_id
                            mp = conn.target_port_id
                            np_port = conn.source_port_id
                        if nbr is not None and nbr in graph.parts and nbr not in visited:
                            visited.add(nbr)
                            rq_nbr = _rotation_quarters_tree(part.transform, graph.parts[nbr].transform)
                            queue.append((nbr, step, mp, np_port, conn.connection_type, rq_nbr))

                step += 1

        return tree_nodes

    @staticmethod
    def serialize_path_text(tree_nodes: List[TreeNode]) -> str:
        """Serialize BFS tree nodes into a clean tokenized path-text format.
        Format per line:
        STEP: <step> | PART: <part_id> | COLOR: <color_id> | PARENT: <p_step> | PORTS: <p_port>-><s_port> | TYPE: <conn_type> | POSE: <x y z a b c d e f g h i>
        """
        lines = []
        for node in tree_nodes:
            p_step = node.parent_step_index if node.parent_step_index is not None else -1
            p_port = node.parent_port or "ROOT"
            s_port = node.self_port or "ROOT"
            c_type = node.conn_type.value if node.conn_type else "ROOT"
            x, y, z = node.transform[:3, 3]
            r = node.transform[:3, :3]
            a, b, c = r[0, 0], r[0, 1], r[0, 2]
            d, e, f = r[1, 0], r[1, 1], r[1, 2]
            g, h, i = r[2, 0], r[2, 1], r[2, 2]
            lines.append(
                f"STEP: {node.step_index:04d} | ID: {node.brick_id:04d} | PART: {node.part_id} | COLOR: {node.color_id} | "
                f"PARENT: {p_step:04d} | PORTS: {p_port}->{s_port} | TYPE: {c_type} | "
                f"POSE: {x:.4f} {y:.4f} {z:.4f} {a:.6f} {b:.6f} {c:.6f} {d:.6f} {e:.6f} {f:.6f} {g:.6f} {h:.6f} {i:.6f}"
            )
        return "\n".join(lines)

    @staticmethod
    def deserialize_path_text(path_text: str) -> List[TreeNode]:
        """Deserialize tokenized path-text into a list of TreeNode objects."""
        tree_nodes: List[TreeNode] = []
        for line in path_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [seg.strip() for seg in line.split("|")]
            meta = {}
            for seg in parts:
                k, _, v = seg.partition(":")
                meta[k.strip()] = v.strip()

            step = int(meta["STEP"])
            brick_id = int(meta["ID"]) if "ID" in meta else step + 1
            part_id = meta["PART"]
            color_id = int(meta["COLOR"])
            p_step_raw = int(meta["PARENT"])
            parent_step = p_step_raw if p_step_raw >= 0 else None

            ports_str = meta.get("PORTS", "ROOT->ROOT")
            p_port_raw, _, s_port_raw = ports_str.partition("->")
            parent_port = None if p_port_raw == "ROOT" else p_port_raw
            self_port = None if s_port_raw == "ROOT" else s_port_raw

            c_type_raw = meta.get("TYPE", "ROOT")
            try:
                conn_type = None if c_type_raw == "ROOT" else ConnectorType(c_type_raw)
            except ValueError:
                conn_type = ConnectorType.STUD

            transform = np.eye(4, dtype=np.float64)
            if "POSE" in meta:
                vals = [float(x) for x in meta["POSE"].split()]
                if len(vals) == 12:
                    x, y, z, a, b, c, d, e, f, g, h, i = vals
                    transform = np.array([
                        [a, b, c, x],
                        [d, e, f, y],
                        [g, h, i, z],
                        [0.0, 0.0, 0.0, 1.0],
                    ], dtype=np.float64)

            node = TreeNode(
                step_index=step,
                brick_id=brick_id,
                part_id=part_id,
                color_id=color_id,
                parent_step_index=parent_step,
                parent_port=parent_port,
                self_port=self_port,
                conn_type=conn_type,
                transform=transform,
            )
            tree_nodes.append(node)
        return tree_nodes

    @staticmethod
    def decode(
        tree_nodes_or_text: Union[List[TreeNode], str],
        name: str = "reconstructed",
        interface_assembly: Optional[AssemblyGraph] = None,
        interface_ports: Optional[Sequence[InterfacePortSpec]] = None,
        anchor_transform: Optional[np.ndarray] = None,
        anchor_transforms: Optional[Union[np.ndarray, dict[int, np.ndarray]]] = None,
        strict: bool = False,
    ) -> AssemblyGraph:
        """Decode a BFS spanning tree path sequence or list of TreeNodes back into an AssemblyGraph.
        Any unanchored roots without interface attachments or permitted anchors are quarantined in
        graph.unsupported_parts and excluded from the reconstructed assembly state.
        """
        if isinstance(tree_nodes_or_text, str):
            if "STEP:" in tree_nodes_or_text:
                tree_nodes = BFSTreeCodec.deserialize_path_text(tree_nodes_or_text)
            else:
                # Compact parent-relative attachment digits (no absolute pose).
                from bricksmith.training.codec import tree_nodes_from_target_text

                tree_nodes = tree_nodes_from_target_text(tree_nodes_or_text)
        else:
            tree_nodes = tree_nodes_or_text

        if interface_assembly is not None and interface_ports is None:
            interface_ports = get_available_interface_ports(interface_assembly)

        graph = AssemblyGraph(name=name)
        graph.interface_connections = []
        graph.unsupported_parts = {}
        unsupported_steps: set[int] = set()
        step_to_inst: dict[int, int] = {}

        for node in tree_nodes:
            if node.parent_step_index is not None and node.parent_step_index in unsupported_steps:
                unsupported_steps.add(node.step_index)
                graph.unsupported_parts[node.brick_id] = node
                continue

            node_transform = None if node.transform is None else node.transform.copy()
            if node_transform is None or np.allclose(node_transform, np.eye(4)):
                if node.parent_step_index is not None:
                    if node.parent_step_index not in step_to_inst:
                        if strict:
                            raise ValueError(
                                f"Parent step {node.parent_step_index} was not decoded before child step {node.step_index}"
                            )
                        unsupported_steps.add(node.step_index)
                        graph.unsupported_parts[node.brick_id] = node
                        continue
                    parent_inst = step_to_inst[node.parent_step_index]
                    parent_part = graph.parts[parent_inst]
                    p_port = node.parent_port or "port_0"
                    s_port = node.self_port or "port_0"

                    from bricksmith.physics.validator import frame
                    from bricksmith.generation.sampler import yaw_matrix

                    p_num = _stem_numeric(parent_part.part_id)
                    c_num = _stem_numeric(node.part_id)
                    p_idx = _parse_port_index(p_port)
                    s_idx = _parse_port_index(s_port)
                    pf = frame(p_num, p_idx)
                    cf = frame(c_num, s_idx)

                    rot_deg = int(getattr(node, "rotation_quarters", 0)) * 90
                    node_transform = parent_part.transform @ pf @ yaw_matrix(rot_deg) @ np.linalg.inv(cf)
                elif node.parent_step_index is None and node.parent_port and node.parent_port.startswith("iface_"):
                    if interface_ports is None:
                        raise ValueError(
                            f"Node at step {node.step_index} references interface port '{node.parent_port}', "
                            "but no interface ports or interface assembly were provided to decode()"
                        )
                    iface_idx = _parse_port_index(node.parent_port)
                    if not (0 <= iface_idx < len(interface_ports)):
                        raise IndexError(
                            f"Interface port index {iface_idx} out of range (available interface ports: {len(interface_ports)})"
                        )
                    iface = interface_ports[iface_idx]
                    from bricksmith.physics.validator import frame
                    from bricksmith.generation.sampler import yaw_matrix

                    c_num = _stem_numeric(node.part_id)
                    s_port = node.self_port or "port_0"
                    s_idx = _parse_port_index(s_port)
                    cf = frame(c_num, s_idx)

                    rot_deg = int(getattr(node, "rotation_quarters", 0)) * 90
                    node_transform = iface.world_transform @ yaw_matrix(rot_deg) @ np.linalg.inv(cf)
                elif node.parent_step_index is None:
                    anchors = anchor_transforms if anchor_transforms is not None else anchor_transform
                    matched_anchor = None
                    if anchors is not None:
                        if isinstance(anchors, dict):
                            if node.brick_id in anchors:
                                matched_anchor = np.asarray(anchors[node.brick_id], dtype=np.float64).copy()
                            elif node.step_index in anchors:
                                matched_anchor = np.asarray(anchors[node.step_index], dtype=np.float64).copy()
                        elif node.step_index == 0 or not graph.parts:
                            matched_anchor = np.asarray(anchors, dtype=np.float64).copy()
                    elif (node.step_index == 0 or not graph.parts) and interface_assembly is None and interface_ports is None:
                        matched_anchor = np.eye(4, dtype=np.float64)

                    if matched_anchor is not None:
                        node_transform = matched_anchor
                    else:
                        if strict:
                            raise ValueError(
                                f"Unresolved root at step {node.step_index} (brick_id={node.brick_id}) has no anchor or interface connection"
                            )
                        unsupported_steps.add(node.step_index)
                        graph.unsupported_parts[node.brick_id] = node
                        continue
                else:
                    unsupported_steps.add(node.step_index)
                    graph.unsupported_parts[node.brick_id] = node
                    continue

            inst_id = graph.add_part(
                part_id=node.part_id,
                color_id=node.color_id,
                transform=node_transform,
                instance_id=node.brick_id,
            )
            step_to_inst[node.step_index] = inst_id

            if node.parent_step_index is not None:
                parent_inst = step_to_inst[node.parent_step_index]
                p_port = node.parent_port or "port_0"
                s_port = node.self_port or "port_0"
                c_type = node.conn_type or ConnectorType.STUD
                graph.connect(
                    source_id=parent_inst,
                    source_port=p_port,
                    target_id=inst_id,
                    target_port=s_port,
                    conn_type=c_type,
                )
            elif node.parent_step_index is None and node.parent_port and node.parent_port.startswith("iface_"):
                iface_idx = _parse_port_index(node.parent_port)
                if interface_ports is not None and 0 <= iface_idx < len(interface_ports):
                    iface = interface_ports[iface_idx]
                    s_port = node.self_port or "port_0"
                    c_type = node.conn_type or ConnectorType.STUD
                    from bricksmith.core.connector import PortConnection
                    graph.interface_connections.append(
                        PortConnection(
                            source_brick_id=iface.brick_id,
                            source_port_id=iface.port_id,
                            target_brick_id=inst_id,
                            target_port_id=s_port,
                            connection_type=c_type,
                        )
                    )

        return graph


def get_available_interface_ports(graph: AssemblyGraph) -> List[InterfacePortSpec]:
    """Find all unoccupied upward-facing stud ports on an assembly, sorted deterministically."""
    from bricknet.data import load_catalog, load_connector_list
    from bricksmith.physics.validator import frame

    catalog = load_catalog()
    conn_list = load_connector_list()

    occupied = set()
    for c in graph.connections:
        occupied.add((c.source_brick_id, c.source_port_id))
        occupied.add((c.target_brick_id, c.target_port_id))

    available = []
    for bid, part in sorted(graph.parts.items()):
        try:
            numeric = _stem_numeric(part.part_id)
        except KeyError:
            continue
        if numeric >= len(conn_list):
            continue
        for idx, meta in enumerate(conn_list[numeric]):
            kind = meta[0]
            port_id = f"port_{idx}"
            if kind == "stud" and (bid, port_id) not in occupied:
                pf = frame(numeric, idx)
                world_t = part.transform @ pf
                world_pos = world_t[:3, 3]
                available.append((world_pos, bid, part.part_id, port_id, world_t, pf))

    available.sort(key=lambda item: (
        round(float(item[0][1]), 2),
        round(float(item[0][0]), 2),
        round(float(item[0][2]), 2),
        item[1],
        item[3],
    ))

    result = []
    for idx, (world_pos, bid, part_id, port_id, world_t, pf) in enumerate(available):
        result.append(
            InterfacePortSpec(
                index=idx,
                brick_id=bid,
                part_id=part_id,
                port_id=port_id,
                connector_type=ConnectorType.STUD,
                world_transform=world_t,
                port_frame=pf,
            )
        )
    return result


def merge_assemblies(
    base_graph: AssemblyGraph,
    bag_graph: AssemblyGraph,
    name: str = "merged",
) -> AssemblyGraph:
    """Merge two assembly graphs across their validated bag interface connections."""
    merged = AssemblyGraph(name=name)
    # 1. Copy base_graph parts and connections
    for bid, p in base_graph.parts.items():
        merged.add_part(part_id=p.part_id, color_id=p.color_id, transform=p.transform.copy(), instance_id=bid)
    for c in base_graph.connections:
        merged.connect(
            source_id=c.source_brick_id,
            source_port=c.source_port_id,
            target_id=c.target_brick_id,
            target_port=c.target_port_id,
            conn_type=c.connection_type,
        )

    # 2. Add bag_graph parts (re-indexing if instance IDs collide)
    bag_id_map: dict[int, int] = {}
    for bid, p in bag_graph.parts.items():
        new_id = bid if bid not in merged.parts else max(merged.parts.keys(), default=0) + 1
        bag_id_map[bid] = new_id
        merged.add_part(part_id=p.part_id, color_id=p.color_id, transform=p.transform.copy(), instance_id=new_id)

    # 3. Add bag_graph internal connections
    for c in bag_graph.connections:
        merged.connect(
            source_id=bag_id_map[c.source_brick_id],
            source_port=c.source_port_id,
            target_id=bag_id_map[c.target_brick_id],
            target_port=c.target_port_id,
            conn_type=c.connection_type,
        )

    # 4. Add cross-bag interface connections
    for ic in getattr(bag_graph, "interface_connections", []):
        parent_id = ic.source_brick_id
        child_id = bag_id_map.get(ic.target_brick_id, ic.target_brick_id)
        if parent_id in merged.parts and child_id in merged.parts:
            merged.connect(
                source_id=parent_id,
                source_port=ic.source_port_id,
                target_id=child_id,
                target_port=ic.target_port_id,
                conn_type=ic.connection_type,
            )

    return merged
