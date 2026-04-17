# [ process + cache ] affinity

CPU Affinity Pin with Cache Topology Awareness for Linux/POSIX x86-64 systems.

A CPU affinity tool that pins processes to cache domains (L1I, L1D, L2, L3) rather than individual cores. It reads Linux sysfs to map which cores share which cache levels.

- cli.py - CLI entry point with commands: show, pin, unpin, suggest
- src/topology.py - Discovers cache topology from Linux (VFS) sysfs (/sys/devices/system/cpu/)
- src/pinner.py - Process pinning logic to systemc cores using `taskset`

## Commands

```bash
# Show cache topology
python cli.py show

# Show cache + NUMA topology
python cli.py show --numa

# Pin process to L2 cache domain
python cli.py pin --pid 1234 --level L2

# Pin process to specific core
python cli.py pin --pid 1234 --core 7

# Unpin (reset to all cores)
python cli.py unpin --pid 1234

# Suggest optimal cores for process
python cli.py suggest --pid 1234

# Verbose suggestions
python cli.py suggest --pid 1234 -v
```

## Quick Examples

```bash
# Find a target PID
ps aux | grep python

# Check cache topology
python cli.py show
# L2: Domain 0: cores [0, 1]

# Pin to L2 cache
python cli.py pin --pid 12345 --level L2

# Verify
python cli.py suggest --pid 12345 -v
```

