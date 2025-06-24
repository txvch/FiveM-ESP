import pymem
import pymem.process
import pymem.exception
import struct
import math

def get_process_handle(process_name="FiveM_GTAProcess.exe"):
    try:
        pm = pymem.Pymem(process_name)
        return pm
    except pymem.exception.ProcessNotFound:
        print(f"[-] Process '{process_name}' not found. Is the game running?")
        return None

def get_module_info(pm, module_name="FiveM_GTAProcess.exe"):
    try:
        return pymem.process.module_from_name(pm.process_handle, module_name)
    except AttributeError:
        print(f"[-] Module '{module_name}' not found in the process.")
        return None

def game_ptr(pm, module_base, offsets):
    pointers = {}
    try:
        print(f"[reg_esp.py] reading world_ptr from: {hex(module_base + offsets['World'])}")
        world_ptr = pm.read_longlong(module_base + offsets['World'])
        print(f"[reg_esp.py] world_ptr: {hex(world_ptr) if world_ptr else world_ptr}")
        pointers['world_ptr'] = world_ptr
        localplayer = pm.read_longlong(world_ptr + 0x8)
        print(f"[reg_esp.py] localplayer: {hex(localplayer) if localplayer else localplayer}")
        pointers['localplayer'] = localplayer
        replay_ptr = pm.read_longlong(module_base + offsets['ReplayInterface'])
        print(f"[reg_esp.py] replay_ptr: {hex(replay_ptr) if replay_ptr else replay_ptr}")
        pointers['replay_ptr'] = replay_ptr
        ped_replay = pm.read_longlong(replay_ptr + 0x18)
        print(f"[reg_esp.py] ped_replay: {hex(ped_replay) if ped_replay else ped_replay}")
        pointers['ped_replay'] = ped_replay
        ped_list = pm.read_longlong(ped_replay + 0x100)
        print(f"[reg_esp.py] ped_list: {hex(ped_list) if ped_list else ped_list}")
        pointers['ped_list'] = ped_list
        entity_count = pm.read_int(ped_replay + 0x108)
        print(f"[reg_esp.py] entity_count: {entity_count}")
        pointers['entity_count'] = entity_count
    except Exception as e:
        print(f"[reg_esp.py] error in game_ptr: {e}")
        return None
    return pointers

def get_build_number(pm, module_base):
    try:
        build_addr = module_base + 0x218B1A0
        build = pm.read_int(build_addr)
        print(f"[reg_esp.py] detected build number: {build}")
        return build
    except Exception as e:
        print(f"[reg_esp.py] could not detect build number: {e}")
        return None 