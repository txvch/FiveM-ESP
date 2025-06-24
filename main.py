import os
os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
import pygame
import struct
import math
import numpy as np
from modules.help import get_process_handle, game_ptr, get_module_info, get_build_number
import win32gui
import win32con

screen_width = 1920
screen_height = 1080

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
        print(f"[esp_overlay.py] error reading view matrix: {e}")
        return None

def tmatrix(matrix):
    return matrix.T

def world_to_screen(world_pos, pm, base_address, viewport_offset, screen_width, screen_height):
    try:
        viewport_ptr = pm.read_longlong(base_address + viewport_offset)
        view_matrix = rmatrix(pm, viewport_ptr + 0x24C)
        if view_matrix is None:
            return None
        view_matrix = tmatrix(view_matrix)
        vec_x = view_matrix[1]
        vec_y = view_matrix[2]
        vec_z = view_matrix[3]
        x = (vec_x[0] * world_pos[0]) + (vec_x[1] * world_pos[1]) + (vec_x[2] * world_pos[2]) + vec_x[3]
        y = (vec_y[0] * world_pos[0]) + (vec_y[1] * world_pos[1]) + (vec_y[2] * world_pos[2]) + vec_y[3]
        z = (vec_z[0] * world_pos[0]) + (vec_z[1] * world_pos[1]) + (vec_z[2] * world_pos[2]) + vec_z[3]
        if z <= 0.1:
            return None
        inv_z = 1.0 / z
        x *= inv_z
        y *= inv_z
        half_width = screen_width / 2
        half_height = screen_height / 2
        screen_x = x + half_width + (0.5 * x * screen_width + 0.5)
        screen_y = half_height - (0.5 * y * screen_height + 0.5)
        return int(screen_x), int(screen_y)
    except Exception as e:
        print(f"[esp_overlay.py] error in world_to_screen: {e}")
        return None

def main():
    pygame.init()
    screen = pygame.display.set_mode((screen_width, screen_height), pygame.NOFRAME)
    pygame.display.set_caption('ESP Overlay')
    hwnd = pygame.display.get_wm_info()['window']
    transparent_window(hwnd)
    clock = pygame.time.Clock()

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
    print(f"[esp_overlay.py] module_base: {hex(module_base) if module_base else module_base}")
    build = get_build_number(pm, module_base)
    print(f"[esp_overlay.py] detected build: {build}")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
        screen.fill((0, 0, 0))
        if not pm or not module_base:
            pygame.display.update()
            clock.tick(60)
            continue
        pointers = game_ptr(pm, module_base, offsets)
        if pointers:
            try:
                localplayer = pointers['localplayer']
                ped_list = pointers['ped_list']
                entity_count = pointers['entity_count']
                for i in range(int(entity_count)):
                    try:
                        ped = pm.read_longlong(int(ped_list) + (i * 0x10))
                        if not ped or ped == localplayer:
                            continue
                        health = float(pm.read_float(int(ped) + int(offsets['Health'])))
                        if health <= 0.0:
                            continue
                        pos = struct.unpack('fff', pm.read_bytes(int(ped) + 0x90, 12))
                        print(f"Ped {i} pos: {pos}")
                        screen_pos = world_to_screen(pos, pm, module_base, offsets['ViewPort'], screen_width, screen_height)
                        print(f"Ped {i} screen_pos: {screen_pos}")
                        if screen_pos:
                            box_w, box_h = 20, 40
                            rect = pygame.Rect(screen_pos[0] - box_w//2, screen_pos[1] - box_h//2, box_w, box_h)
                            pygame.draw.rect(screen, (0, 255, 0), rect, 2)
                        else:
                            pygame.draw.circle(screen, (255, 0, 0), (50, 50 + 10*i), 5)
                    except Exception as e:
                        print(f"[esp_overlay.py] error reading ped {i}: {e}")
                        continue
            except Exception as e:
                print(f"[esp_overlay.py] error in entity loop: {e}")
        pygame.display.update()
        clock.tick(60)

if __name__ == '__main__':
    main() 