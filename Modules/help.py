import pymem
import pymem.process
import pymem.exception
import struct
import math
import pygame
import numpy as np

def get_process_handle(process_name="FiveM_GTAProcess.exe"):
    try:
        pm = pymem.Pymem(process_name)
        return pm
    except pymem.exception.ProcessNotFound:
        return None

def get_module_info(pm, module_name="FiveM_GTAProcess.exe"):
    try:
        return pymem.process.module_from_name(pm.process_handle, module_name)
    except AttributeError:
        return None

def game_ptr(pm, module_base, offsets):
    pointers = {}
    try:
        world_ptr = pm.read_longlong(module_base + offsets['World'])
        pointers['world_ptr'] = world_ptr
        localplayer = pm.read_longlong(world_ptr + 0x8)
        pointers['localplayer'] = localplayer
        replay_ptr = pm.read_longlong(module_base + offsets['ReplayInterface'])
        pointers['replay_ptr'] = replay_ptr
        ped_replay = pm.read_longlong(replay_ptr + 0x18)
        pointers['ped_replay'] = ped_replay
        ped_list = pm.read_longlong(ped_replay + 0x100)
        pointers['ped_list'] = ped_list
        entity_count = pm.read_int(ped_replay + 0x108)
        pointers['entity_count'] = entity_count
    except Exception as e:
        return None
    return pointers

def get_build_number(pm, module_base):
    try:
        build_addr = module_base + 0x218B1A0
        build = pm.read_int(build_addr)
        return build
    except Exception as e:
        return None

def draw_entity(screen, screen_pos, box_w, box_h, distance):
    rect = pygame.Rect(screen_pos[0] - box_w//2, screen_pos[1] - box_h//2, box_w, box_h)
    pygame.draw.rect(screen, (0, 255, 0), rect, 2)
    mark_x = screen_pos[0]
    mark_y = screen_pos[1] - box_h // 2
    pygame.draw.circle(screen, (255, 255, 0), (mark_x, mark_y), 5)
    font = pygame.font.Font(None, 24)
    distance_text = f"{distance:.1f}m"
    text_surface = font.render(distance_text, True, (255, 255, 255))
    text_rect = text_surface.get_rect(center=(mark_x, mark_y - 15))
    screen.blit(text_surface, text_rect)

def draw_entity_with_health(screen, screen_pos, box_w, box_h, distance, health):
    rect = pygame.Rect(screen_pos[0] - box_w//2, screen_pos[1] - box_h//2, box_w, box_h)
    pygame.draw.rect(screen, (0, 255, 0), rect, 2)
    bar_x = rect.left - 8
    bar_y = rect.top
    bar_w = 6
    bar_h = box_h
    health = max(0, min(health, 100))
    health_ratio = health / 100.0
    filled_h = int(bar_h * health_ratio)
    if health >= 50:
        t = (100 - health) / 50 
        r = int(0 + t * (255 - 0))
        g = int(255 - t * (255 - 165))
        b = 0
    else:
        t = (50 - health) / 50
        r = 255
        g = int(165 - t * 165)
        b = 0
    bar_color = (r, g, b)
    pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h))
    pygame.draw.rect(screen, bar_color, (bar_x, bar_y + (bar_h - filled_h), bar_w, filled_h))
    pygame.draw.rect(screen, (0, 0, 0), (bar_x, bar_y, bar_w, bar_h), 1)
    mark_x = screen_pos[0]
    mark_y = screen_pos[1] - box_h // 2
    pygame.draw.circle(screen, (255, 255, 0), (mark_x, mark_y), 5)
    font = pygame.font.Font(None, 24)
    distance_text = f"{distance:.1f}m"
    text_surface = font.render(distance_text, True, (255, 255, 255))
    text_rect = text_surface.get_rect(center=(mark_x, mark_y - 15))
    screen.blit(text_surface, text_rect)

def read_matrix(pm, address):
    data = pm.read_bytes(address, 64)
    return np.array(struct.unpack('16f', data), dtype=np.float32).reshape((4, 4))

def get_bone_index(pm, crSkeletonData_ptr, bone_id):
    m_Used = pm.read_uint(int(crSkeletonData_ptr) + 0x1A)
    m_NumBones = int(pm.read_uint(int(crSkeletonData_ptr) + 0x5E))
    if m_Used != 0:
        m_BoneIdTable_Slots = int(pm.read_ushort(int(crSkeletonData_ptr) + 0x18))
        m_BoneIdTable = int(pm.read_longlong(int(crSkeletonData_ptr) + 0x10))
        hash_addr = m_BoneIdTable + 0x8 * (bone_id % m_BoneIdTable_Slots)
        i = int(pm.read_longlong(hash_addr))
        while i != 0:
            i_key = pm.read_int(i)
            if bone_id == i_key:
                p_Data = pm.read_int(i + 0x4)
                return p_Data
            i = int(pm.read_longlong(i + 0x8))
    elif bone_id < m_NumBones:
        return bone_id
    return None

def bone_world_pos(pm, ped, bone_id):
    try:
        frag_inst = pm.read_longlong(int(ped) + 0x1430)
        if not frag_inst:
            return None
        v9 = pm.read_longlong(frag_inst + 0x68)
        if not v9:
            return None
        m_pSkeleton = pm.read_longlong(v9 + 0x178)
        if not m_pSkeleton:
            return None
        crSkeletonData_ptr = pm.read_longlong(m_pSkeleton)
        if not crSkeletonData_ptr:
            return None
        Arg1 = read_matrix(pm, m_pSkeleton + 0x8)
        Arg2 = pm.read_longlong(m_pSkeleton + 0x18)
        if not Arg2:
            return None
        bone_index = get_bone_index(pm, crSkeletonData_ptr, bone_id)
        if bone_index is None:
            return None
        bone_matrix_addr = Arg2 + (int(bone_index) * 0x40)
        bone_matrix = read_matrix(pm, bone_matrix_addr)
        result = np.dot(Arg1, bone_matrix)
        pos = result[:3, 3]
        return tuple(pos)
    except Exception as e:
        return None

def get_head_pos(pm, ped, build_number=None):
    try:
        if not ped:
            return None
        bone_id = 0
        if build_number is not None and build_number >= 2802:
            bone_offset = 0x410
        else:
            bone_offset = 0x430 + 0x10 * bone_id
        mtx_addr = int(ped) + 0x60
        bone_pos_addr = int(ped) + bone_offset
        mtx_data = pm.read_bytes(mtx_addr, 64)
        bone_data = pm.read_bytes(bone_pos_addr, 12)
        mtx = np.array(struct.unpack('16f', mtx_data), dtype=np.float32).reshape((4, 4))
        bone = np.array(struct.unpack('3f', bone_data), dtype=np.float32)
        bone_h = np.append(bone, 1.0)
        transformed = np.dot(mtx, bone_h)
        return tuple(transformed[:3])
    except Exception as e:
        return None

def bone_world_pos_espstyle(pm, module_base, ped, bone_id, rmatrix_func, read_matrix_func):
    try:
        frag_inst = int(pm.read_longlong(int(ped) + 0x1430))
        v9 = int(pm.read_longlong(frag_inst + 0x68))
        if not v9:
            return None
        m_pSkeleton = int(pm.read_longlong(v9 + 0x178))
        crSkeletonData_ptr = int(pm.read_longlong(m_pSkeleton))
        if not crSkeletonData_ptr:
            return None
        m_BoneIdTable_Slots = int(pm.read_ushort(int(crSkeletonData_ptr) + 0x18))
        m_BoneIdTable = int(pm.read_longlong(int(crSkeletonData_ptr) + 0x10))
        Arg1_addr = int(pm.read_longlong(m_pSkeleton + 0x8))
        Arg1 = read_matrix_func(pm, Arg1_addr)
        Arg2 = int(pm.read_longlong(m_pSkeleton + 0x18))
        m_Used = pm.read_uint(int(crSkeletonData_ptr) + 0x1A)
        m_NumBones = int(pm.read_uint(int(crSkeletonData_ptr) + 0x5E))
        bone_index = None
        if m_Used != 0:
            hash_addr = m_BoneIdTable + 0x8 * (bone_id % m_BoneIdTable_Slots)
            i = int(pm.read_longlong(hash_addr))
            while i != 0:
                i_key = pm.read_int(i)
                if bone_id == i_key:
                    p_Data = pm.read_int(i + 0x4)
                    bone_index = p_Data
                    break
                i = int(pm.read_longlong(i + 0x8))
        elif bone_id < m_NumBones:
            bone_index = bone_id
        if bone_index is not None:
            bone_matrix_addr = Arg2 + (int(bone_index) * 0x40)
            bone_matrix = read_matrix_func(pm, bone_matrix_addr)
            vec1 = Arg1[0][:3]
            vec2 = Arg1[1][:3]
            vec3 = Arg1[2][:3]
            vec4 = Arg1[3][:3]
            vec5 = bone_matrix[3][:3]
            pos = (
                vec1[0] * vec5[0] + vec4[0] + vec2[0] * vec5[1] + vec3[0] * vec5[2],
                vec1[1] * vec5[0] + vec4[1] + vec2[1] * vec5[1] + vec3[1] * vec5[2],
                vec1[2] * vec5[0] + vec4[2] + vec2[2] * vec5[1] + vec3[2] * vec5[2],
            )
            return pos
        return None
    except Exception as e:
        return None 
