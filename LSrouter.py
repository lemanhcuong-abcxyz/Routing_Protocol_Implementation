import heapq
import json

from packet import Packet
from router import Router


class LSrouter(Router):
    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.neighbors = {}
        self.seq = 0
        self.lsdb = {self.addr: (self.seq, {})}
        self.fwd = {}

    def _own_links(self):
        return {nbr: cost for nbr, cost in self.neighbors.values()}

    def _make_lsp(self):
        content = json.dumps({
            "origin": self.addr,
            "seq": self.seq,
            "links": self.lsdb[self.addr][1],
        })
        return content

    def _flood(self, content, except_port=None):
        for port, (nbr, _) in self.neighbors.items():
            if port == except_port:
                continue
            self.send(port, Packet(Packet.ROUTING, self.addr, nbr, content))

    def _update_own_state(self):
        self.seq += 1
        self.lsdb[self.addr] = (self.seq, self._own_links())
        self._dijkstra()
        self._flood(self._make_lsp())

    def _dijkstra(self):
        graph = {}
        for origin, (_, links) in self.lsdb.items():
            for nbr, cost in links.items():
                if nbr in self.lsdb and origin not in self.lsdb[nbr][1]:
                    continue
                graph.setdefault(origin, {})[nbr] = cost

        dist = {self.addr: 0}
        first_hop = {}
        heap = [(0, self.addr, None)]
        visited = set()

        while heap:
            d, node, hop = heapq.heappop(heap)
            if node in visited:
                continue
            visited.add(node)
            if hop is not None:
                first_hop[node] = hop
            for nbr, cost in graph.get(node, {}).items():
                nd = d + cost
                if nbr not in dist or nd < dist[nbr]:
                    dist[nbr] = nd
                    heapq.heappush(heap, (nd, nbr, nbr if node == self.addr else hop))

        port_of = {nbr: port for port, (nbr, _) in self.neighbors.items()}
        self.fwd = {
            dst: port_of[hop]
            for dst, hop in first_hop.items()
            if hop in port_of
        }

    def handle_packet(self, port, packet):
        if packet.is_traceroute:
            out_port = self.fwd.get(packet.dst_addr)
            if out_port is not None:
                self.send(out_port, packet)
            return

        lsp = json.loads(packet.content)
        origin, seq, links = lsp["origin"], lsp["seq"], lsp["links"]
        if origin == self.addr:
            return

        old = self.lsdb.get(origin)
        if old is not None and seq <= old[0]:
            return

        self.lsdb[origin] = (seq, links)
        if old is None or old[1] != links:
            self._dijkstra()
        self._flood(packet.content, except_port=port)

    def handle_new_link(self, port, endpoint, cost):
        self.neighbors[port] = (endpoint, cost)
        self._update_own_state()

    def handle_remove_link(self, port):
        if port not in self.neighbors:
            return
        self.neighbors.pop(port)
        self._update_own_state()

    def handle_time(self, time_ms):
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._flood(self._make_lsp())

    def __repr__(self):
        rows = [f"LSrouter(addr={self.addr}, seq={self.seq})"]
        for dst in sorted(self.fwd):
            rows.append(f"  {dst}: port={self.fwd[dst]}")
        return "\n".join(rows)
