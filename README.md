# Harvard CS145 Routing — personalized implementation

This package contains personalized implementations of both routing algorithms:

- `DVrouter.py`: Distance Vector, with periodic advertisements and poisoned reverse.
- `LSrouter.py`: Link State, with sequence numbers, flooding, and Dijkstra shortest-path calculation.

## Integration

Copy these two files into the root of your original Harvard-CS145 `routing` repository, replacing the starter files. Keep the simulator, JSON topologies, `packet.py`, `router.py`, tests, and submodules unchanged.

## Run tests in the original repository

```bash
python network.py 01_small_net.json DV
python network.py 01_small_net.json LS
./test_scripts/test_dv_ls.sh DV
./test_scripts/test_dv_ls.sh LS
```

Run the full suite with:

```bash
./test_scripts/test_dv_ls.sh
```

**Note:** The source repository could not be cloned in this environment (network DNS unavailable), so these files are not tested against the simulator here. Run the tests locally before submitting.

## Algorithm overview

### Distance Vector
Each router stores neighbor link costs and the latest distance vector received from each neighbor. It recalculates costs using Bellman-Ford-style updates and forwards packets using its next-hop port. It periodically advertises vectors and uses poisoned reverse to reduce routing loops.

### Link State
Each router advertises its own adjacency list with a monotonically increasing sequence number. Newer advertisements are flooded, stored in a local link-state database, and used to calculate next hops with Dijkstra's algorithm.
