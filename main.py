import os
os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
import pygame
import struct
import math
import numpy as np
from modules.help import get_process_handle, game_ptr, get_module_info, get_build_number, draw_entity, draw_entity_with_health, get_bone_world_position, read_matrix
import win32gui
import win32con
import keyboard
import win32api
import win32process
import win32com.client

screen_width = 1920
screen_height = 1080

# --- Skeleton Data ---
BONE_IDS = {
    'pelvis': 0x2e28,
    'neck': 0x9995,
    'left_upperarm': 0xb1c5,
    'right_upperarm': 0x9d4d,
    'left_forearm': 0xeeeb,
    'right_forearm': 0x6e5c,
    'left_hand': 0x49d9,
    'right_hand': 0xdead,
    'left_thigh': 0xe39f,
    'left_calf': 0xf9bb,
    'left_foot': 0x3779,
    'right_thigh': 0xca72,
    'right_calf': 0x9000,
    'right_foot': 0xcc4d,
}
SKELETON_CONNECTIONS = [
    ('pelvis', 'neck'),
    ('neck', 'left_upperarm'),
    ('neck', 'right_upperarm'),
    ('left_upperarm', 'left_forearm'),
    ('left_forearm', 'left_hand'),
    ('right_upperarm', 'right_forearm'),
    ('right_forearm', 'right_hand'),
    ('pelvis', 'left_thigh'),
    ('pelvis', 'right_thigh'),
    ('left_thigh', 'left_calf'),
    ('left_calf', 'left_foot'),
    ('right_thigh', 'right_calf'),
    ('right_calf', 'right_foot'),
]
BONE_BASE_OFFSETS = [0x430, 0x60, 0x20, 0x50, 0x440, 0x480, 0x4A0, 0x4C0, 0x4E0, 0x500]
BONE_OFFSET_COLORS = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 128, 0),
    (128, 0, 255),
    (0, 128, 255),
    (128, 255, 0),
]
STRIDES = [0x30, 0x40, 0x50]
POS_OFFSETS = [0x00, 0x10, 0x20, 0x30]

bone_pos_cache = {}

# --- Overlay/Window Section ---
def transparent_window(hwnd):
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    ex_style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
    win32gui.SetLayeredWindowAttributes(hwnd, 0x000000, 255, win32con.LWA_COLORKEY)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

def rmatrix(pm, address):
    try:
        data = pm.read_bytes(address, 64)
        values = struct.unpack('16f', data)
        matrix = np.array(values, dtype=np.float32).reshape((4, 4))
        return matrix
    except Exception as e:
        return None

def tmatrix(matrix):
    return matrix.T

def world_to_screen(world_pos, view_matrix, screen_width, screen_height):
    try:
        if any(np.isnan(x) or np.isinf(x) for x in world_pos):
            return None
        view_matrix = view_matrix.T
        vec_x = view_matrix[1]
        vec_y = view_matrix[2]
        vec_z = view_matrix[3]
        x = (vec_x[0] * world_pos[0]) + (vec_x[1] * world_pos[1]) + (vec_x[2] * world_pos[2]) + vec_x[3]
        y = (vec_y[0] * world_pos[0]) + (vec_y[1] * world_pos[1]) + (vec_y[2] * world_pos[2]) + vec_y[3]
        z = (vec_z[0] * world_pos[0]) + (vec_z[1] * world_pos[1]) + (vec_z[2] * world_pos[2]) + vec_z[3]
        if z <= 0.1 or np.isnan(x) or np.isnan(y) or np.isnan(z) or np.isinf(x) or np.isinf(y) or np.isinf(z):
            return None
        inv_z = 1.0 / z
        x *= inv_z
        y *= inv_z
        half_width = screen_width / 2
        half_height = screen_height / 2
        screen_x = x + half_width + (0.5 * x * screen_width + 0.5)
        screen_y = half_height - (0.5 * y * screen_height + 0.5)
        if any(np.isnan(val) or np.isinf(val) for val in [screen_x, screen_y]):
            return None
        return int(screen_x), int(screen_y)
    except Exception as e:
        return None

def get_bone_position(pm, ped, bone_id, frag_inst_offset=0x1430, debug=False):
    try:
        frag_inst = pm.read_longlong(int(ped) + frag_inst_offset)
        bone_array = pm.read_longlong(frag_inst + 0x50)
        bone_matrix = bone_array + bone_id * 0x40
        pos = struct.unpack('fff', pm.read_bytes(bone_matrix + 0x30, 12))
        return pos
    except Exception as e:
        return None

# --- Overlay Main Loop / Visuals ---
def run_overlay(shared_state):
    pygame.init()
    screen = pygame.display.set_mode((screen_width, screen_height), pygame.NOFRAME)
    pygame.display.set_caption('ESP Overlay')
    hwnd = pygame.display.get_wm_info()['window']
    transparent_window(hwnd)
    clock = pygame.time.Clock()
    center_x = screen_width // 2
    center_y = screen_height // 2

    offsets = {
        'World': 0x25B14B0,
        'ReplayInterface': 0x1FBD4F0,
        'ViewPort': 0x201DBA0,
        'Health': 0x280,
        'BoneHead': 0x430,
    }
    pm = get_process_handle()
    module = get_module_info(pm)
    module_base = module.lpBaseOfDll if module else 0
    build = get_build_number(pm, module_base)
    shared_state['build_number'] = build

    matrix_offsets = [0x24C, 0x1E0, 0x250, 0x2D0]
    correct_matrix_offset = None

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
        screen.fill((0, 0, 0))
        if not pm or not module_base:
            pygame.display.update()
            clock.tick(0)
            continue
        pointers = game_ptr(pm, module_base, offsets)
        if pointers:
            try:
                localplayer = pointers['localplayer']
                ped_list = pointers['ped_list']
                entity_count = pointers['entity_count']
                player_list = []
                friends = shared_state.get('friends', [])
                best_target = None
                best_dist = float('inf')
                best_head_screen = None

                viewport_ptr = int(pm.read_longlong(module_base + offsets['ViewPort']))
                local_pos = struct.unpack('fff', pm.read_bytes(int(localplayer) + 0x90, 12))
                for moff in matrix_offsets:
                    try:
                        view_matrix = rmatrix(pm, viewport_ptr + moff)
                        screen_proj = world_to_screen(local_pos, view_matrix, screen_width, screen_height)
                    except Exception as e:
                        continue

                view_matrix = rmatrix(pm, viewport_ptr + matrix_offsets[0])

                for i in range(int(entity_count)):
                    try:
                        ped = pm.read_longlong(int(ped_list) + (i * 0x10))
                        if not ped or ped == localplayer:
                            continue
                        try:
                            playerinfo_ptr = pm.read_longlong(int(ped) + 0x10A8)
                            if playerinfo_ptr:
                                ped_id = pm.read_int(int(playerinfo_ptr) + 0xE8)
                            else:
                                ped_id = 0
                        except Exception:
                            ped_id = 0
                        raw_health = float(pm.read_float(int(ped) + int(offsets['Health'])))
                        max_health = 200.0
                        health = max(0, min(raw_health, max_health)) / max_health * 100
                        if health <= 0.0:
                            continue
                        pos = struct.unpack('fff', pm.read_bytes(int(ped) + 0x90, 12))
                        local_pos = struct.unpack('fff', pm.read_bytes(int(localplayer) + 0x90, 12))
                        dx = pos[0] - local_pos[0]
                        dy = pos[1] - local_pos[1]
                        dz = pos[2] - local_pos[2]
                        distance = math.sqrt(dx*dx + dy*dy + dz*dz)
                        esp_distance = shared_state.get('esp_distance', 300)
                        if distance > esp_distance:
                            continue
                        name = 'Unknown'
                        player_list.append({'id': ped_id, 'name': name, 'distance': distance})
                        if ped_id in friends:
                            continue
                        if not shared_state.get('show_npcs', True) and ped_id == 0:
                            continue
                        screen_pos = world_to_screen(pos, view_matrix, screen_width, screen_height)

                        base_box_w, base_box_h = 80, 160
                        scale = min(2.0, max(0.5, 10.0 / (distance + 1e-5)))
                        box_w = int(base_box_w * scale)
                        box_h = int(base_box_h * scale)
                        box_color = shared_state.get('box_color', (0, 255, 0))

                        # --- Visuals: Box ESP ---
                        if shared_state.get('boxes_enabled', False):
                            if screen_pos is not None and isinstance(screen_pos, (tuple, list)) and len(screen_pos) == 2:
                                rect = pygame.Rect(screen_pos[0] - box_w//2, screen_pos[1] - box_h//2, box_w, box_h)
                                pygame.draw.rect(screen, box_color, rect, 2)

                        # --- Visuals: Health Bar ---
                        if shared_state.get('health_enabled', False):
                            if screen_pos is not None and isinstance(screen_pos, (tuple, list)) and len(screen_pos) == 2:
                                rect = pygame.Rect(screen_pos[0] - box_w//2, screen_pos[1] - box_h//2, box_w, box_h)
                                bar_x = rect.left - 8
                                bar_y = rect.top
                                bar_w = 6
                                bar_h = box_h
                                health_clamped = max(0, min(health, 100))
                                health_ratio = health_clamped / 100.0
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

                        # --- Visuals: Meters (distance) ---
                        if shared_state.get('meters_enabled', False):
                            if screen_pos is not None and isinstance(screen_pos, (tuple, list)) and len(screen_pos) == 2:
                                mark_x = screen_pos[0]
                                mark_y = screen_pos[1] - box_h // 2
                                pygame.draw.circle(screen, (255, 255, 0), (mark_x, mark_y), 5)
                                font = pygame.font.Font(None, 24)
                                distance_text = f"{distance:.1f}m"
                                text_surface = font.render(distance_text, True, (255, 255, 255))
                                text_rect = text_surface.get_rect(center=(mark_x, mark_y - 15))
                                screen.blit(text_surface, text_rect)

                        # --- Visuals: ID ESP ---
                        head_pos_for_id = None
                        head_screen_for_id = None
                        if shared_state.get('ids_enabled', False):
                            try:
                                head_pos_for_id = get_bone_world_position(pm, ped, 0x9995)
                            except Exception:
                                pass
                            if head_pos_for_id and all(-10000 < x < 10000 for x in head_pos_for_id) and not any(np.isnan(x) or np.isinf(x) for x in head_pos_for_id):
                                viewport_ptr_id = int(pm.read_longlong(module_base + offsets['ViewPort']))
                                view_matrix_id = rmatrix(pm, viewport_ptr_id + 0x24C)
                                head_screen_for_id = world_to_screen(head_pos_for_id, view_matrix_id, screen_width, screen_height)
                            id_screen = head_screen_for_id if head_screen_for_id else screen_pos
                            if (
                                id_screen is not None and
                                isinstance(id_screen, (tuple, list)) and len(id_screen) == 2 and
                                all(x is not None and isinstance(x, (int, float)) and not np.isnan(x) and not np.isinf(x) for x in id_screen)
                            ):
                                x, y = id_screen
                                if x is not None and y is not None:
                                    font = pygame.font.Font(None, 22)
                                    id_text = str(ped_id)
                                    text_surface = font.render(id_text, True, (255, 255, 255))
                                    text_rect = text_surface.get_rect(midleft=(x + 15, y - 10))
                                    screen.blit(text_surface, text_rect)

                        # --- Visuals: Skeleton ESP ---
                        if shared_state.get('skeletons_enabled', False):
                            try:
                                frag_inst = int(pm.read_longlong(int(ped) + 0x1430))
                                v9 = int(pm.read_longlong(frag_inst + 0x68))
                                if not v9:
                                    continue
                                m_pSkeleton = int(pm.read_longlong(v9 + 0x178))
                                crSkeletonData_ptr = int(pm.read_longlong(m_pSkeleton))
                                if not crSkeletonData_ptr:
                                    continue
                                m_BoneIdTable_Slots = int(pm.read_ushort(int(crSkeletonData_ptr) + 0x18))
                                m_BoneIdTable = int(pm.read_longlong(int(crSkeletonData_ptr) + 0x10))
                                Arg1_addr = int(pm.read_longlong(m_pSkeleton + 0x8))
                                Arg1 = read_matrix(pm, Arg1_addr)
                                Arg2 = int(pm.read_longlong(m_pSkeleton + 0x18))
                                ped_id = int(ped)
                                if ped_id not in bone_pos_cache:
                                    bone_pos_cache[ped_id] = {}
                                bone_screen = {}
                                for name, bone_id in BONE_IDS.items():
                                    bone_index = None
                                    m_Used = pm.read_uint(int(crSkeletonData_ptr) + 0x1A)
                                    m_NumBones = int(pm.read_uint(int(crSkeletonData_ptr) + 0x5E))
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
                                        bone_matrix = read_matrix(pm, bone_matrix_addr)
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
                                        viewport_ptr_bone = int(pm.read_longlong(module_base + offsets['ViewPort']))
                                        view_matrix_bone = rmatrix(pm, viewport_ptr_bone + 0x24C)
                                        screen_bone = world_to_screen(pos, view_matrix_bone, screen_width, screen_height)
                                        if screen_bone:
                                            prev = bone_pos_cache[ped_id].get(name)
                                            if prev:
                                                smoothed = (
                                                    int(prev[0] * 0.5 + screen_bone[0] * 0.5),
                                                    int(prev[1] * 0.5 + screen_bone[1] * 0.5)
                                                )
                                                bone_screen[name] = smoothed
                                                bone_pos_cache[ped_id][name] = smoothed
                                            else:
                                                bone_screen[name] = screen_bone
                                                bone_pos_cache[ped_id][name] = screen_bone
                                for a, b in SKELETON_CONNECTIONS:
                                    if a in bone_screen and b in bone_screen:
                                        x1, y1 = bone_screen[a]
                                        x2, y2 = bone_screen[b]
                                        if (0 <= x1 < screen_width and 0 <= y1 < screen_height and
                                            0 <= x2 < screen_width and 0 <= y2 < screen_height):
                                            skeleton_color = shared_state.get('skeleton_color', (0, 200, 255))
                                            pygame.draw.line(screen, skeleton_color, (x1, y1), (x2, y2), 3)
                            except Exception as e:
                                continue
                        else:
                            pygame.draw.circle(screen, (255, 0, 0), (50, 50 + 10*i), 5)
                    except Exception as e:
                        continue
                shared_state['player_list'] = player_list
            except Exception as e:
                continue
        pygame.display.update()
        clock.tick(0) 
