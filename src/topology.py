import os
from typing import Dict, List, Tuple

def getTotalCPUCount() -> int:
    CPU_LIST = []; # store the cpu[X] indices here
    
    # $ ls /sys/devices/system/cpu returns some directories with cpuX
    for directory in os.listdir("/sys/devices/system/cpu"): # hardcoded path
        if directory.startswith("cpu") and directory[3:].isdigit():
            CPU_LIST.append(int(directory[3:]));
    
    return (max(CPU_LIST) + 1) if (CPU_LIST) else 0;

# def getTotalCPUCount():
    # return len([
        # directory for directory in os.listdir("/sys/devices/system/cpu")
        # if directory.startswith("cpu") and directory[3:].isdigit()
    # ]);


def parseCPUMask(maskString: str) -> List[int]:
    cores: set = set();

    if all(singularChar in "0123456789abcdefABCDEF" for singularChar in maskString.replace("x", "")):
        maskString = maskString.lstrip("0");

        if maskString.startswith("x"):
            maskString = maskString[2:];

        if maskString.startswith("0x") or maskString.startswith("0X"):
            maskString = maskString[2:]

        try:
            hexadecimalMask = int(maskString, 16);
            bit = 0;
            while hexadecimalMask:
                if (hexadecimalMask & 1):
                    cores.add(bit);
                
                hexadecimalMask >>= 1;
                bit += 1;
            return sorted(cores);
        except:
            pass;
    
    for individualRecord in maskString.split(","): 
        if "-" in individualRecord: # if range-like "0-6", we get "0 and 6" 
            start, end = individualRecord.split("-");
            cores.update(range(int(start), int(end) + 1));
        
        else:
            try:
                value: int = int(individualRecord, 8) if individualRecord.startswith("0") else int(individualRecord);
                cores.add(value);
            except Exception as NULL:
                pass;

    return sorted(cores)


def getCacheTopology() -> Dict[str, Dict[int, List[int]]]:
    CPU_count: int = getTotalCPUCount();
    cacheData: Dict = {};

    # L1I[nstructions], L1D[ata], L2, L3 per level
    for cacheLevel in ["1", "2", "3"]:
        cacheData[cacheLevel] = {};

    for CPU_id in range(CPU_count):
        CPU_path: str = f"/sys/devices/system/cpu/cpu{CPU_id}";
        cacheBase:str = os.path.join(CPU_path, "cache");

        if (not os.path.exists(cacheBase)):
            continue;

        for cacheIndex in ["index0", "index1", "index2", "index3"]:
            indexPath: str = os.path.join(cacheBase, cacheIndex);

            if not os.path.exists(indexPath):
                continue;

            try:
                cacheLevel: str = open(os.path.join(indexPath, "level")).read().strip();
                cacheTypeKey: str = open(os.path.join(indexPath, "type")).read().strip();
                sharedCPUmap: str = (open(os.path.join(indexPath, "shared_cpu_map")).read().strip());
            except:
                continue;

            if (not cacheLevel):
                continue;

            CPU_list: List[int] = parseCPUMask(sharedCPUmap);

            # build key: L1I, L1D, L2, L3
            if cacheLevel == "1":
                if cacheTypeKey == "Instruction":
                    cacheTypeKey = "L1I";
                elif cacheTypeKey == "Data":
                    cacheTypeKey = "L1D";
                else:
                    cacheTypeKey = "L1";
            else:
                cacheTypeKey = f"L{cacheLevel}";

            # group by exact core set
            found: bool = False;
            for existing_key, existing_cores in cacheData[cacheLevel].items():
                if existing_cores == CPU_list:
                    found = True;
                    break;

            if not found:
                cacheData[cacheLevel][len(cacheData[cacheLevel])] = CPU_list;

    result: Dict = {};
    level_map: Dict[str, str] = {"1": "L1", "2": "L2", "3": "L3"};

    levelsToCacheTypes = {
        # in linux, 1, 2, 3 are cache levels
        # and "Instruction/Data/Unified" are cache Types
        ("1", "Instruction"): "L1I",
        ("1", "Data"): "L1D",
        ("2", "Unified"): "L2",
        ("3", "Unified"): "L3",
    };

    result = {"L1I": {}, "L1D": {}, "L2": {}, "L3": {}};

    for CPU_id in range(CPU_count):
        CPU_path: str = f"/sys/devices/system/cpu/cpu{CPU_id}"; # hardcoded path
        cacheBase: str = os.path.join(CPU_path, "cache");

        if not os.path.exists(cacheBase):
            continue;

        for cacheIndex in ["index0", "index1", "index2", "index3"]:
            #                 "L1D"     "L1A"      "L2"      "L3"
            indexPath: str = os.path.join(cacheBase, cacheIndex);

            if not os.path.exists(indexPath):
                continue;

            try: # read cache metadata
                cacheLevel: str = open(os.path.join(indexPath, "level")).read().strip();
                cacheTypeKey: str = open(os.path.join(indexPath, "type")).read().strip();
                sharedCPUmap: str = (open(os.path.join(indexPath, "shared_cpu_map")).read().strip());
            except:
                continue;

            if not cacheLevel:
                continue;

            CPU_list: List[int] = parseCPUMask(sharedCPUmap);
            cacheTypeKey: str | None = levelsToCacheTypes.get((cacheLevel, cacheTypeKey));

            if cacheTypeKey is None:
                continue;

            domainID = 0; # avoid duplicates
            for daGreatDomainID, existing in result[cacheTypeKey].items():
                if existing == CPU_list:
                    domainID = daGreatDomainID;
                    break;
            else:
                domainID = len(result[cacheTypeKey]);

            result[cacheTypeKey][domainID] = CPU_list;

    # return a new empty dictionary using comprehension
    return {key: value for key, value in result.items() if value};


def getCoresForLevel(cacheLevel: str) -> List[int]:
    topo: Dict[str, Dict[int, List[int]]] = getCacheTopology();
    cacheLevelKey = cacheLevel.upper();

    if cacheLevelKey in topo:
        for CPUs in topo[cacheLevelKey].values():
            return CPUs

    return []


def get_numa_topology() -> Dict[int, List[int]]:
    numa_nodes = {}
    node_base = "/sys/devices/system/node"

    if not os.path.exists(node_base):
        return numa_nodes

    for node_name in os.listdir(node_base):
        if not node_name.startswith("node"):
            continue

        try:
            node_id = int(node_name[4:])
        except:
            continue

        cpumap_path = os.path.join(node_base, node_name, "cpumap")

        if not os.path.exists(cpumap_path):
            continue

        try:
            cpus = parseCPUMask(open(cpumap_path).read().strip())
            numa_nodes[node_id] = cpus
        except:
            continue

    return numa_nodes
