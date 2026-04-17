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

    return sorted(cores);

def getCacheTopology() -> Dict[str, Dict[int, List[int]]]: 
    # ^^^ build a map of user's CPU cache architecture by reading (linux) sys files
    CPU_count: int = getTotalCPUCount();
    cacheData: Dict = {}; # type[Dict] = {};

    # L1I[nstructions], L1D[ata], L2, L3 per level
    for cacheLevel in ["1", "2", "3"]:
        cacheData[cacheLevel] = {};

    for CPU_id in range(CPU_count):
        # construct a file path string for the current CPU ID 
        # and then join it with cache (Str) to create a cacheBase path
        # if that path does not exist, we skip promptly

        # os.path.join(path, *paths)
        # paths = ["devices", "system", "cpu"]
        # os.path.join("/sys", *paths)
        CPU_path: str = f"/sys/devices/system/cpu/cpu{CPU_id}";
        cacheBase:str = os.path.join(CPU_path, "cache");
        
        if (not os.path.exists(cacheBase)):
            continue;
        
        for cacheIndex in ["index0", "index1", "index2", "index3"]:
            indexPath: str = os.path.join(cacheBase, cacheIndex);
            # /sys/.../cpu2/cache/index[0]

            if not os.path.exists(indexPath):
                continue;

            try: # extract cache metadata
                cacheLevel: str = open(os.path.join(indexPath, "level")).read().strip(); # 1, 2, 3 
                cacheTypeKey: str = open(os.path.join(indexPath, "type")).read().strip();# Instruction (L1I), Data (L1D), Unified
                sharedCPUmap: str = (open(os.path.join(indexPath, "shared_cpu_map")).read().strip()); # bitmask of cpus sharing this cache
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
            # cacheData[cacheLevel="2"] = {
                # 0: [0,1],
                # 1: [2,3]...
            # }
                if existing_cores == CPU_list:
                    found = True;
                    break;

            if not found:
                cacheData[cacheLevel][len(cacheData[cacheLevel])] = CPU_list; # add new shared cache CPU(s) 
                                                                              # using intance such as 2: [4, 5]

    mapOfCacheTopologyRESULT: Dict = {};
    cacheLevelMap: Dict[str, str] = {"1": "L1", "2": "L2", "3": "L3"};

    levelsToCacheTypes = {
        # in linux, 1, 2, 3 are cache levels
        # and "Instruction/Data/Unified" are cache Types
        ("1", "Instruction"): "L1I",
        ("1", "Data"): "L1D",
        ("2", "Unified"): "L2",
        ("3", "Unified"): "L3",
    };

    mapOfCacheTopologyRESULT = {"L1I": {}, "L1D": {}, "L2": {}, "L3": {}};

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

            CPU_list: List[int] = parseCPUMask(sharedCPUmap); # CPUs that share this cache instance
            cacheTypeKey: str | None = levelsToCacheTypes.get((cacheLevel, cacheTypeKey));

            if cacheTypeKey is None:
                continue;

            domainID = 0; # domain = shared group of CPUs using a cache instance // we will avoid duplicates
            for daGreatDomainIDwhichIsAKey, existing in mapOfCacheTopologyRESULT[cacheTypeKey].items():
                if existing == CPU_list:
                    domainID = daGreatDomainIDwhichIsAKey;
                    break;
            else:
                domainID = len(mapOfCacheTopologyRESULT[cacheTypeKey]);
            # result = { # EXG
            #     "L1I": {
            #         0: [0],
            #         1: [1],
            #         2: [2],
            #         3: [3]
            #     },
            #     "L1D": {
            #         0: [0],
            #         1: [1],
            #     },
            #     "L2": {
            #         0: [0, 1],
            #         1: [2, 3]
            #     },
            #     "L3": {
            #         0: [0, 1, 2, 3]
            #     }
            # }
            mapOfCacheTopologyRESULT[cacheTypeKey][domainID] = CPU_list;

    # return a new that only includes cache types that actually have data, some cache is unused, we dont want those
    return {key: value for key, value in mapOfCacheTopologyRESULT.items() if value};

def getCoresForCacheLevel(cacheLevel: str) -> List[int]:
    # cacheTopo = {
    #     "L1I": {0: [0], 1: [1]},
    #     "L2":  {0: [0,67], 1: [69,3]},
    #     "L3":  {0: [0,1,67,3]}
    # }
    cacheTopology: Dict[str, Dict[int, List[int]]] = getCacheTopology();
    cacheLevelKey = cacheLevel.upper();

    if (cacheLevelKey in cacheTopology):
        for CPUs in cacheTopology[cacheLevelKey].values(): # {0: [0,67], 1: [420,3]} -> eturn {[0,67], [420,3]}
            return CPUs;

    # fallback and return no CPUs in case
    return [];

def getNumaTopology() -> Dict[int, List[int]]:
    # a machine might be NUMA aware or !NUMA aware
    # we must handle both

    NUMA_nodes: Dict = {}; 
    nodeBase: str = "/sys/devices/system/node"; # hardcoded path

    if not os.path.exists(nodeBase):
        return NUMA_nodes;

    for nodeName in os.listdir(nodeBase):
        if not nodeName.startswith("node"): # if !NUMA aware 
            continue;

        try:
            nodeID = int(nodeName[4:]); # node[X]
        except:
            continue;

        cpuMap_Path = os.path.join(nodeBase, nodeName, "cpumap")

        if not os.path.exists(cpuMap_Path):
            continue;

        try:
            CPUs = parseCPUMask(open(cpuMap_Path).read().strip());
            NUMA_nodes[nodeID] = CPUs;
        except:
            continue;

    return NUMA_nodes;
