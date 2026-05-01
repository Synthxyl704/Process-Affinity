import os as operatingSystem
import re as regex  
import subprocess
# import shlex
# import operator 

from typing import Dict, List, Optional, Final
from .topology import getCacheTopology, getCoresForCacheLevel

def buildProcessorMask(cores: List[int]) -> str:
    if (not cores or cores == False or not bool(cores)):
        return "0";

    mask: int = 0;
    for core in cores:
        if not isinstance(core, int) or core < 0:
            return "0";
        # shift 01 by core positions 
        # [0, 2, 3] 
        # 1 << [0] = {0001 -> 0001}
        # 1 << [2] = {0001 -> 0100} => [0001] |= 0100 = 0101
        # 1 << [3] = {0001 -> 1000} => [0101] |= 1101
        mask |= 1 << core;

    return hex(mask);

def convertBitmaskToCores(maskString: str) -> List[int]:
    BASE16_FORMAT: Final[int] = 16; # so you can define constants like this...
    maskString: str = maskString.strip();

    if maskString.startswith("0x"): 
        HEX2INT_mask: int = int(maskString, base=BASE16_FORMAT); 
    
    else:
        HEX2INT_mask: int = (int(maskString, BASE16_FORMAT)) if (maskString.startswith("0")) else int(maskString);

    coresList: List[int] = [];
    bitFlag: int = int(0, base=2);

    # [8/4/2/1]: 7 -> 0111 = 1 => TRUE
    # [8/4/2/1]: 4 -> 0100 = 0 => FALSE
    
    # [0, 2, 3] = [1101 (from before)] 
    # (1101 & 0001) => 
    # [{[1]101 & [0]001 = 0}, {1[1]01 & 0[0]01 = 0}, 
    #  {11[0]1 & 00[0]1} = 0, {110[1] & 000[1] = 1}] -> (bit = 0) = coreList.append(0)
    # 32_0 
    # 1101 -> [0, 2, 3] in this way of appending
    while HEX2INT_mask: # scan right -> left, pretty smart
        if (HEX2INT_mask & 1): 
            coresList.append(bitFlag);
        
        HEX2INT_mask >>= 1;
        bitFlag += 1;

    return coresList;

def getCurrentProcessAffinity(processID: int) -> Optional[List[int]]:
    try:
        # taskset -p -c 6767
        # retrieves cpu affinity of PID 6767
        TASKSET_result = subprocess.run(
            ["taskset", "-p", "-c", str(processID)],
            capture_output=True, text=True, timeout=5
        ); # subprocess.run returns CompletedProcess[str] to tasksetResult

        if (TASKSET_result.returncode != 0):
            return None;

        output: str = TASKSET_result.stdout.strip();

        # "current affinity masks: 0-3" or "current affinity list: 0,1" or "0-3,4,5"
        # also handles hex masks like "pid 123's current affinity mask: f0"
        match: str = regex.search(r"(?:masks|list|mask):\s*(.+)", output);

        if not match:
            return None;

        maskString = match.group(1).strip();

        cores: List[int] = [];
        
        # we check if it looks like a hex mask (contains a-f or A-F)
        # taskset usually outputs "list: 0,1,2" or "mask: ff"
        # If it contains letters, it's likely a hex mask,
        # though i dont think we will need this, god measure enough
        if any(c in maskString for c in 'abcdefABCDEF'):
            # parse it as hex (mask)
            try:
                maskValue = int(maskString, 16);
                bitIndex = 0;
                while maskValue > 0:
                    if maskValue & 1:
                        cores.append(bitIndex);
                    maskValue >>= 1;
                    bitIndex += 1;
            except ValueError:
                return None;
        else:
            # parse as comma-separated list/ranges
            for part in maskString.split(","):
                part = part.strip();

                if "-" in part:
                    parts = part.split("-");
                    try:
                        start = int(parts[0])
                        end = int(parts[1])
                        cores.extend(range(start, end + 1));
                    except ValueError:
                        return None
                
                else:
                    try:
                        cores.append(int(part, 10));
                    except ValueError:
                        return None

        return sorted(cores);

    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None;

def pinProcessToCacheLevel(processID: int, coresList: List[int]) -> bool:
    if not coresList:
        print(f"[ERROR]: no cores specified/pinned for PID {processID}");
        return False;

    mask: str = buildProcessorMask(coresList);

    try:
        TASKSET_result = subprocess.run(
            ["taskset", "-p", mask, str(processID)],
            capture_output=True, text=True, timeout=5
        );

        if TASKSET_result.returncode != 0:
            print(f"[SHELLCMD_ERROR]: taskset cmd failed: {TASKSET_result.stderr}")
            return False;

        print(f"[SUCCESS]: pinned PID {processID} to core(s) {coresList}");
        return True;

    except FileNotFoundError:
        print("[SHELLCMD_NOTFOUND_ERROR]: \"taskset\" not found. Plz install \"util-linux\" package.")
        return False;

    except Exception as SOME_OTHER_EXCEPTION:
        print(f"[PINNING_ERROR]: {SOME_OTHER_EXCEPTION}");
        return False;

def pinToCacheLevel(processID: int, cacheLevel: str) -> bool:
    cacheLevelKey: str = cacheLevel.upper();
    if cacheLevelKey == "L1":
        cacheLevelKey = "L1D";

    cacheTopology: Dict[str, Dict[int, List[int]]] = getCacheTopology();
    domains: Dict[int, List[int]] = cacheTopology.get(cacheLevelKey, {});
    if not domains:
        print(f"[CACHE_LEVEL_ERROR]: no cores found for cache level {cacheLevel}")
        return False;

    currentAffinity: List[int] = getCurrentProcessAffinity(processID);
    if currentAffinity is None:
        print(f"[CACHE_LEVEL_ERROR]: failed to retrieve affinity for process {processID}")
        return False;

    currentAffinitySet = set(currentAffinity);

    chosenDomainID: int = sorted(domains.keys())[0];
    bestOverlap: int = (-1);
    bestDomainSize: int = (10**9);

    for domainID, domainCores in domains.items():
        overlap = len(currentAffinitySet.intersection(domainCores));
        domainSize = len(domainCores);
        if (overlap > bestOverlap) or (overlap == bestOverlap and domainSize < bestDomainSize):
            chosenDomainID = domainID;
            bestOverlap = overlap;
            bestDomainSize = domainSize;

    chosenCores: List[int] = sorted(domains[chosenDomainID]);
    print(f"[INFO]: selected {cacheLevelKey} domain {chosenDomainID} -> cores {chosenCores}");
    return pinProcessToCacheLevel(processID, chosenCores);

def pinToCacheLevel(processID: int, cacheLevel: str) -> bool:
    cacheLevelKey: str = cacheLevel.upper();
    if cacheLevelKey == "L1":
        cacheLevelKey = "L1D";

    cacheTopology: Dict[str, Dict[int, List[int]]] = getCacheTopology();
    domains: Dict[int, List[int]] = cacheTopology.get(cacheLevelKey, {});
    if not domains:
        print(f"[CACHE_LEVEL_ERROR]: no cores found for cache level {cacheLevel}")
        return False;

    currentAffinity: List[int] = getCurrentProcessAffinity(processID);
    if currentAffinity is None:
        print(f"[CACHE_LEVEL_ERROR]: failed to retrieve affinity for process {processID}")
        return False;

    currentAffinitySet = set(currentAffinity);

    chosenDomainID: int = sorted(domains.keys())[0];
    bestOverlap: int = (-1);
    bestDomainSize: int = (10**9);

    for domainID, domainCores in domains.items():
        overlap = len(currentAffinitySet.intersection(domainCores));
        domainSize = len(domainCores);
        if (overlap > bestOverlap) or (overlap == bestOverlap and domainSize < bestDomainSize):
            chosenDomainID = domainID;
            bestOverlap = overlap;
            bestDomainSize = domainSize;

    chosenCores: List[int] = sorted(domains[chosenDomainID]);
    print(f"[INFO]: selected {cacheLevelKey} domain {chosenDomainID} -> cores {chosenCores}");
    return pinProcessToCacheLevel(processID, chosenCores);

def unpinProcessFromCacheLevel(processID: int) -> bool:
    try:
        # get number of CPUs for a sys
        CPU_COUNT: int = operatingSystem.sysconf(operatingSystem.sysconf_names["SC_NPROCESSORS_ONLN"])
    except:
        # CPU_COUNT: int = 12;  # fallback, but is this bad? edit: yes its bad
        CPU_COUNT: int = operatingSystem.cpu_count() or 1; 

    coreList: str = ",".join(str(inx) for inx in range(CPU_COUNT));

    try:
        resultOfSubprocess = subprocess.run(
            # -p = operate on a process, -c = specify CPUs as a list
            ["taskset", "-pc", coreList, str(processID)],
            capture_output=True, text=True, timeout=5
        );

        if resultOfSubprocess.returncode != 0:
            print(f"[ERROR]: taskset (utility) failed // error log: {resultOfSubprocess.stderr}")
            return False;

        print(f"[UNPIN_SUCCESS]: unpinned PID {processID}, (now open to ALL cores)")
        return True;

    except Exception as ERROR_IN_PROCESS_UNPINN:
        print(f"[UNPIN_ERROR]: {ERROR_IN_PROCESS_UNPINN}");
        return False;

def suggestOptimization(processID: int) -> Optional[dict]:
    currentCoresForProcess = getCurrentProcessAffinity(processID);

    if currentCoresForProcess is None:
        return None; 
        # if affinity cannot be retrieved
        # there is something going on
        # we better fuck off

    currentSet: set = set(currentCoresForProcess);
    cacheTopology: Dict[str, Dict[int, List[int]]] = getCacheTopology(); # EXG: {"L2": {0: [0,420], 1: [2,1337]}}
    suggestions: List[dict] = [];
    domainsSeen: set = set();  # deduplicate by (level, frozenset(cores))

    # we detect cross-domain differences/splits at each cache level
    splitWarnings: List[dict] = [];

    for cacheLevelKey, sharedGroupOfCPUs_DOMAIN in cacheTopology.items():
        # process's current cores = [0,2]
        # domains:
        # #0 [0,1] -> overlap 
        # #1 [2,3] -> overlap 
        # #2 [4,5] -> there is no overlap, so not this
        # return domains [#0,#1]

        domainsContainingAny: List[int] = [ # build list of cache domains that overlap with current process
            (domainID) for (domainID, domainCores) in (sharedGroupOfCPUs_DOMAIN.items())
            if (currentSet & set(domainCores))
        ];

        # if the process spans more than one cache domain (which is bad), at this cache level, we flag it
        isSplit: bool = len(domainsContainingAny) > 1;
        
        if isSplit:
            splitWarnings.append({
                "level": cacheLevelKey,
                "spannedDomains": domainsContainingAny,
                "type": "split_warning",
                "priority": 0, # highest urgency
                "reason": "process affinity crosses cache domain boundaries which introduces severe cache thrash risk!",
            });
        
        # cache thrashing is the CPU cache which frequents invalidation and refilling
        # so the data in there doesnt remain for long

        # Pre-calculate best consolidation target for this level if split
        bestConsolidationDomainID: Optional[int] = None;
        bestConsolidationOverlap: int = -1;
        bestConsolidationSize: int = 10**9;

        if isSplit:
            for dID, dCores in sharedGroupOfCPUs_DOMAIN.items():
                dSet = set(dCores);
                dOverlap = len(currentSet & dSet);
                dSize = len(dCores);
                
                if dOverlap == 0:
                    continue;

                isBetter = False;
                if dOverlap > bestConsolidationOverlap:
                    isBetter = True;
                elif dOverlap == bestConsolidationOverlap:
                    if dSize < bestConsolidationSize:
                        isBetter = True;
                    elif dSize == bestConsolidationSize:
                        if dID < bestConsolidationDomainID:
                            isBetter = True;
                
                if isBetter:
                    bestConsolidationDomainID = dID;
                    bestConsolidationOverlap = dOverlap;
                    bestConsolidationSize = dSize;

        for domainID, domainCores in sharedGroupOfCPUs_DOMAIN.items():
            domainSet: set = set(domainCores);
            uniqueDomainKey: tuple = (cacheLevelKey, frozenset(domainSet));

            # "L2": {
            #     0: [0,67],
            #     1: [0,67], # duplicate domain (so conv to uniqueCoresKey) (same CPUs)
            #     2: [4,20]
            # }

            if uniqueDomainKey in domainsSeen:
                continue;
            
            domainsSeen.add(uniqueDomainKey);
            overlap: set = currentSet & domainSet;
            overlapCount: int = len(overlap);

            if (not overlap):
                continue;  # ignore a completely unrelated cache domain 

            if (currentSet == domainSet):
                # this signals perfect alignment - process exactly fills one cache domain
                suggestions.append({
                    "level": cacheLevelKey,
                    "cores": domainCores,
                    "type": "optimal",
                    "priority": 1,
                    "reason": "process is perfectly aligned to a single cache-sharing domain!",
                });

            elif currentSet.issubset(domainSet):
                # The process fits inside a single cache domain.
                # This is a healthy/neutral state. Emit a signal so consumers know analysis happened.
                suggestions.append({
                    "level": cacheLevelKey,
                    "cores": domainCores,
                    "type": "contained",
                    "priority": 2,
                    "reason": f"process is contained within a single cache domain ({overlapCount}/{len(domainCores)} cores used). No action needed.",
                });

            elif isSplit and domainID == bestConsolidationDomainID:
                # Process is split, and this is the best domain to consolidate to.
                # This covers both 'domainSet.issubset(currentSet)' and partial overlaps.
                suggestions.append({
                    "level": cacheLevelKey,
                    "cores": domainCores,
                    "type": "consolidate",
                    "priority": 3,
                    "overlapCount": overlapCount,
                    "totalProcessCores": len(currentSet),
                    "reason": f"Consolidate to this domain to reduce cross-domain traffic. It holds {overlapCount}/{len(currentSet)} of your process cores (best available target).",
                });

            else:
                # Partial overlap but not the best target, or other non-actionable states.
                pass;

    suggestions.sort(key=lambda s: s["priority"]);

    return {
        "processID": processID,
        "current": currentCoresForProcess,
        "splitWarnings": splitWarnings,
        "suggestions": suggestions,
    };
