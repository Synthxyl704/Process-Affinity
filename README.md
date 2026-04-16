# Process-Affinity
Hand over CPU affinity to processes in linux (only) with cache topologies and suggestions.

---

# Cache Affinity

CPU Affinity Pin with Cache Topology Awareness for Linux/POSIX x86-64 systems.

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

