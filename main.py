#!/usr/bin/env python3
import argparse
import sys
from src.topology import getCacheTopology, getCoresForLevel, get_numa_topology
from src.pinner import (
    pin_to_cache_level,
    getCurrentProcessAffinity,
    suggest_optimization,
    unpin_process,
)


def cmdShow(args):
    topo = getCacheTopology()
    print("=== Cache Topology ===")
    for levelKey in ["L1", "L2", "L3"]:
        if levelKey in topo:
            print(f"\n{levelKey}:")
            for domainId, cpus in topo[levelKey].items():
                print(f"  Domain {domainId}: cores {cpus}")

    if args.numa:
        numa = get_numa_topology()
        print("\n=== NUMA Topology ===")
        for nodeId, cpus in sorted(numa.items()):
            print(f"  Node {nodeId}: cores {cpus}")


def cmdPin(args):
    if not args.pid:
        print("Error: --pid is required")
        sys.exit(1)

    if args.level:
        success = pin_to_cache_level(args.pid, args.level)
        sys.exit(0 if success else 1)

    if args.core:
        from src.pinner import pinProcess

        success = pinProcess(args.pid, [args.core])
        sys.exit(0 if success else 1)

    print("Error: specify --level or --core")
    sys.exit(1)


def cmdSuggest(args):
    if not args.pid:
        print("Error: --pid is required")
        sys.exit(1)

    current = getCurrentProcessAffinity(args.pid)
    if current is None:
        print(f"Error: could not get affinity for PID {args.pid}")
        sys.exit(1)

    print(f"Current affinity: cores {current}")
    if args.verbose:
        result = suggest_optimization(args.pid)
        if result:
            print(f"\nSuggestions:")
            for sugg in result["suggestions"]:
                status = "optimal" if sugg["optimal"] else "suboptimal"
                print(f"  {sugg['level']}: {sugg['cores']} ({status})")


def main():
    parser = argparse.ArgumentParser(
        description="CPU Affinity Pin with Cache Topology Awareness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py show                    # Show cache topology
  python cli.py show --numa            # Show cache + NUMA topology
  python cli.py pin 12345 --level L2   # Pin PID to L2 cache domain
  python cli.py pin 12345 --core 7    # Pin PID to specific core
  python cli.py unpin 12345          # Unpin (use all cores)
  python cli.py suggest 12345         # Suggest optimal cores
  python cli.py suggest 12345 -v       # Verbose suggestions
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    showParser = subparsers.add_parser("show", help="Show cache topology")
    showParser.add_argument("--numa", action="store_true", help="include NUMA topology")
    pinParser = subparsers.add_parser("pin", help="pin process to cache level or core")
    pinParser.add_argument("--pid", type=int, required=True, help="process ID")
    pinParser.add_argument("--level", help="cache level (L1, L2, L3)")
    pinParser.add_argument("--core", type=int, help="specific core")
    suggestParser = subparsers.add_parser("suggest", help="suggest optimal cores")
    suggestParser.add_argument("--pid", type=int, required=True, help="process ID")
    suggestParser.add_argument(
        "-v", "--verbose", action="store_true", help="verbose output"
    )
    unpinParser = subparsers.add_parser(
        "unpin", help="unpin process (reset to all cores)"
    )
    unpinParser.add_argument("--pid", type=int, required=True, help="process ID")
    parsedArgs = parser.parse_args()
    if parsedArgs.command == "show":
        cmdShow(parsedArgs)
    elif parsedArgs.command == "pin":
        cmdPin(parsedArgs)
    elif parsedArgs.command == "suggest":
        cmdSuggest(parsedArgs)
    elif parsedArgs.command == "unpin":
        success = unpin_process(parsedArgs.pid)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
