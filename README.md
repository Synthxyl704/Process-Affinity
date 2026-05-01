# Cache + NUMA // Process Affinity Mapper
> Pin processes to CPU cache domains on x86-64 linux operating systems, aided with NUMA awareness.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/ed9071bf-bcbd-41fb-88bc-db138f564d8b" />

(You can view its working in here) 
> https://drive.google.com/file/d/17lApzbGUHCLqxyw1tTULDt3-Pb9FXLxL/view?usp=sharing

## Requirements
- Linux (ONLY)
- x86-64 (Intel/AMD)
- Python 3.10+
- Root (or `CAP_SYS_NICE`) to change affinity
- Taskset utility

> [!WARNING]
> You need permissions to set CPU affinity sometimes.
> On most systems, this means running as root or having `CAP_SYS_NICE`.

Run it directly (only way):
```bash
git clone https://github.com/Synthxyl704/Process-affinity-pinner
cd Process-affinity-pinner
python main.py -h

# python main.py <command> [options]
```
## Commands list
| Command | Description |
|---------|-------------|
| `show` | Display your system's cache topology |
| `pin` | Pin the process to a cache level or core |
| `unpin` | Reset the process affinity to all cores |
| `suggest` | Suggest optimal cores for a process along with manual review! |

### `show` - displays your system's cache topology
```bash
python main.py show
python main.py show --numa    # includes NUMA nodes
```
### `pin` - pin a process / PID to a cache level or core
```bash
python main.py pin --pid <PID> --level L2
python main.py pin --pid <PID> --core 7
```
> [!NOTE]
> Pinning your process or PID to `--level L1` or  simply `--level L1` - it will NOT work (despite the program saying otherwise). <br>
> Use `--level L1I` or `--level L1D` instead (some systems expose both, some only one). <br>
> If `--level L1` doesn't work and the affinity retains to 0-[--CPU_COUNT], try `--level L1D` instead or `--level L1I`.

### `unpin` - reset that process's affinity to all available cores
```bash
python main.py unpin --pid <PID>
```
### `suggest` — get good cache placement recommendations
```bash
python main.py suggest --pid <PID>
python main.py suggest --pid <PID> -v # kinda verbose logging 
```
**Verbose mode `[-v]` shows**:
- Split/Cross-domain warnings (when process spans multiple cache domains)
- And suggestions like: 
- `CONSOLIDATE` (cross-domain)
- `EXPAND` (process is subset in a domain)
- `OPTIMAL` (self-explanatory) placement

## How 2 actually use?
```bash
# step 1: find your target process
ps aux | grep "xX_69420_7T1AMAT_GAMER__Xx"

# step 2: check what cache topology you're working with
python main.py show

# step 3: now pin it to your desired cache, for example L2 cache
python main.py pin --pid 6767 --level L2

# step 4: check if the (cache) placement is optimal for that process
python main.py suggest --pid 6767 -v

# WARNING: step 4's dump might be a bit large
```

## Extra(s) - Project existence reason
CPU caches are not evenly shared on a computer. <br>
On most x86-64 machines, cores 0-3 share an L2, cores 4-7 share another, and so on (depends). <br> Or a process can be variably assigned to different cores as part of its cache domain by the task scheduler! <br>

Pinning a process to "all cores" means it jumps between cache domains, trashing the L3 every time is not something that one might want especially in benchmarking, etc. <br>
So this tool lets you pin a process to a single cache domain - so it stays in cache, and your NUMA node if you're on a multi-socket machine.
