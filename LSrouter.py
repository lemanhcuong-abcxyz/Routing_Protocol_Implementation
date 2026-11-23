"""Link-state routing implementation for the Harvard CS145 simulator."""
import json
import heapq
from router import Router
from packet import Packet


class LSrouter(Router):
    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.ports = {}              # port -> (neighbor address, link cost)
        self.database = {addr: {}}    # router address -> adjacency map
        self.sequence = 0
        self.sequences = {addr: 0}
        self.next_hop = {}

    def _own_state(self):
        self.database[self.addr] = {neighbor: cost for _, (neighbor, cost) in self.ports.items()}

    def _originate(self):
        self.sequence += 1
        self.sequences[self.addr] = self.sequence
        self._own_state()
        payload = json.dumps({"type": "ls", "origin": self.addr, "seq": self.sequence,
                             "links": self.database[self.addr]})
        for port, (neighbor, _) in list(self.ports.items()):
            self.send(port, Packet(Packet.ROUTING, self.addr, neighbor, payload))

    def _compute_routes(self):
        graph = {node: dict(edges) for node, edges in self.database.items()}
        graph.setdefault(self.addr, {})
        # Add local link state so current adjacency is authoritative.
        graph[self.addr] = {neighbor: cost for _, (neighbor, cost) in self.ports.items()}
        distances = {self.addr: 0}
        first_port = {}
        queue = [(0, self.addr, None)]
        visited = set()
        while queue:
            cost_so_far, node, first = heapq.heappop(queue)
            if node in visited:
                continue
            visited.add(node)
            if node != self.addr and first is not None:
                distances[node] = cost_so_far
                first_port[node] = first
            for neighbor, edge_cost in graph.get(node, {}).items():
                if neighbor in visited:
                    continue
                new_cost = cost_so_far + edge_cost
                new_first = neighbor if node == self.addr else first
                if new_cost < distances.get(neighbor, float("inf")):
                    distances[neighbor] = new_cost
                    heapq.heappush(queue, (new_cost, neighbor, new_first))
                    if node == self.addr:
                        first_port[neighbor] = next((p for p, (n, _) in self.ports.items() if n == neighbor), None)
        self.next_hop = {dest: port for dest, port in first_port.items() if port is not None}

    def handle_packet(self, port, packet):
        if packet.is_traceroute:
            out_port = self.next_hop.get(packet.dst_addr)
            if out_port is not None:
                self.send(out_port, packet)
            return
        try:
            data = json.loads(packet.content)
            if data.get("type") != "ls":
                return
            origin = data["origin"]
            seq = int(data["seq"])
            if seq <= self.sequences.get(origin, -1):
                return
            self.sequences[origin] = seq
            self.database[origin] = data.get("links", {})
            self._compute_routes()
            # Flood only to neighbors other than the incoming port.
            for out_port, (neighbor, _) in list(self.ports.items()):
                if out_port == port:
                    continue
                self.send(out_port, Packet(Packet.ROUTING, self.addr, neighbor, packet.content))
        except (KeyError, TypeError, ValueError):
            return

    def handle_new_link(self, port, endpoint, cost):
        self.ports[port] = (endpoint, cost)
        self._compute_routes()
        self._originate()

    def handle_remove_link(self, port):
        self.ports.pop(port, None)
        self._compute_routes()
        self._originate()

    def handle_time(self, time_ms):
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._originate()

    def __repr__(self):
        return f"LSrouter(addr={self.addr}, next_hop={self.next_hop})"
