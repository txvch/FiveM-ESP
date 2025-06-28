# Requires: pip install ttkbootstrap keyboard
import ttkbootstrap as tb
from ttkbootstrap.constants import X, LEFT, PRIMARY, SUCCESS, SECONDARY, INFO, WARNING, DANGER
from multiprocessing import Process, Manager
import tkinter as tk
from tkinter import colorchooser
import sys
import os
import threading
import keyboard
sys.path.append(os.path.dirname(__file__))
import main
import win32gui
import win32con

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)
    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#1a2233", foreground="#e0e6f0",
                         relief=tk.SOLID, borderwidth=1,
                         font=("Segoe UI", 9))
        label.pack(ipadx=6, ipady=2)
    def hide_tip(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

def start_overlay(shared_state):
    main.run_overlay(shared_state)

def force_focus(window_title):
    hwnd = win32gui.FindWindow(None, window_title)
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)

def flash_taskbar(window_title):
    hwnd = win32gui.FindWindow(None, window_title)
    if hwnd:
        win32gui.FlashWindow(hwnd, True)
    
def main_gui():
    manager = Manager()
    shared_state = manager.dict()
    shared_state['boxes_enabled'] = False
    shared_state['meters_enabled'] = False
    shared_state['health_enabled'] = False
    shared_state['skeletons_enabled'] = False
    shared_state['box_color'] = (0, 255, 0)
    shared_state['esp_distance'] = 300
    shared_state['gui_hotkey'] = 'insert'
    shared_state['friends'] = []
    shared_state['player_list'] = []
    shared_state['show_npcs'] = True
    shared_state['skeleton_color'] = (0, 200, 255)

    overlay_proc = None

    app = tb.Window(themename="darkly")
    app.title("Technical Cheats")
    app.geometry("600x600")
    app.resizable(False, False)

    # --- Hotkey logic ---
    hotkey_var = tk.StringVar(value=shared_state['gui_hotkey'].capitalize())
    waiting_for_key = tk.BooleanVar(value=False)
    hotkey_hook_id = [None]  # Use a list to allow assignment in nested function

    def listen_for_hotkey():
        while True:
            key = shared_state.get('gui_hotkey', 'insert')
            keyboard.wait(key)
            app.after(0, toggle_gui_visibility)
            keyboard.wait('esc') if key == 'esc' else keyboard.wait(key, suppress=False)

    def toggle_gui_visibility():
        if app.state() == 'normal':
            app.iconify()
        else:
            app.deiconify()
            app.lift()
            force_focus(app.title())
            flash_taskbar(app.title())

    def set_hotkey():
        if waiting_for_key.get():
            return
        waiting_for_key.set(True)
        set_hotkey_btn.config(text='Waiting...')
        def on_key_press(event):
            key = event.name
            shared_state['gui_hotkey'] = key
            hotkey_var.set(key.capitalize())
            set_hotkey_btn.config(text=f"Set GUI Hotkey ({key.capitalize()})")
            waiting_for_key.set(False)
            if hotkey_hook_id[0] is not None:
                keyboard.unhook(hotkey_hook_id[0])
        hotkey_hook_id[0] = keyboard.hook(on_key_press, suppress=False)

    def start_hotkey_thread():
        t = threading.Thread(target=listen_for_hotkey, daemon=True)
        t.start()
    start_hotkey_thread()

    # --- Tabbed interface ---
    notebook = tb.Notebook(app)
    notebook.pack(fill='both', expand=True, padx=10, pady=10)

    esp_tab = tb.Frame(notebook)
    #aimbot_tab = tb.Frame(notebook)
    world_tab = tb.Frame(notebook)
    extra_tab = tb.Frame(notebook)
    notebook.add(esp_tab, text='ESP')
    #notebook.add(aimbot_tab, text='Aimbot')
    notebook.add(world_tab, text='World')
    notebook.add(extra_tab, text='Extra')

    # --- ESP Tab ---
    options_frame = tb.LabelFrame(esp_tab, text="ESP Options", padding=30)
    options_frame.pack(fill=X, padx=30, pady=(30, 15))

    # Boxes + Color
    boxes_var = tk.BooleanVar(value=False)
    meters_var = tk.BooleanVar(value=False)
    health_var = tk.BooleanVar(value=False)
    skeletons_var = tk.BooleanVar(value=False)
    box_color_var = tk.StringVar(value='#00ff00')
    ids_var = tk.BooleanVar(value=False)
    skeleton_color_var = tk.StringVar(value='#00c8ff')

    box_row = tb.Frame(options_frame)
    box_row.pack(fill=X, pady=5)
    def on_boxes_toggle():
        shared_state['boxes_enabled'] = boxes_var.get()
    boxes_check = tb.Checkbutton(box_row, text='Enable Boxes', variable=boxes_var, command=on_boxes_toggle)
    boxes_check.pack(side=LEFT, padx=(0, 4))
    ToolTip(boxes_check, "Show 2D boxes around entities.")
    # Box color preview (clickable)
    def on_color_pick(event=None):
        color = colorchooser.askcolor(color=box_color_var.get(), title="Pick Box Color")
        if color[0]:
            rgb = tuple(int(x) for x in color[0])
            shared_state['box_color'] = rgb
            box_color_var.set('#%02x%02x%02x' % rgb)
            color_preview.config(background=box_color_var.get())
    color_preview = tb.Label(box_row, width=2, background=box_color_var.get(), relief="groove", cursor="hand2")
    color_preview.pack(side=LEFT, padx=(0, 10))
    color_preview.bind('<Button-1>', on_color_pick)
    ToolTip(color_preview, "Click to pick box color.")

    # Skeletons toggle
    def on_skeletons_toggle():
        shared_state['skeletons_enabled'] = skeletons_var.get()
    skeletons_check = tb.Checkbutton(box_row, text='Enable Skeletons', variable=skeletons_var, command=on_skeletons_toggle)
    skeletons_check.pack(side=LEFT, padx=(0, 4))
    ToolTip(skeletons_check, "Show skeleton ESP on entities.")
    # Skeleton color preview (clickable)
    def on_skeleton_color_pick(event=None):
        color = colorchooser.askcolor(color=skeleton_color_var.get(), title="Pick Skeleton Color")
        if color[0]:
            rgb = tuple(int(x) for x in color[0])
            shared_state['skeleton_color'] = rgb
            skeleton_color_var.set('#%02x%02x%02x' % rgb)
            skeleton_color_preview.config(background=skeleton_color_var.get())
    skeleton_color_preview = tb.Label(box_row, width=2, background=skeleton_color_var.get(), relief="groove", cursor="hand2")
    skeleton_color_preview.pack(side=LEFT, padx=(0, 10))
    skeleton_color_preview.bind('<Button-1>', on_skeleton_color_pick)
    ToolTip(skeleton_color_preview, "Click to pick skeleton color.")

    # Show IDs toggle
    def on_ids_toggle():
        shared_state['ids_enabled'] = ids_var.get()
    ids_check = tb.Checkbutton(box_row, text='Show IDs', variable=ids_var, command=on_ids_toggle)
    ids_check.pack(side=LEFT, padx=(0, 10))
    ToolTip(ids_check, "Show player IDs above their ESP box.")

    # Meters
    def on_meters_toggle():
        shared_state['meters_enabled'] = meters_var.get()
    meters_check = tb.Checkbutton(options_frame, text='Enable Meters', variable=meters_var, command=on_meters_toggle)
    meters_check.pack(anchor='w', pady=5)
    ToolTip(meters_check, "Show distance to each entity above their head.")

    # Health
    def on_health_toggle():
        shared_state['health_enabled'] = health_var.get()
    health_check = tb.Checkbutton(options_frame, text='Enable Health Bar', variable=health_var, command=on_health_toggle)
    health_check.pack(anchor='w', pady=5)
    ToolTip(health_check, "Show a health bar next to each entity.")

    # --- ESP Max Distance (label, slider+mark, entry) ---
    distance_section = tb.Frame(options_frame)
    distance_section.pack(fill=X, pady=10)

    # Top label
    distance_label = tb.Label(distance_section, text='ESP Max Distance (meters):')
    distance_label.pack(anchor='w', pady=(0, 2))

    # Slider + mark canvas
    slider_row = tb.Frame(distance_section)
    slider_row.pack(fill=X)
    distance_var = tk.IntVar(value=300)
    slider_canvas = tk.Canvas(slider_row, width=140, height=30, bg=app.cget('background'), highlightthickness=0)
    slider_canvas.pack(side=LEFT, padx=(0, 0))

    def update_slider_mark(val=None):
        val = distance_var.get()
        min_val, max_val = 1, 1000
        slider_len = 100  # Make this match the slider length
        x = int((val - min_val) / (max_val - min_val) * slider_len) + 20
        slider_canvas.delete('all')
        slider_canvas.create_polygon(x-5, 25, x+5, 25, x, 15, fill='#e0e6f0', outline='')
        slider_canvas.create_text(x, 8, text=f"{val}m", fill='#e0e6f0', font=("Segoe UI", 9, "bold"))

    def on_distance_slider(val):
        val_int = int(float(val))
        distance_var.set(val_int)
        distance_entry_var.set(str(val_int))
        shared_state['esp_distance'] = val_int
        update_slider_mark()
    def on_distance_entry(*args):
        try:
            val = int(distance_entry_var.get())
            if val < 1:
                val = 1
            elif val > 1000:
                val = 1000
        except ValueError:
            return
        distance_var.set(val)
        distance_slider.set(val)
        shared_state['esp_distance'] = val
        update_slider_mark()

    distance_slider = tb.Scale(slider_row, from_=1, to=1000, orient='horizontal', variable=distance_var, command=on_distance_slider, length=100)
    distance_slider.pack(side=LEFT, padx=(10, 0))
    distance_entry_var = tk.StringVar(value=str(distance_var.get()))
    update_slider_mark()

    # Entry below, centered
    entry_row = tb.Frame(distance_section)
    entry_row.pack(fill=X, pady=(4, 0))
    entry_label = tb.Label(entry_row, text='Type meters:')
    entry_label.pack(side=LEFT, padx=(0, 5))
    distance_entry = tb.Entry(entry_row, textvariable=distance_entry_var, width=8)
    distance_entry.pack(side=LEFT)
    distance_entry_var.trace_add('write', on_distance_entry)

    # --- Hotkey Option ---
    hotkey_frame = tb.Frame(options_frame)
    hotkey_frame.pack(fill=X, pady=(10, 0))
    hotkey_label = tb.Label(hotkey_frame, text='GUI Hotkey:')
    hotkey_label.pack(side=LEFT, padx=(0, 5))
    set_hotkey_btn = tb.Button(hotkey_frame, text=f"Set GUI Hotkey ({hotkey_var.get()})", command=set_hotkey)
    set_hotkey_btn.pack(side=LEFT)

    # Control Frame
    control_frame = tb.LabelFrame(esp_tab, text="Overlay Control", padding=15)
    control_frame.pack(fill=X, padx=20, pady=(10, 10))
    status_var = tk.StringVar(value="Overlay Not Running")
    status_label = tb.Label(control_frame, textvariable=status_var, font=("Segoe UI", 10, "italic"))
    status_label.pack(anchor='w', pady=(0, 10))

    def start():
        nonlocal overlay_proc
        if overlay_proc is None or not overlay_proc.is_alive():
            overlay_proc = Process(target=start_overlay, args=(shared_state,))
            overlay_proc.start()
            status_var.set("Overlay Running")
    def stop():
        nonlocal overlay_proc
        if overlay_proc and overlay_proc.is_alive():
            overlay_proc.terminate()
            overlay_proc = None
            status_var.set("Overlay Stopped")
    start_btn = tb.Button(control_frame, text="Start Overlay", command=start)
    start_btn.pack(side=LEFT, padx=(0, 10))
    ToolTip(start_btn, "Launch the ESP overlay window.")
    stop_btn = tb.Button(control_frame, text="Stop Overlay", command=stop)
    stop_btn.pack(side=LEFT)
    ToolTip(stop_btn, "Close the ESP overlay window.")

    about_frame = tb.LabelFrame(esp_tab, text="About", padding=10)
    about_frame.pack(fill=X, padx=20, pady=(10, 10))
    about_label = tb.Label(about_frame, text="Technical Utilities\nby Tech <3", font=("Segoe UI", 9))
    about_label.pack(anchor='w')

    # --- Extra Tab ---
    extra_frame = tb.LabelFrame(extra_tab, text="Extra Options", padding=30)
    extra_frame.pack(fill=X, padx=30, pady=(30, 15))
    show_npcs_var = tk.BooleanVar(value=True)
    def on_show_npcs_toggle():
        shared_state['show_npcs'] = show_npcs_var.get()
    show_npcs_check = tb.Checkbutton(extra_frame, text='Show NPCs', variable=show_npcs_var, command=on_show_npcs_toggle)
    show_npcs_check.pack(anchor='w', pady=5)
    ToolTip(show_npcs_check, "Show or hide NPCs (ID 0) in ESP.")

    # --- Players Page ---
    def refresh_players_list():
        for widget in world_tab.winfo_children():
            widget.destroy()
        tb.Label(world_tab, text='Players within 500m', font=("Segoe UI", 12, "bold")).pack(pady=10)
        # --- Scrollable player list ---
        canvas = tk.Canvas(world_tab, height=350)
        scrollbar = tk.Scrollbar(world_tab, orient='vertical', command=canvas.yview)
        scroll_frame = tb.Frame(canvas)
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True, padx=(10,0))
        scrollbar.pack(side='right', fill='y', padx=(0,10))
        player_list = shared_state.get('player_list', [])
        friends = shared_state.get('friends', [])
        for player in player_list:
            pid = player.get('id')
            name = player.get('name', 'Unknown')
            dist = player.get('distance', 0)
            frame = tb.Frame(scroll_frame)
            frame.pack(fill='x', padx=10, pady=2)
            tb.Label(frame, text=f"{name} (ID: {pid}) - {dist:.1f}m").pack(side='left')
            if pid in friends:
                btn = tb.Button(frame, text='Unfriend', command=lambda p=pid: unfriend_player(p))
            else:
                btn = tb.Button(frame, text='Friend', command=lambda p=pid: friend_player(p))
            btn.pack(side='right')
    def friend_player(pid):
        friends = shared_state.get('friends', [])
        if pid not in friends:
            friends = friends + [pid]
            shared_state['friends'] = friends
        refresh_players_list()
    def unfriend_player(pid):
        friends = shared_state.get('friends', [])
        friends = [f for f in friends if f != pid]
        shared_state['friends'] = friends
        refresh_players_list()

    # Bind tab change to refresh player list for World tab
    def on_tab_changed(event):
        selected_tab = event.widget.select()
        if event.widget.tab(selected_tab, 'text') == 'World':
            refresh_players_list()
    notebook.bind('<<NotebookTabChanged>>', on_tab_changed)

    def on_close():
        stop()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()

if __name__ == '__main__':
    main_gui() 