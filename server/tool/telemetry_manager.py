import threading

_telemetry_lock = threading.Lock()
_nodes = {"root": {"id": "root", "name": "Main Agent", "status": "idle", "children": []}}

def update_node_status(node_id: str, status: str):
    with _telemetry_lock:
        if node_id in _nodes:
            _nodes[node_id]["status"] = status

def add_child_node(parent_id: str, child_id: str, child_name: str):
    with _telemetry_lock:
        if child_id not in _nodes:
            _nodes[child_id] = {"id": child_id, "name": child_name, "status": "idle", "children": []}
        if parent_id in _nodes and child_id not in _nodes[parent_id]["children"]:
            _nodes[parent_id]["children"].append(child_id)

def remove_node(node_id: str):
    with _telemetry_lock:
        if node_id in _nodes:
            del _nodes[node_id]
        for node in _nodes.values():
            if node_id in node["children"]:
                node["children"].remove(node_id)

def get_tree(node_id="root"):
    with _telemetry_lock:
        if node_id not in _nodes:
            return None
        node = _nodes[node_id].copy()
        node["children"] = [get_tree(c) for c in node["children"] if c in _nodes]
        return node
