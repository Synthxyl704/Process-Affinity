#!/usr/bin/env python3
import argparse
import sys
import json
from typing import Dict, List
from src.topology import getCacheTopology, getCoresForCacheLevel, getNumaTopology;
from src.pinner import (
    pinToCacheLevel,
    getCurrentProcessAffinity,
    suggestOptimization,
    unpinProcessFromCacheLevel,
);

_RESET = "\033[0m";
_BOLD = "\033[1m";
_DIM = "\033[2m";
_MAGENTA = "\033[35m";
_CYAN = "\033[36m";
_GREEN = "\033[32m";
_YELLOW = "\033[33m";
_RED = "\033[31m";
_BLUE = "\033[34m";

def _tree(label: str, children: List[tuple], prefix: str = ""):
    print(f"{prefix}{label}");
    for i, (text, subs) in enumerate(children):
        is_last_child = i == len(children) - 1;
        connector = "└──" if is_last_child else "├──";
        trunk = "   " if is_last_child else "│  ";
        print(f"{prefix}{connector} {text}");
        for j, sub in enumerate(subs):
            is_last_sub = j == len(subs) - 1;
            sub_connector = "└" if is_last_sub else "├";
            print(
                f"{prefix}{trunk}{_DIM}│{_RESET}  {_DIM}{sub_connector}{_RESET} {sub}"
            );
def showUserTheirTopologies(args):
    cacheTopology: Dict[str, Dict[int, List[int]]] = getCacheTopology();
    if args.json:
        result: Dict[str, object] = {
            "cache_topology": cacheTopology,
            "numa_topology": getNumaTopology() if args.numa else {},
        };
        print(json.dumps(result, indent=2));
        return;
    levels = [k for k in ["L1", "L2", "L3"] if k in cacheTopology];
    children: List[tuple] = [];
    for cacheLevelKey in levels:
        domains = list(cacheTopology[cacheLevelKey].items());
        subs = [
            f"domain {domainId}  {_DIM}->{_RESET}  {_CYAN}cores{_RESET} {CPUs}"
            for domainId, CPUs in domains
        ];
        children.append((f"{_BOLD}{_MAGENTA}{cacheLevelKey}{_RESET}", subs));
    print();
    _tree(f"{_BOLD}{_CYAN}┌── [CACHE] topology{_RESET}", children);
    print();
    if args.numa:
        NUMA_TOPOLOGY: Dict[int, List[int]] = getNumaTopology();
        numa_children: List[tuple] = [
            (
                f"node {nodeId}  {_DIM}->{_RESET}  {_CYAN}cores{_RESET} {CPUs}",
                [],
            )
            for nodeId, CPUs in sorted(NUMA_TOPOLOGY.items())
        ];
        _tree(f"{_BOLD}{_CYAN}┌── [NUMA] topology{_RESET}", numa_children);
        print();
def commandPin(args):
    if not args.pid:
        print(f"\n┌── {_RED}[ERROR]{_RESET}");
        print(f"└── --pid (process ID) is required\n");
        sys.exit(1);
    if args.level:
        processSuccessStatus: bool = pinToCacheLevel(args.pid, args.level);
        if processSuccessStatus == 0 or processSuccessStatus:
            print(f"\n┌── {_GREEN}[PINNED]{_RESET}");
            print(f"├── pid    {args.pid}");
            print(f"└── level  {_CYAN}{args.level}{_RESET}\n");
        sys.exit(0 if (processSuccessStatus == 0 or processSuccessStatus) else 1);
    if args.core:
        from src.pinner import pinToCacheLevel;
        processSuccessStatus: bool = pinToCacheLevel(args.pid, [args.core]);
        if processSuccessStatus == 0 or processSuccessStatus:
            print(f"\n┌── {_GREEN}[PINNED]{_RESET}");
            print(f"├── pid   {args.pid}");
            print(f"└── core  {_CYAN}{args.core}{_RESET}\n");
        sys.exit(0 if (processSuccessStatus == 0 or processSuccessStatus) else 1);
    print(f"\n┌── {_RED}error{_RESET}");
    print(f"└── specify --level or --core\n");
    sys.exit(1);
def commandSuggest(args):
    if not args.pid:
        print(f"\n┌── {_RED}[ERROR]{_RESET}");
        print(f"└── --pid (process ID) is required\n");
        sys.exit(1);
    currentAffinityCores: List[int] = getCurrentProcessAffinity(args.pid);
    if currentAffinityCores is None:
        print(f"\n┌── {_RED}[ERROR]{_RESET}");
        print(f"└── could not read affinity for PID {args.pid}\n");
        sys.exit(1);
    if args.json:
        result: Dict[str, object] = {"pid": args.pid, "cores": currentAffinityCores};
        if args.verbose:
            optimizationResult: Dict | None = suggestOptimization(args.pid);
            if optimizationResult:
                result.update(optimizationResult);
        print(json.dumps(result, indent=2));
        return;
    print(f"\n┌── {_CYAN}pid {args.pid}{_RESET}");
    print(f"└── cores  {_GREEN}{currentAffinityCores}{_RESET}");
    if args.verbose:
        result: Dict | None = suggestOptimization(args.pid);
        if result:
            items: List[tuple] = [];
            if result.get("splitWarnings"):
                for warn in result["splitWarnings"]:
                    subs = [
                        f"domains  {warn['spannedDomains']}",
                        f"{_DIM}{warn['reason']}{_RESET}",
                    ];
                    items.append((f"{_YELLOW}warning{_RESET}  {warn['level']}", subs));
            for s in result["suggestions"]:
                tag = {
                    "optimal": f"{_GREEN}OPTIMAL{_RESET} ",
                    "expand": f"{_CYAN}EXPAND{_RESET}  ",
                    "consolidate": f"{_MAGENTA}NARROW{_RESET}  ",
                    "partial_overlap": f"{_YELLOW}PARTIAL{_RESET} ",
                }.get(s["type"], s["type"].ljust(8));
                subs = [
                    f"cores  {s['cores']}",
                    f"{_DIM}{s['reason']}{_RESET}",
                ];
                items.append((f"{tag} {s['level']}", subs));
            print();
            _tree(f"┌── {_BOLD}[SUGGESTIONS + VIEW]{_RESET}", items);
    print();
def main():
    parser = argparse.ArgumentParser(
        description="CPU affinity pinning of processes/PIDs with cool cache topology awareness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="%(prog)s <command> [options]",
        epilog="""
┌── [COMMANDS]:
├── show     display cache topology
├── pin      pin process to cache level or core
├── suggest  suggest optimal cores for a process
└── unpin    unpin process (reset to all cores)
┌── [EXAMPLES]:
├── python main.py show
├── python main.py show --json
├── python main.py show --numa
├── python main.py show --numa --json
├── python main.py pin --pid 67 --level L2 
├── ^^^ (NOTE, pinning PID to L1 or  simply "--level L1" will NOT work (despite the program saying otherwise), use "--level L1I" or "--level L1D" instead!)
├── python main.py pin --pid 67 --core 7
├── python main.py unpin --pid 67
├── python main.py suggest --pid 67
└── python main.py suggest --pid 67 -v
        """,
    );
    subparsers = parser.add_subparsers(dest="command", required=True);
    showParser = subparsers.add_parser("show", help="show cache topology");
    showParser.add_argument("--numa", action="store_true", help="include NUMA topology");
    showParser.add_argument("--json", action="store_true", help="JSON output");
    pinParser = subparsers.add_parser("pin", help="pin process to cache level or core");
    pinParser.add_argument("--pid", type=int, required=True, help="process ID");
    pinParser.add_argument("--level", help="cache level (L1, L2, L3)");
    pinParser.add_argument("--core", type=int, help="specific core");
    suggestParser = subparsers.add_parser("suggest", help="suggest optimal cores");
    suggestParser.add_argument("--pid", type=int, required=True, help="process ID");
    suggestParser.add_argument(
        "-v", "--verbose", action="store_true", help="verbose output"
    );
    suggestParser.add_argument("--json", action="store_true", help="JSON output");
    unpinParser = subparsers.add_parser(
        "unpin", help="unpin process (reset to all cores)"
    );
    unpinParser.add_argument("--pid", type=int, required=True, help="process ID");
    parsedArgs = parser.parse_args();
    if parsedArgs.command == "show":
        showUserTheirTopologies(parsedArgs);
    elif parsedArgs.command == "pin":
        commandPin(parsedArgs);
    elif parsedArgs.command == "suggest":
        commandSuggest(parsedArgs);
    elif parsedArgs.command == "unpin":
        success = unpinProcessFromCacheLevel(parsedArgs.pid);
        if success:
            print(f"\n┌── {_GREEN}[UNPINNED]{_RESET}");
            print(f"├── pid   {parsedArgs.pid}");
            print(f"└── cores {_CYAN}all{_RESET}\n");
        sys.exit(0 if success else 1);
if __name__ == "__main__":
    main();
