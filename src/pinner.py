import os
import re
import subprocess
import shlex
# import operator 

from typing import List, Optional, Final
from .topology import getCacheTopology, getCoresForLevel

def buildProcessorMask(cores: List[int]) -> str:
    if (not cores or cores == False or not bool(cores)):
        return "0/Zero";

    mask: int = 0;
    for core in cores:
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

    coresList: List = [];
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
        match: str = re.search(r"(?:masks|list):\s*(.+)", output);

        if not match:
            return None;

        maskString = match.group(1).strip();

        cores: List = [];
        for part in maskString.split(","):
            part = part.strip();

            if "-" in part:
                parts = part.split("-");
                cores.extend(range(int(parts[0]), int(parts[1]) + 1));
            
            else:
                cores.append(int(part, 10));

        return sorted(cores);

    except Exception as ERROR_IN_AFFINITY_RETRIEVAL:
        return None;

def pinProcess(processID: int, coresList: List[int]) -> bool:
    if not coresList:
        print(f"[ERROR]: no cores specified/pinned for PID {processID}");
        return False;

    mask:str = buildProcessorMask(coresList);

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

def pin_to_cache_level(pid: int, level: str) -> bool:
    cores: List[int] = getCoresForLevel(level);

    if (not cores):
        print(f"Error: no cores found for cache level {level}")
        return False

    return pinProcess(pid, cores)


def unpin_process(pid: int) -> bool:
    try:
        # Get number of CPUs
        cpu_count = os.sysconf(os.sysconf_names["SC_NPROCESSORS_ONLN"])
    except:
        cpu_count = 12  # fallback

    core_list = ",".join(str(i) for i in range(cpu_count))

    try:
        result = subprocess.run(
            ["taskset", "-pc", core_list, str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            print(f"Error: taskset failed: {result.stderr}")
            return False

        print(f"Unpinned PID {pid} (now using all cores)")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def suggest_optimization(pid: int) -> Optional[dict]:
    current_cores = getCurrentProcessAffinity(pid)

    if current_cores is None:
        return None

    topo = getCacheTopology()
    suggestions = []

    for level_key, domains in topo.items():
        for domain_id, domain_cores in domains.items():
            if set(current_cores) == set(domain_cores):
                suggestions.append(
                    {"level": level_key, "cores": domain_cores, "optimal": True}
                )
            elif not set(current_cores).issubset(set(domain_cores)):
                suggestions.append(
                    {"level": level_key, "cores": domain_cores, "optimal": False}
                )

    return {"current": current_cores, "suggestions": suggestions}
