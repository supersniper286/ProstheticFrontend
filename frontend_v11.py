import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import collections
import random
import threading
import time
import csv
from datetime import datetime
import asyncio  # Asynchronous background loop
from bleak import BleakClient, BleakScanner  # Native BLE connection and scanning

# --- CONFIGURATION & MEDICAL CONSTANTS ---
MAX_DATA_POINTS = 50
HISTORY_LIMIT = 100  # Saved data points for detailed trends
CRITICAL_HR_HIGH = 100
CRITICAL_HR_LOW = 60
CRITICAL_OX_LOW = 94
# ESP32 BLE Characteristic UUID
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

# --- THEME PALETTE (Refined Modern) ---
COLOR_BG = "#f0f4f8"              # Cool gray background
COLOR_CARD_BG = "#ffffff"          # Pure White
COLOR_SIDEBAR = "#0c1222"          # Deep Navy
COLOR_SIDEBAR_HEADER = "#131b2e"   # Slightly lighter navy
COLOR_SIDEBAR_ITEM_BG = "#162036"  # Device list bg
COLOR_PRIMARY = "#3b82f6"          # Blue 500 (vibrant)
COLOR_PRIMARY_HOVER = "#2563eb"    # Blue 600
COLOR_PRIMARY_SOFT = "#eff6ff"     # Blue 50
COLOR_SUCCESS = "#10b981"          # Emerald 500
COLOR_SUCCESS_HOVER = "#059669"    # Emerald 600
COLOR_SUCCESS_SOFT = "#ecfdf5"     # Emerald 50
COLOR_DANGER = "#ef4444"           # Red 500
COLOR_DANGER_HOVER = "#dc2626"     # Red 600
COLOR_DANGER_SOFT = "#fef2f2"      # Red 50
COLOR_WARNING_FG = "#f59e0b"       # Amber 500
COLOR_WARNING_SOFT = "#fffbeb"     # Amber 50
COLOR_TEXT_MAIN = "#0f172a"        # Slate 900
COLOR_TEXT_SECONDARY = "#334155"   # Slate 700
COLOR_TEXT_MUTED = "#64748b"       # Slate 500
COLOR_TEXT_FAINT = "#94a3b8"       # Slate 400
COLOR_BORDER = "#e2e8f0"           # Slate 200
COLOR_BORDER_LIGHT = "#f1f5f9"     # Slate 100
COLOR_CARD_SHADOW = "#cbd5e1"      # Slate 300 — used for shadow-like border
COLOR_ACCENT_CYAN = "#06b6d4"      # Cyan 500 — for branding highlight

# Chart palette
CHART_BG = "#f8fafc"
CHART_LINE = "#3b82f6"
CHART_FILL = "#3b82f6"
CHART_GRID = "#e2e8f0"
CHART_SPINE = "#cbd5e1"
CHART_TICK = "#94a3b8"


def _rounded_frame(parent, bg, border_color, padx=0, pady=0, **kw):
    """Create a frame with a subtle card-like border (simulates rounded corners on tkinter)."""
    outer = tk.Frame(parent, bg=border_color, padx=1, pady=1, **kw)
    inner = tk.Frame(outer, bg=bg, padx=padx, pady=pady)
    inner.pack(fill=tk.BOTH, expand=True)
    return outer, inner


class ModernProstheticApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IoB Prosthetic Frontend Application | Created by Amelia Mushtaq, Arslan Naqvi & Sara Fatima")
        self.root.geometry("1400x940")
        self.root.minsize(1100, 750)
        self.root.configure(bg=COLOR_BG)

        self.devices = {} 
        self.active_serial = "TEST-DEV-999001"
        self.current_motion_state = "IDLE (Rest)"
        
        # Default mock device initialized on start
        self.register_device(self.active_serial, is_mock=True)

        self.setup_styles()
        self.setup_ui()
        
        # --- Run Async Event Loop in Background Daemon Thread ---
        self.kill_signal = False
        self.loop = asyncio.new_event_loop()
        self.data_thread = threading.Thread(target=self.start_async_loop, args=(self.loop,), daemon=True)
        self.data_thread.start()

    def start_async_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.ble_main_loop())

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=COLOR_BG)
        style.configure("Card.TFrame", background=COLOR_CARD_BG, relief="flat")
        style.configure("Sidebar.TFrame", background=COLOR_SIDEBAR)

    # ------------------------------------------------------------------
    # BUTTON HOVER HELPERS
    # ------------------------------------------------------------------
    @staticmethod
    def _bind_hover(btn, enter_bg, leave_bg, enter_fg=None, leave_fg=None):
        """Bind enter/leave events to swap background (and optionally foreground)."""
        def on_enter(e):
            btn.config(bg=enter_bg)
            if enter_fg:
                btn.config(fg=enter_fg)
        def on_leave(e):
            btn.config(bg=leave_bg)
            if leave_fg:
                btn.config(fg=leave_fg)
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

    # ------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------
    def setup_ui(self):
        # ==========================================
        # 1. SIDEBAR (Left Column)
        # ==========================================
        self.sidebar = tk.Frame(self.root, bg=COLOR_SIDEBAR, width=300)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Sidebar Header Branding
        brand_frame = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR_HEADER, padx=22, pady=22)
        brand_frame.pack(fill=tk.X)

        title_lbl = tk.Label(
            brand_frame, text="🦾 PROSTHETIC IoB", 
            fg=COLOR_ACCENT_CYAN, bg=COLOR_SIDEBAR_HEADER, font=("Segoe UI", 15, "bold")
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = tk.Label(
            brand_frame, text="Diagnostics & Calibration Hub", 
            fg=COLOR_TEXT_FAINT, bg=COLOR_SIDEBAR_HEADER, font=("Segoe UI", 9)
        )
        subtitle_lbl.pack(anchor="w", pady=(3, 0))

        # Thin accent separator below header
        tk.Frame(self.sidebar, bg=COLOR_ACCENT_CYAN, height=2).pack(fill=tk.X)

        # Device Manager Section
        dev_section = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR, padx=18, pady=18)
        dev_section.pack(fill=tk.BOTH, expand=True)

        dev_title_frame = tk.Frame(dev_section, bg=COLOR_SIDEBAR)
        dev_title_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            dev_title_frame, text="REGISTERED DEVICES", 
            fg=COLOR_TEXT_FAINT, bg=COLOR_SIDEBAR, font=("Segoe UI", 8, "bold"),
            anchor="w"
        ).pack(side=tk.LEFT)

        self.dev_count_badge = tk.Label(
            dev_title_frame, text="  1 Online  ", 
            fg="#34d399", bg="#064e3b", font=("Segoe UI", 7, "bold"), padx=7, pady=2
        )
        self.dev_count_badge.pack(side=tk.RIGHT)

        # Device Listbox Container
        list_container = tk.Frame(dev_section, bg=COLOR_SIDEBAR_ITEM_BG, highlightbackground="#1e3a5f", highlightthickness=1)
        list_container.pack(fill=tk.BOTH, expand=True, pady=(0, 16))

        self.device_listbox = tk.Listbox(
            list_container, bg=COLOR_SIDEBAR_ITEM_BG, fg="#e2e8f0", borderwidth=0,
            highlightthickness=0, font=("Cascadia Code", 10), 
            selectbackground=COLOR_PRIMARY, selectforeground="#ffffff",
            activestyle="none", relief="flat"
        )
        self.device_listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.device_listbox.bind('<<ListboxSelect>>', self.on_device_select)
        self.device_listbox.insert(tk.END, self.active_serial)
        self.device_listbox.select_set(0)

        # Sidebar Buttons
        self.btn_reg = tk.Button(
            dev_section, text="＋  Pair / Register Device", command=self.open_registration, 
            bg=COLOR_SUCCESS, fg="white", relief="flat", activebackground=COLOR_SUCCESS_HOVER,
            activeforeground="white", font=("Segoe UI", 10, "bold"), pady=10, cursor="hand2", bd=0
        )
        self.btn_reg.pack(fill=tk.X, pady=(0, 6))
        self._bind_hover(self.btn_reg, COLOR_SUCCESS_HOVER, COLOR_SUCCESS)

        self.btn_rem = tk.Button(
            dev_section, text="✕  Remove Active Device", command=self.open_removal, 
            bg="#1e293b", fg="#f87171", relief="flat", activebackground=COLOR_DANGER,
            activeforeground="white", font=("Segoe UI", 10, "bold"), pady=9, cursor="hand2", bd=0
        )
        self.btn_rem.pack(fill=tk.X)
        self._bind_hover(self.btn_rem, COLOR_DANGER, "#1e293b", enter_fg="white", leave_fg="#f87171")

        # Sidebar Footer
        footer_frame = tk.Frame(self.sidebar, bg="#080e1a", padx=16, pady=14)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(
            footer_frame, text="CUST BCS-231  •  FYP Spring 2026", 
            fg="#475569", bg="#080e1a", font=("Segoe UI", 7)
        ).pack(anchor="center")

        # ==========================================
        # 2. MAIN CONTENT AREA (Right Column)
        # ==========================================
        self.content = tk.Frame(self.root, bg=COLOR_BG)
        self.content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=26, pady=22)

        # Top App Header
        header_bar = tk.Frame(self.content, bg=COLOR_BG)
        header_bar.pack(fill=tk.X, pady=(0, 18))

        header_title_box = tk.Frame(header_bar, bg=COLOR_BG)
        header_title_box.pack(side=tk.LEFT)

        tk.Label(
            header_title_box, text="Live Dashboard", 
            font=("Segoe UI", 20, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG
        ).pack(anchor="w")

        self.lbl_active_dev_sub = tk.Label(
            header_title_box, text=f"Active Target Node: {self.active_serial} (Simulated Mock Loop)", 
            font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG
        )
        self.lbl_active_dev_sub.pack(anchor="w", pady=(2, 0))

        # System Status Pill Badge
        status_box = tk.Frame(header_bar, bg=COLOR_SUCCESS_SOFT, highlightbackground="#a7f3d0", highlightthickness=1, padx=14, pady=5)
        status_box.pack(side=tk.RIGHT)
        self.lbl_system_status = tk.Label(
            status_box, text="● SYSTEM ONLINE & STREAMING", 
            font=("Segoe UI", 9, "bold"), fg=COLOR_SUCCESS, bg=COLOR_SUCCESS_SOFT
        )
        self.lbl_system_status.pack()

        # ==========================================
        # 3. VITALS CARDS ("Biscuit Cards")
        # ==========================================
        self.vitals_frame = tk.Frame(self.content, bg=COLOR_BG)
        self.vitals_frame.pack(fill=tk.X, pady=(0, 16))

        self.lbl_hr, self.badge_hr = self.create_modern_card(
            self.vitals_frame, "Heart Rate", "hr", "BPM", icon="❤️", normal_range="60 – 100 BPM"
        )
        self.lbl_ox, self.badge_ox = self.create_modern_card(
            self.vitals_frame, "Blood Oxygen", "ox", "% SpO₂", icon="🫁", normal_range="95 – 100 %"
        )
        self.lbl_temp, self.badge_temp = self.create_modern_card(
            self.vitals_frame, "Temperature", "temp", "°C", icon="🌡️", normal_range="36.1 – 37.2 °C"
        )

        # ==========================================
        # 4. EMG WAVEFORM & THRESHOLDS CARD
        # ==========================================
        emg_outer, self.graph_outer_frame = _rounded_frame(
            self.content, bg=COLOR_CARD_BG, border_color=COLOR_CARD_SHADOW, padx=0, pady=0
        )
        emg_outer.pack(fill=tk.BOTH, expand=True, pady=(0, 16))

        # Chart Header
        chart_top_bar = tk.Frame(self.graph_outer_frame, bg=COLOR_CARD_BG, padx=20, pady=14)
        chart_top_bar.pack(fill=tk.X)

        chart_title_frame = tk.Frame(chart_top_bar, bg=COLOR_CARD_BG)
        chart_title_frame.pack(side=tk.LEFT)

        tk.Label(
            chart_title_frame, text="⚡ Live EMG Signal (Myoelectric Potential)", 
            font=("Segoe UI", 13, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_CARD_BG
        ).pack(anchor="w")

        tk.Label(
            chart_title_frame, text="12-Bit Bio-Signal Sampling (0 – 4095 mV) with Dynamic Gesture Trigger Overlays", 
            font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD_BG
        ).pack(anchor="w", pady=(2, 0))

        # Live Motion Classification Banner
        self.motion_banner = tk.Label(
            chart_top_bar, text="  Hand State: ⏸️ IDLE (Rest)  ", 
            font=("Segoe UI", 10, "bold"), fg="#1e40af", bg="#dbeafe",
            highlightbackground="#93c5fd", highlightthickness=1, padx=14, pady=5
        )
        self.motion_banner.pack(side=tk.RIGHT)

        # Matplotlib Canvas Frame
        self.graph_frame = tk.Frame(self.graph_outer_frame, bg=COLOR_CARD_BG)
        self.graph_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=2)
        
        # Configure High Quality Matplotlib Styling
        plt.rcParams.update({
            'font.family': 'Segoe UI',
            'axes.titleweight': 'bold',
        })
        self.fig, self.ax = plt.subplots(figsize=(8, 3.6), dpi=100, facecolor=COLOR_CARD_BG)
        self.ax.set_facecolor(CHART_BG)
        
        # Grid and Spines
        self.ax.grid(True, linestyle=':', alpha=0.6, color=CHART_GRID, linewidth=0.7)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['left'].set_color(CHART_SPINE)
        self.ax.spines['bottom'].set_color(CHART_SPINE)
        self.ax.spines['left'].set_linewidth(0.8)
        self.ax.spines['bottom'].set_linewidth(0.8)
        self.ax.tick_params(colors=CHART_TICK, labelsize=8, length=4, width=0.6)

        # Main Trace Line & Fill
        self.line, = self.ax.plot([], [], lw=2.0, color=CHART_LINE, zorder=5, antialiased=True, solid_capstyle='round')
        self.fill_poly = None
        
        self.ax.set_ylabel("Amplitude (mV)", fontsize=9, fontweight='bold', color='#475569')
        self.ax.set_xlabel("Time Samples (n)", fontsize=9, fontweight='bold', color='#475569')
        self.ax.set_ylim(0, 4200)
        self.fig.tight_layout(pad=2.0)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Threshold Interaction Controls
        self.thresh_ctrl_frame = tk.Frame(self.graph_outer_frame, bg=COLOR_CARD_BG, padx=20, pady=12)
        self.thresh_ctrl_frame.pack(fill=tk.X)

        tk.Label(
            self.thresh_ctrl_frame, text="Threshold Controls:", 
            font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD_BG
        ).pack(side=tk.LEFT, padx=(0, 12))
        
        btn_add_t = tk.Button(
            self.thresh_ctrl_frame, text="＋ Add Threshold", command=self.add_threshold_dialog, 
            bg=COLOR_PRIMARY, fg="white", activebackground=COLOR_PRIMARY_HOVER, activeforeground="white",
            relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=5, cursor="hand2", bd=0
        )
        btn_add_t.pack(side=tk.LEFT, padx=4)
        self._bind_hover(btn_add_t, COLOR_PRIMARY_HOVER, COLOR_PRIMARY)

        btn_edit_t = tk.Button(
            self.thresh_ctrl_frame, text="✏️ Edit Thresholds", command=self.edit_threshold_dialog, 
            bg="#475569", fg="white", activebackground="#334155", activeforeground="white",
            relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=5, cursor="hand2", bd=0
        )
        btn_edit_t.pack(side=tk.LEFT, padx=4)
        self._bind_hover(btn_edit_t, "#334155", "#475569")

        btn_rem_t = tk.Button(
            self.thresh_ctrl_frame, text="🗑️ Remove Threshold", command=self.remove_threshold_dialog, 
            bg=COLOR_BORDER_LIGHT, fg=COLOR_DANGER, activebackground=COLOR_DANGER, activeforeground="white",
            relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=5, cursor="hand2",
            highlightbackground="#fca5a5", highlightthickness=1, bd=0
        )
        btn_rem_t.pack(side=tk.LEFT, padx=4)
        self._bind_hover(btn_rem_t, COLOR_DANGER_SOFT, COLOR_BORDER_LIGHT)

        # ==========================================
        # 5. SYSTEM EVENT LOG (Bottom Area)
        # ==========================================
        log_card_outer, log_outer = _rounded_frame(
            self.content, bg=COLOR_CARD_BG, border_color=COLOR_CARD_SHADOW, padx=18, pady=14
        )
        log_card_outer.pack(fill=tk.X)

        log_header = tk.Frame(log_outer, bg=COLOR_CARD_BG)
        log_header.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            log_header, text="📋 System Event Log & Biological Safety Alerts", 
            bg=COLOR_CARD_BG, font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_MAIN
        ).pack(side=tk.LEFT)

        clear_btn = tk.Button(
            log_header, text="Clear Log", command=self.clear_log,
            bg=COLOR_BORDER_LIGHT, fg=COLOR_TEXT_MUTED, relief="flat", font=("Segoe UI", 8),
            padx=10, pady=2, cursor="hand2", bd=0
        )
        clear_btn.pack(side=tk.RIGHT)
        self._bind_hover(clear_btn, COLOR_BORDER, COLOR_BORDER_LIGHT)

        log_inner_frame = tk.Frame(log_outer, bg="#0c1222", highlightbackground="#1e293b", highlightthickness=1)
        log_inner_frame.pack(fill=tk.X)

        self.log_text = tk.Text(
            log_inner_frame, height=4, bg="#0c1222", fg="#e2e8f0", relief="flat", 
            font=("Cascadia Code", 9), state="disabled", padx=12, pady=10,
            insertbackground="#3b82f6", selectbackground="#334155"
        )
        self.log_text.pack(fill=tk.X)

        # Initial Log Notice
        self.log_event("Application initialized successfully. Mock telemetry active.", "INFO")

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state="disabled")

    def create_modern_card(self, parent, title, data_key, unit, icon="📊", normal_range=""):
        # Outer wrapper for shadow-like border
        card_outer = tk.Frame(parent, bg=COLOR_CARD_SHADOW, padx=1, pady=1)
        card_outer.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=6)

        card = tk.Frame(card_outer, bg=COLOR_CARD_BG, padx=20, pady=16)
        card.pack(fill=tk.BOTH, expand=True)

        # Top row of card (Icon + Title + Details Button)
        top_row = tk.Frame(card, bg=COLOR_CARD_BG)
        top_row.pack(fill=tk.X)

        title_box = tk.Frame(top_row, bg=COLOR_CARD_BG)
        title_box.pack(side=tk.LEFT)

        tk.Label(title_box, text=icon, bg=COLOR_CARD_BG, font=("Segoe UI", 13)).pack(side=tk.LEFT, padx=(0, 7))
        tk.Label(title_box, text=title.upper(), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MUTED, font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)

        detail_btn = tk.Button(
            top_row, text="Analytics ↗",
            command=lambda: self.show_history_view(title, data_key, unit),
            bg=COLOR_PRIMARY_SOFT, fg=COLOR_PRIMARY, relief="flat", font=("Segoe UI", 8, "bold"),
            padx=10, pady=3, cursor="hand2", bd=0, activebackground="#dbeafe"
        )
        detail_btn.pack(side=tk.RIGHT)
        self._bind_hover(detail_btn, "#dbeafe", COLOR_PRIMARY_SOFT)

        # Value row
        val_row = tk.Frame(card, bg=COLOR_CARD_BG)
        val_row.pack(anchor="w", pady=(10, 5))
        
        lbl_val = tk.Label(val_row, text="--", bg=COLOR_CARD_BG, fg=COLOR_TEXT_MAIN, font=("Segoe UI", 28, "bold"))
        lbl_val.pack(side=tk.LEFT)
        
        tk.Label(val_row, text=f" {unit}", bg=COLOR_CARD_BG, fg=COLOR_TEXT_FAINT, font=("Segoe UI", 11)).pack(side=tk.LEFT, pady=(10, 0))

        # Bottom row (Status Badge & Range note)
        bottom_row = tk.Frame(card, bg=COLOR_CARD_BG)
        bottom_row.pack(fill=tk.X, pady=(2, 0))

        status_badge = tk.Label(
            bottom_row, text="● NORMAL", bg=COLOR_SUCCESS_SOFT, fg=COLOR_SUCCESS, font=("Segoe UI", 8, "bold"), padx=8, pady=2
        )
        status_badge.pack(side=tk.LEFT)

        if normal_range:
            tk.Label(bottom_row, text=f"Ref: {normal_range}", bg=COLOR_CARD_BG, fg=COLOR_TEXT_FAINT, font=("Segoe UI", 7)).pack(side=tk.RIGHT)

        return lbl_val, status_badge

    def add_threshold_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Gesture Threshold")
        dialog.geometry("380x280")
        dialog.configure(bg=COLOR_CARD_BG)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Configure Gesture Trigger", font=("Segoe UI", 13, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MAIN).pack(pady=(20, 4))
        tk.Label(dialog, text="Set mV activation boundary for prosthesis actuation", font=("Segoe UI", 8), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MUTED).pack(pady=(0, 14))

        form = tk.Frame(dialog, bg=COLOR_CARD_BG, padx=28)
        form.pack(fill=tk.X)

        tk.Label(form, text="Gesture Name:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY).pack(anchor="w")
        name_ent = tk.Entry(form, font=("Segoe UI", 10), bg=COLOR_BORDER_LIGHT, relief="solid", bd=1, highlightcolor=COLOR_PRIMARY, highlightthickness=1)
        name_ent.pack(fill=tk.X, pady=(3, 12), ipady=3)
        name_ent.insert(0, "Fist Clench")

        tk.Label(form, text="Trigger Value (0 – 4095 mV):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY).pack(anchor="w")
        val_ent = tk.Entry(form, font=("Segoe UI", 10), bg=COLOR_BORDER_LIGHT, relief="solid", bd=1, highlightcolor=COLOR_PRIMARY, highlightthickness=1)
        val_ent.pack(fill=tk.X, pady=(3, 16), ipady=3)
        val_ent.insert(0, "2800")

        def save():
            name = name_ent.get().strip()
            try:
                val = int(val_ent.get().strip())
                if name and 0 <= val <= 4095:
                    self.devices[self.active_serial]['thresholds'][name] = val
                    self.log_event(f"Configured gesture threshold '{name}' at {val} mV", "INFO")
                    dialog.destroy()
                    self.refresh_ui()
                else: raise ValueError
            except: 
                messagebox.showerror("Validation Error", "Please provide a valid Gesture Name and numeric threshold between 0 and 4095 mV.")
        
        btn_save = tk.Button(
            dialog, text="Save Gesture Threshold", command=save, 
            bg=COLOR_PRIMARY, fg="white", font=("Segoe UI", 10, "bold"), 
            pady=9, relief="flat", cursor="hand2", bd=0,
            activebackground=COLOR_PRIMARY_HOVER, activeforeground="white"
        )
        btn_save.pack(fill=tk.X, padx=28, pady=10)
        self._bind_hover(btn_save, COLOR_PRIMARY_HOVER, COLOR_PRIMARY)

    def edit_threshold_dialog(self):
        self.add_threshold_dialog()

    def remove_threshold_dialog(self):
        rem_win = tk.Toplevel(self.root)
        rem_win.title("Remove Gesture Threshold")
        rem_win.geometry("380x400")
        rem_win.configure(bg=COLOR_CARD_BG)
        rem_win.resizable(False, False)
        rem_win.transient(self.root)
        rem_win.grab_set()

        tk.Label(rem_win, text="Remove Threshold", font=("Segoe UI", 13, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MAIN).pack(pady=(20, 4))
        tk.Label(rem_win, text="Select active gesture threshold to delete:", font=("Segoe UI", 9), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MUTED).pack(pady=(0, 12))
        
        list_frame = tk.Frame(rem_win, bg=COLOR_BORDER_LIGHT, highlightbackground=COLOR_BORDER, highlightthickness=1)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=5)

        lb = tk.Listbox(list_frame, font=("Segoe UI", 10), bg=COLOR_BORDER_LIGHT, fg=COLOR_TEXT_MAIN, borderwidth=0, highlightthickness=0, selectbackground=COLOR_PRIMARY, selectforeground="white")
        lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        current_thresh = self.devices[self.active_serial]['thresholds']
        for name, val in current_thresh.items():
            lb.insert(tk.END, f"{name} ({val} mV)")

        def do_delete():
            selection = lb.curselection()
            if selection:
                raw_txt = lb.get(selection[0])
                key = raw_txt.split(" (")[0]
                if key in self.devices[self.active_serial]['thresholds']:
                    del self.devices[self.active_serial]['thresholds'][key]
                    self.log_event(f"Removed threshold '{key}'", "INFO")
                    rem_win.destroy()
                    self.refresh_ui()

        del_btn = tk.Button(
            rem_win, text="Delete Selected", command=do_delete, 
            bg=COLOR_DANGER, fg="white", font=("Segoe UI", 10, "bold"),
            pady=9, relief="flat", cursor="hand2", bd=0,
            activebackground=COLOR_DANGER_HOVER, activeforeground="white"
        )
        del_btn.pack(fill=tk.X, padx=24, pady=18)
        self._bind_hover(del_btn, COLOR_DANGER_HOVER, COLOR_DANGER)

    def show_history_view(self, title, data_key, unit):
        view_win = tk.Toplevel(self.root)
        view_win.title(f"Clinical Analysis: {title} | {self.active_serial}")
        view_win.geometry("760x700")
        view_win.configure(bg=COLOR_CARD_BG)
        view_win.transient(self.root)

        # Header
        head = tk.Frame(view_win, bg=COLOR_CARD_BG, padx=28, pady=20)
        head.pack(fill=tk.X)

        tk.Label(head, text=f"{title} Trend & History Report", font=("Segoe UI", 16, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MAIN).pack(anchor="w")
        tk.Label(head, text=f"Target Patient Device: {self.active_serial}  •  Data points: Last {HISTORY_LIMIT} frames", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD_BG).pack(anchor="w", pady=(3, 0))

        history_data = list(self.devices[self.active_serial]['history'][data_key])
        vals = [entry['val'] for entry in history_data] if history_data else [0]

        # Trend Chart
        fig_h, ax_h = plt.subplots(figsize=(6.2, 2.8), dpi=100, facecolor=COLOR_CARD_BG)
        ax_h.set_facecolor(CHART_BG)
        ax_h.plot(vals, color='#0284c7', marker='o', markersize=2.5, linestyle='-', linewidth=1.6, label=title)
        if len(vals) > 1:
            ax_h.fill_between(range(len(vals)), vals, min(vals), color='#0284c7', alpha=0.08)
        ax_h.set_ylabel(unit, fontsize=9, color='#475569')
        ax_h.set_xlabel("Historical Observations", fontsize=9, color='#475569')
        ax_h.grid(True, linestyle=':', alpha=0.5, color=CHART_GRID, linewidth=0.7)
        ax_h.spines['top'].set_visible(False)
        ax_h.spines['right'].set_visible(False)
        ax_h.spines['left'].set_color(CHART_SPINE)
        ax_h.spines['bottom'].set_color(CHART_SPINE)
        ax_h.tick_params(colors=CHART_TICK, labelsize=8)
        fig_h.tight_layout()

        canvas_h = FigureCanvasTkAgg(fig_h, master=view_win)
        canvas_h.get_tk_widget().pack(fill=tk.BOTH, expand=False, padx=28, pady=(0, 12))

        # Log Frame
        list_frame = tk.Frame(view_win, bg=COLOR_CARD_BG, padx=28)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        tk.Label(list_frame, text="Recorded Stream Log:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MAIN).pack(anchor="w", pady=(0, 6))
        
        log_box_frame = tk.Frame(list_frame, bg="#0c1222", highlightbackground="#1e293b", highlightthickness=1, padx=4, pady=4)
        log_box_frame.pack(fill=tk.BOTH, expand=True)

        history_area = tk.Text(log_box_frame, font=("Cascadia Code", 9), height=7, bg="#0c1222", fg="#e2e8f0", borderwidth=0, relief="flat")
        history_area.pack(fill=tk.BOTH, expand=True)
        
        if not history_data:
            history_area.insert(tk.END, "No historical readings recorded yet for this device session.\n")
        else:
            for entry in reversed(history_data):
                history_area.insert(tk.END, f"[{entry['time']}] Measured: {entry['val']} {unit}\n")
        
        history_area.config(state="disabled")

        # Action Buttons
        btn_frame = tk.Frame(view_win, bg=COLOR_CARD_BG, padx=28, pady=18)
        btn_frame.pack(fill=tk.X)

        export_btn = tk.Button(
            btn_frame, text="💾  Export Log to CSV",
            command=lambda: self.export_metric_history_to_csv(title, data_key, unit),
            bg=COLOR_SUCCESS, fg="white", font=("Segoe UI", 10, "bold"),
            padx=18, pady=9, relief="flat", cursor="hand2", bd=0,
            activebackground=COLOR_SUCCESS_HOVER, activeforeground="white"
        )
        export_btn.pack(side=tk.RIGHT)
        self._bind_hover(export_btn, COLOR_SUCCESS_HOVER, COLOR_SUCCESS)

        close_btn = tk.Button(
            btn_frame, text="Close Window", command=view_win.destroy,
            bg=COLOR_BORDER_LIGHT, fg=COLOR_TEXT_SECONDARY, font=("Segoe UI", 10),
            padx=18, pady=9, relief="flat", cursor="hand2", bd=0,
            activebackground=COLOR_BORDER
        )
        close_btn.pack(side=tk.RIGHT, padx=10)
        self._bind_hover(close_btn, COLOR_BORDER, COLOR_BORDER_LIGHT)

    def export_metric_history_to_csv(self, title, data_key, unit):
        history_data = list(self.devices[self.active_serial]['history'][data_key])

        if not history_data:
            messagebox.showinfo("No Data", f"There is no {title} data available to export.")
            return

        safe_title = title.replace(" ", "_").replace("(", "").replace(")", "")
        default_filename = f"{safe_title}_Telemetry_{self.active_serial}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_filename,
            title=f"Save {title} Clinical Export"
        )

        if not filepath:
            return

        try:
            with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Prosthetic Device Serial", self.active_serial])
                writer.writerow(["Diagnostic Metric", title])
                writer.writerow(["Exported On", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow([])
                writer.writerow(["Timestamp", f"{title} ({unit})"])
                for entry in history_data:
                    writer.writerow([entry['time'], entry['val']])

            self.log_event(f"{title} diagnostic telemetry exported to CSV successfully", "INFO")
            messagebox.showinfo("Export Successful", f"Diagnostic dataset exported successfully to:\n{filepath}")
        except Exception as e:
            self.log_event(f"CSV export failed: {str(e)}", "CRITICAL")
            messagebox.showerror("Export Failed", f"Could not save dataset file:\n{str(e)}")

    def open_registration(self):
        reg_win = tk.Toplevel(self.root)
        reg_win.title("Register / Pair Device")
        reg_win.geometry("460x380")
        reg_win.configure(bg=COLOR_CARD_BG)
        reg_win.resizable(False, False)
        reg_win.transient(self.root)
        reg_win.grab_set()

        tk.Label(reg_win, text="Register New Prosthetic Node", font=("Segoe UI", 14, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MAIN).pack(pady=(24, 3))
        tk.Label(reg_win, text="Connect via BLE Advertised Name or Simulation ID", font=("Segoe UI", 8), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MUTED).pack(pady=(0, 18))

        form = tk.Frame(reg_win, bg=COLOR_CARD_BG, padx=32)
        form.pack(fill=tk.X)

        tk.Label(form, text="Device Serial / BLE Name:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY).pack(anchor="w")
        entry_sn = tk.Entry(form, font=("Cascadia Code", 11), bg=COLOR_BORDER_LIGHT, relief="solid", bd=1, justify="center", highlightcolor=COLOR_PRIMARY, highlightthickness=1)
        entry_sn.pack(fill=tk.X, pady=(4, 14), ipady=5)
        entry_sn.insert(0, "ESP32-PROSTHETIC-01")

        is_mock_var = tk.BooleanVar(value=True)
        chk = tk.Checkbutton(
            form, text=" Run in Offline Simulation Mode (Mock Data)", 
            variable=is_mock_var, font=("Segoe UI", 9), bg=COLOR_CARD_BG, activebackground=COLOR_CARD_BG,
            fg=COLOR_TEXT_SECONDARY, selectcolor=COLOR_CARD_BG
        )
        chk.pack(anchor="w", pady=(0, 18))

        def submit():
            sn = entry_sn.get().strip()
            is_mock = is_mock_var.get()
            
            if sn:
                if is_mock:
                    self.register_device(sn, is_mock=True)
                    self.log_event(f"Registered Simulated Device '{sn}'", "INFO")
                else:
                    self.register_device(sn, port=sn, is_mock=False)
                    self.log_event(f"Registered BLE Target '{sn}'. Commencing background discovery...", "INFO")
                
                self.device_listbox.insert(tk.END, sn)
                self.dev_count_badge.config(text=f"{len(self.devices)} Registered")
                reg_win.destroy()
            else:
                messagebox.showerror("Input Error", "Please provide a valid Hardware Serial or BLE Identifier.")

        btn_submit = tk.Button(
            reg_win, text="Confirm & Add Device", command=submit, 
            bg=COLOR_PRIMARY, fg="white", activebackground=COLOR_PRIMARY_HOVER,
            activeforeground="white",
            font=("Segoe UI", 11, "bold"), pady=10, relief="flat", cursor="hand2", bd=0
        )
        btn_submit.pack(fill=tk.X, padx=32, pady=10)
        self._bind_hover(btn_submit, COLOR_PRIMARY_HOVER, COLOR_PRIMARY)

    def open_removal(self):
        if not self.devices:
            return
        
        rem_win = tk.Toplevel(self.root)
        rem_win.title("Remove Device")
        rem_win.geometry("420x280")
        rem_win.configure(bg=COLOR_CARD_BG)
        rem_win.resizable(False, False)
        rem_win.transient(self.root)
        rem_win.grab_set()

        tk.Label(rem_win, text="Remove Hardware Node", font=("Segoe UI", 14, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MAIN).pack(pady=(24, 3))
        tk.Label(rem_win, text=f"Confirm removal of current active device:\n'{self.active_serial}'", font=("Segoe UI", 10), bg=COLOR_CARD_BG, fg=COLOR_TEXT_MUTED).pack(pady=(8, 22))

        def submit():
            sn = self.active_serial
            if sn in self.devices:
                if self.devices[sn].get('serial_conn'):
                    client = self.devices[sn]['serial_conn']
                    try:
                        self.loop.call_soon_threadsafe(asyncio.create_task, client.disconnect())
                    except: pass
                
                del self.devices[sn]
                self.device_listbox.delete(0, tk.END)
                for s in self.devices.keys():
                    self.device_listbox.insert(tk.END, s)
                
                if self.devices:
                    self.active_serial = list(self.devices.keys())[0]
                    self.device_listbox.select_set(0)
                else:
                    self.register_device("TEST-DEV-999001", is_mock=True)
                    self.device_listbox.insert(tk.END, "TEST-DEV-999001")
                    self.active_serial = "TEST-DEV-999001"
                    self.device_listbox.select_set(0)
                
                self.dev_count_badge.config(text=f"{len(self.devices)} Registered")
                self.log_event(f"Device '{sn}' removed from active registry", "INFO")
                rem_win.destroy()
                self.refresh_ui()

        btn_submit = tk.Button(
            rem_win, text="Confirm Removal", command=submit, 
            bg=COLOR_DANGER, fg="white", activebackground=COLOR_DANGER_HOVER,
            activeforeground="white",
            font=("Segoe UI", 10, "bold"), pady=10, relief="flat", cursor="hand2", bd=0
        )
        btn_submit.pack(fill=tk.X, padx=34, pady=8)
        self._bind_hover(btn_submit, COLOR_DANGER_HOVER, COLOR_DANGER)

    def register_device(self, serial_no, port=None, is_mock=False):
        self.devices[serial_no] = {
            'emg': collections.deque([2000]*MAX_DATA_POINTS, maxlen=MAX_DATA_POINTS),
            'hr': 75, 'ox': 98, 'temp': 36.6, 
            'is_mock': is_mock,
            'port': port,
            'serial_conn': None,
            'thresholds': {'Point Gesture': 1600, 'Fist Clench': 3200}, 
            'history': {
                'hr': collections.deque(maxlen=HISTORY_LIMIT), 
                'ox': collections.deque(maxlen=HISTORY_LIMIT), 
                'temp': collections.deque(maxlen=HISTORY_LIMIT)
            }
        }

    def on_device_select(self, event):
        selection = self.device_listbox.curselection()
        if selection:
            self.active_serial = self.device_listbox.get(selection[0])
            mode = "Mock" if self.devices[self.active_serial]['is_mock'] else "BLE Target"
            self.lbl_active_dev_sub.config(text=f"Active Target Node: {self.active_serial} ({mode})")
            self.refresh_ui()

    def log_event(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        
        # Tags formatting
        self.log_text.tag_config("crit", foreground="#f87171", font=("Cascadia Code", 9, "bold"))
        self.log_text.tag_config("info", foreground="#60a5fa", font=("Cascadia Code", 9))
        self.log_text.tag_config("time", foreground="#64748b", font=("Cascadia Code", 8))
        self.log_text.tag_config("action", foreground="#34d399", font=("Cascadia Code", 9, "bold"))

        tag = "crit" if level == "CRITICAL" else ("action" if level == "MOTION" else "info")
        self.log_text.insert(tk.END, f"[{timestamp}] ", "time")
        self.log_text.insert(tk.END, f"[{level}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    async def ble_main_loop(self):
        """Asynchronous execution loop for real BLE transmissions and simulated data."""
        def notification_handler(sender, data):
            try:
                decoded_line = data.decode('utf-8').strip()
                parts = decoded_line.split(',')
                if len(parts) == 4:
                    new_emg = int(parts[0])
                    new_hr = int(parts[1])
                    new_ox = int(parts[2])
                    new_temp = float(parts[3])
                    
                    d = self.devices[self.active_serial]
                    d['emg'].append(new_emg)
                    d['hr'], d['ox'], d['temp'] = new_hr, new_ox, new_temp

                    ts = datetime.now().strftime("%H:%M:%S")
                    d['history']['hr'].append({'time': ts, 'val': new_hr})
                    d['history']['ox'].append({'time': ts, 'val': new_ox})
                    d['history']['temp'].append({'time': ts, 'val': new_temp})

                    if new_hr > CRITICAL_HR_HIGH or new_hr < CRITICAL_HR_LOW:
                        self.root.after(0, self.log_event, f"Cardiac Out-of-Bounds: {new_hr} BPM", "CRITICAL")
                    if new_ox < CRITICAL_OX_LOW:
                        self.root.after(0, self.log_event, f"SpO2 Desaturation: {new_ox}%", "CRITICAL")
                    
                    self.root.after(0, self.refresh_ui)
            except Exception:
                pass

        def make_disconnect_callback(device_serial):
            def handle_disconnect(client):
                self.root.after(0, self.log_event, f"Connection lost to '{device_serial}'. Retrying...", "CRITICAL")
                if device_serial in self.devices:
                    self.devices[device_serial]['serial_conn'] = None
            return handle_disconnect

        while not self.kill_signal:
            for sn, data in list(self.devices.items()):
                if data['is_mock']:
                    # Simulation Model
                    new_emg = random.randint(1850, 2150) + (random.randint(-1100, 1400) if random.random() > 0.85 else 0)
                    new_hr = random.randint(72, 78) if random.random() > 0.08 else random.randint(58, 108)
                    new_ox = random.randint(97, 99) if random.random() > 0.04 else random.randint(91, 95)
                    new_temp = round(36.6 + random.uniform(-0.3, 0.3), 1)

                    data['emg'].append(new_emg)
                    data['hr'], data['ox'], data['temp'] = new_hr, new_ox, new_temp
                    
                    ts = datetime.now().strftime("%H:%M:%S")
                    data['history']['hr'].append({'time': ts, 'val': new_hr})
                    data['history']['ox'].append({'time': ts, 'val': new_ox})
                    data['history']['temp'].append({'time': ts, 'val': new_temp})
                    self.root.after(0, self.refresh_ui)
                else:
                    if data.get('serial_conn') is None:
                        try:
                            target_name = data['port']
                            discovered_devices = await BleakScanner.discover(timeout=4.0)
                            target_address = None
                            for device in discovered_devices:
                                if device.name == target_name:
                                    target_address = device.address
                                    break
                            if target_address is None:
                                await asyncio.sleep(1.0)
                                continue
                                
                            client = BleakClient(target_address, disconnected_callback=make_disconnect_callback(sn))
                            await client.connect()
                            data['serial_conn'] = client
                            self.root.after(0, self.log_event, f"BLE connected to {target_name} ({target_address})", "INFO")
                            await client.start_notify(CHARACTERISTIC_UUID, notification_handler)
                        except Exception:
                            data['serial_conn'] = None
                            await asyncio.sleep(2.0)
                            continue
                            
            await asyncio.sleep(0.08)

    def refresh_ui(self):
        if self.active_serial not in self.devices:
            return
        
        d = self.devices[self.active_serial]
        
        # 1. Update Biscuit Cards & Status Badges
        # Heart Rate
        hr_val = d['hr']
        self.lbl_hr.config(text=str(hr_val))
        if hr_val > CRITICAL_HR_HIGH or hr_val < CRITICAL_HR_LOW:
            self.lbl_hr.config(fg=COLOR_DANGER)
            self.badge_hr.config(text="● ALERT", bg=COLOR_DANGER_SOFT, fg=COLOR_DANGER)
        else:
            self.lbl_hr.config(fg=COLOR_TEXT_MAIN)
            self.badge_hr.config(text="● NORMAL", bg=COLOR_SUCCESS_SOFT, fg=COLOR_SUCCESS)

        # Oxygen (SpO2)
        ox_val = d['ox']
        self.lbl_ox.config(text=str(ox_val))
        if ox_val < CRITICAL_OX_LOW:
            self.lbl_ox.config(fg=COLOR_DANGER)
            self.badge_ox.config(text="● LOW O₂", bg=COLOR_DANGER_SOFT, fg=COLOR_DANGER)
        else:
            self.lbl_ox.config(fg=COLOR_TEXT_MAIN)
            self.badge_ox.config(text="● OPTIMAL", bg=COLOR_SUCCESS_SOFT, fg=COLOR_SUCCESS)

        # Temperature
        temp_val = d['temp']
        self.lbl_temp.config(text=str(temp_val))
        if temp_val > 37.5 or temp_val < 35.8:
            self.lbl_temp.config(fg=COLOR_WARNING_FG)
            self.badge_temp.config(text="● ELEVATED", bg=COLOR_WARNING_SOFT, fg=COLOR_WARNING_FG)
        else:
            self.lbl_temp.config(fg=COLOR_TEXT_MAIN)
            self.badge_temp.config(text="● STABLE", bg=COLOR_SUCCESS_SOFT, fg=COLOR_SUCCESS)

        # 2. Update EMG Graph Curve
        ydata = list(d['emg'])
        xdata = list(range(len(ydata)))
        self.line.set_data(xdata, ydata)

        # Optional soft translucent fill under the EMG trace
        if self.fill_poly:
            self.fill_poly.remove()
        if len(ydata) > 0:
            self.fill_poly = self.ax.fill_between(xdata, ydata, 0, color=CHART_FILL, alpha=0.10, zorder=2)

        # 3. Dynamic Threshold Lines & Motion Detection
        for item in list(self.ax.get_children()):
            if hasattr(item, 'is_threshold_line'):
                item.remove()

        current_spike = ydata[-1] if ydata else 0
        active_gesture_triggered = None
        palette_colors = ['#ef4444', '#f59e0b', '#8b5cf6', '#10b981']

        for idx, (name, val) in enumerate(d['thresholds'].items()):
            col = palette_colors[idx % len(palette_colors)]
            l = self.ax.axhline(y=val, color=col, linestyle='--', alpha=0.75, lw=1.3, zorder=4)
            t = self.ax.text(
                MAX_DATA_POINTS - 8, val + 70, f" {name}: {val}mV ", 
                color=col, fontweight='bold', fontsize=7.5,
                bbox=dict(boxstyle="round,pad=0.3", fc="#ffffff", ec=col, alpha=0.92, lw=0.8),
                zorder=6
            )
            l.is_threshold_line = True
            t.is_threshold_line = True

            # Evaluate if latest EMG spike crosses threshold
            if current_spike >= val:
                active_gesture_triggered = name

        # 4. Update Motion Banner State
        if active_gesture_triggered:
            self.motion_banner.config(
                text=f"  Hand State: 🦾 {active_gesture_triggered.upper()} [ACTUATING]  ",
                fg="#ffffff", bg=COLOR_SUCCESS, highlightbackground=COLOR_SUCCESS_HOVER
            )
        else:
            self.motion_banner.config(
                text="  Hand State: ⏸️ IDLE (Rest)  ",
                fg="#1e40af", bg="#dbeafe", highlightbackground="#93c5fd"
            )

        self.ax.set_xlim(0, MAX_DATA_POINTS)
        self.canvas.draw_idle()

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernProstheticApp(root)
    root.mainloop()
