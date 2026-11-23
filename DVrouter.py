import json
from router import Router
from packet import Packet


class DVrouter(Router):
    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.ports = {}             # port -> (neighbor address, link cost)
        self.neighbor_vectors = {}  # neighbor -> {destination: cost}
        self.distance = {addr: 0}
        self.next_hop = {}
        self.infinity = 16

    def _recompute(self):
        dist = {self.addr: 0}
        hop = {}
        # Direct links are known independently of neighbor advertisements.
        for port, (neighbor, cost) in self.ports.items():
            if cost < dist.get(neighbor, self.infinity):
                dist[neighbor] = cost
                hop[neighbor] = port
        for neighbor, vector in self.neighbor_vectors.items():
            if neighbor not in self.ports_by_neighbor():
                continue
            port, link_cost = self.ports_by_neighbor()[neighbor]
            for destination, advertised in vector.items():
                if destination == self.addr or advertised >= self.infinity:
                    continue
                candidate = min(self.infinity, link_cost + advertised)
                if candidate < dist.get(destination, self.infinity):
                    dist[destination] = candidate
                    hop[destination] = port
        self.distance, self.next_hop = dist, hop

    def ports_by_neighbor(self):
        return {neighbor: (port, cost) for port, (neighbor, cost) in self.ports.items()}

    def _advertisement(self, outgoing_neighbor=None):
        # Poison reverse: routes learned through this neighbor are advertised as unreachable.
        vector = {}
        for destination, cost in self.distance.items():
            if destination == self.addr:
                continue
            if outgoing_neighbor is not None and self.next_hop.get(destination) == self.ports_by_neighbor().get(outgoing_neighbor, (None,))[0]:
                vector[destination] = self.infinity
            else:
                vector[destination] = cost
        return vector

    def _send_updates(self):
        for port, (neighbor, _) in list(self.ports.items()):
            msg = {"type": "dv", "vector": self._advertisement(neighbor)}
            self.send(port, Packet(Packet.ROUTING, self.addr, neighbor, json.dumps(msg)))

    def handle_packet(self, port, packet):
        if packet.is_traceroute:
            out_port = self.next_hop.get(packet.dst_addr)
            if out_port is not None:
                self.send(out_port, packet)
            return
        try:
            data = json.loads(packet.content)
            if data.get("type") != "dv":
                return
            neighbor = self.ports.get(port, (None, None))[0]
            if neighbor is None:
                return
            self.neighbor_vectors[neighbor] = data.get("vector", {})
            old = (dict(self.distance), dict(self.next_hop))
            self._recompute()
            if old != (self.distance, self.next_hop):
                self._send_updates()
        except (TypeError, ValueError, AttributeError):
            return

    def handle_new_link(self, port, endpoint, cost):
        self.ports[port] = (endpoint, cost)
        self.neighbor_vectors.pop(endpoint, None)
        self._recompute()
        self._send_updates()

    def handle_remove_link(self, port):
        old = self.ports.pop(port, None)
        if old:
            self.neighbor_vectors.pop(old[0], None)
        self._recompute()
        self._send_updates()

    def handle_time(self, time_ms):
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._send_updates()

    def __repr__(self):
        return f"DVrouter(addr={self.addr}, routes={self.distance})"
