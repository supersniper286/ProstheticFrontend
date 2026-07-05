import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import collections
import random
import threading
import time
from datetime import datetime

# --- CONFIGURATION ---
MAX_DATA_POINTS = 50
HISTORY_LIMIT = 100  # How many historical points to track for the popup graphs
CRITICAL_HR_HIGH = 100
CRITICAL_HR_LOW = 60
CRITICAL_OX_LOW = 94

class ModernProstheticApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IoB Hybrid Diagnostic Suite - CUST CS")
        self.root.geometry("1300x900")
        self.root.configure(bg="#f0f2f5")

        self.devices = {} 
        self.active_serial = "TEST-DEV-999001"
        
        # Track threshold lines for the plot
        self.threshold_lines = {}

        self.register_device(self.active_serial, is_mock=True)

        self.setup_styles()
        self.setup_ui()
        
        self.kill_signal = False
        self.data_thread = threading.Thread(target=self.bluetooth_loop, daemon=True)
        self.data_thread.start()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Card.TFrame", background="white", relief="flat")
        style.configure("Header.TLabel", background="#f0f2f5", font=("Segoe UI", 20, "bold"))

    def setup_ui(self):
        # --- Sidebar ---
        self.sidebar = tk.Frame(self.root, bg="#2d3436", width=300)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="DEVICE MANAGER", fg="white", bg="#2d3436", font=("Segoe UI", 16, "bold"), pady=30).pack()
        
        self.device_listbox = tk.Listbox(self.sidebar, bg="#3d444b", fg="white", borderwidth=0, 
                                         highlightthickness=0, font=("Consolas", 13), selectbackground="#0984e3")
        self.device_listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        self.device_listbox.bind('<<ListboxSelect>>', self.on_device_select)
        self.device_listbox.insert(tk.END, self.active_serial)

        btn_reg = tk.Button(self.sidebar, text="+ Register Device", command=self.open_registration, 
                            bg="#00b894", fg="white", relief="flat", font=("Segoe UI", 12, "bold"), pady=15, cursor="hand2")
        btn_reg.pack(fill=tk.X, padx=20, pady=30)
        
        # Added Removal Button
        btn_rem = tk.Button(self.sidebar, text="- Remove Device", command=self.open_removal, 
                            bg="#d63031", fg="white", relief="flat", font=("Segoe UI", 12, "bold"), pady=15, cursor="hand2")
        btn_rem.pack(fill=tk.X, padx=20, pady=10)

        # --- Main Content ---
        self.content = tk.Frame(self.root, bg="#f0f2f5")
        self.content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=40, pady=30)

        # Top Bar: Vitals (Clickable Cards)
        self.vitals_frame = tk.Frame(self.content, bg="#f0f2f5")
        self.vitals_frame.pack(fill=tk.X)

        self.lbl_hr = self.create_biscuit_card(self.vitals_frame, "Heart Rate", "hr", "BPM")
        self.lbl_ox = self.create_biscuit_card(self.vitals_frame, "Oxygen (SpO2)", "ox", "%")
        self.lbl_temp = self.create_biscuit_card(self.vitals_frame, "Temperature", "temp", "°C")

        # Middle: Main EMG Graph
        self.graph_outer_frame = tk.Frame(self.content, bg="white", highlightbackground="#dfe6e9", highlightthickness=1)
        self.graph_outer_frame.pack(fill=tk.BOTH, expand=True, pady=25)
        
        self.graph_frame = tk.Frame(self.graph_outer_frame, bg="white")
        self.graph_frame.pack(fill=tk.BOTH, expand=True)
        
        self.fig, self.ax = plt.subplots(figsize=(7, 4), dpi=100, facecolor='white')
        self.ax.set_facecolor('#f8f9fa')
        self.line, = self.ax.plot([], [], lw=2, color='#0984e3', zorder=5)
        
        self.ax.set_title("Live EMG Signal (Myoelectric Potential)", fontsize=14, pad=15, fontweight='bold')
        self.ax.set_ylabel("Amplitude (mV)", fontsize=11)
        self.ax.set_xlabel("Time Samples (n)", fontsize=11)
        self.ax.set_ylim(0, 4095)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Threshold Control Bar
        self.thresh_ctrl_frame = tk.Frame(self.graph_outer_frame, bg="white")
        self.thresh_ctrl_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Button(self.thresh_ctrl_frame, text="Add Threshold", command=self.add_threshold_dialog, bg="#0984e3", fg="white", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=20)
        tk.Button(self.thresh_ctrl_frame, text="Edit Thresholds", command=self.edit_threshold_dialog, bg="#636e72", fg="white", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(self.thresh_ctrl_frame, text="Remove Threshold", command=self.remove_threshold_dialog, bg="#d63031", fg="white", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=5)

        # Bottom: Log
        tk.Label(self.content, text="System Event Log", bg="#f0f2f5", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.log_text = tk.Text(self.content, height=5, bg="white", relief="flat", font=("Consolas", 11), state="disabled", highlightbackground="#dfe6e9", highlightthickness=1)
        self.log_text.pack(fill=tk.X, pady=10)

    def add_threshold_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("New Gesture Threshold")
        dialog.geometry("300x200")
        
        tk.Label(dialog, text="Gesture Name:").pack(pady=5)
        name_ent = tk.Entry(dialog)
        name_ent.pack()
        
        tk.Label(dialog, text="Value (0-4095):").pack(pady=5)
        val_ent = tk.Entry(dialog)
        val_ent.pack()

        def save():
            name = name_ent.get().strip()
            try:
                val = int(val_ent.get().strip())
                if name and 0 <= val <= 4095:
                    self.devices[self.active_serial]['thresholds'][name] = val
                    dialog.destroy()
                else: raise ValueError
            except: messagebox.showerror("Error", "Invalid Name or Value")
        
        tk.Button(dialog, text="Add", command=save, bg="#00b894", fg="white").pack(pady=10)

    def edit_threshold_dialog(self):
        # Reuses add logic to overwrite existing keys
        self.add_threshold_dialog()

    def remove_threshold_dialog(self):
        rem_win = tk.Toplevel(self.root)
        rem_win.title("Remove Gesture Threshold")
        rem_win.geometry("300x400")
        
        tk.Label(rem_win, text="Select Threshold to Remove:", font=("Segoe UI", 10, "bold")).pack(pady=10)
        
        lb = tk.Listbox(rem_win, font=("Consolas", 11))
        lb.pack(fill=tk.BOTH, expand=True, padx=10)
        
        current_thresh = self.devices[self.active_serial]['thresholds']
        for name in current_thresh.keys():
            lb.insert(tk.END, name)

        def do_delete():
            selection = lb.curselection()
            if selection:
                key = lb.get(selection[0])
                del self.devices[self.active_serial]['thresholds'][key]
                rem_win.destroy()

        tk.Button(rem_win, text="Delete Selected", command=do_delete, bg="#d63031", fg="white").pack(pady=10)

    def create_biscuit_card(self, parent, title, data_key, unit):
        card = tk.Frame(parent, bg="white", padx=25, pady=25, highlightbackground="#dfe6e9", highlightthickness=1, cursor="hand2")
        card.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        
        for widget in (card,):
            widget.bind("<Button-1>", lambda e: self.show_history_view(title, data_key, unit))
        
        tk.Label(card, text=title.upper(), bg="white", fg="#636e72", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        val_frame = tk.Frame(card, bg="white")
        val_frame.pack(anchor="w")
        
        lbl = tk.Label(val_frame, text="--", bg="white", font=("Segoe UI", 32, "bold"))
        lbl.pack(side=tk.LEFT)
        
        tk.Label(val_frame, text=f" {unit}", bg="white", fg="#b2bec3", font=("Segoe UI", 14)).pack(side=tk.LEFT, pady=(15,0))
        return lbl

    def show_history_view(self, title, data_key, unit):
        view_win = tk.Toplevel(self.root)
        view_win.title(f"Diagnostic Report: {title}")
        view_win.geometry("700x600")
        view_win.configure(bg="white")

        tk.Label(view_win, text=f"{title} Analysis", font=("Segoe UI", 16, "bold"), bg="white", pady=10).pack()

        fig_h, ax_h = plt.subplots(figsize=(5, 3), dpi=90)
        history_data = self.devices[self.active_serial]['history'][data_key]
        vals = [entry['val'] for entry in history_data]
        
        ax_h.plot(vals, color='#e17055', marker='o', markersize=3, linestyle='-', linewidth=1)
        ax_h.set_title(f"{title} Trends Over Time")
        ax_h.set_ylabel(unit)
        ax_h.set_xlabel("Recent Readings")
        ax_h.grid(True, linestyle='--', alpha=0.6)

        canvas_h = FigureCanvasTkAgg(fig_h, master=view_win)
        canvas_h.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20)

        list_frame = tk.Frame(view_win, bg="white")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(list_frame, text="Detailed Reading Log", font=("Segoe UI", 10, "bold"), bg="white").pack(anchor="w")
        history_area = tk.Text(list_frame, font=("Consolas", 10), height=8, bg="#f8f9fa")
        history_area.pack(fill=tk.BOTH, expand=True)
        
        for entry in reversed(history_data):
            history_area.insert(tk.END, f"[{entry['time']}] Measured: {entry['val']} {unit}\n")
        
        history_area.config(state="disabled")

    def open_registration(self):
        reg_win = tk.Toplevel(self.root)
        reg_win.title("Register New Device")
        reg_win.geometry("450x280")
        
        tk.Label(reg_win, text="15-Digit Hardware ID:", font=("Segoe UI", 12), pady=20).pack()
        entry = tk.Entry(reg_win, font=("Consolas", 16), justify="center", bg="#f8f9fa")
        entry.pack(pady=10, padx=40, fill=tk.X)

        def submit():
            sn = entry.get().strip().upper()
            if len(sn) == 15:
                self.register_device(sn)
                self.device_listbox.insert(tk.END, sn)
                reg_win.destroy()
            else:
                messagebox.showerror("Format Error", "ID must be 15 alphanumeric characters.")

        tk.Button(reg_win, text="Confirm Pair", command=submit, bg="#0984e3", fg="white", 
                  font=("Segoe UI", 12, "bold"), padx=25, pady=12, relief="flat").pack(pady=20)

    def open_removal(self):
        rem_win = tk.Toplevel(self.root)
        rem_win.title("Remove Device")
        rem_win.geometry("450x280")
        
        tk.Label(rem_win, text="15-Digit Hardware ID:", font=("Segoe UI", 12), pady=20).pack()
        entry = tk.Entry(rem_win, font=("Consolas", 16), justify="center", bg="#f8f9fa")
        entry.pack(pady=10, padx=40, fill=tk.X)

        def submit():
            sn = entry.get().strip().upper()
            if sn in self.devices:
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
                
                rem_win.destroy()
            else:
                messagebox.showerror("Format Error", "Device not found in registry.")

        tk.Button(rem_win, text="Confirm Removal", command=submit, bg="#d63031", fg="white", 
                  font=("Segoe UI", 12, "bold"), padx=25, pady=12, relief="flat").pack(pady=20)

    def register_device(self, serial, is_mock=False):
        self.devices[serial] = {
            'emg': collections.deque([2000]*MAX_DATA_POINTS, maxlen=MAX_DATA_POINTS),
            'hr': 0, 'ox': 0, 'temp': 0, 
            'is_mock': is_mock,
            'thresholds': {}, # Dictionary to store Label: Value
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

    def log_event(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        tag = "crit" if level == "CRITICAL" else "info"
        self.log_text.insert(tk.END, f"[{timestamp}] {level}: {message}\n", tag)
        self.log_text.tag_config("crit", foreground="#d63031", font=("Segoe UI", 11, "bold"))
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def bluetooth_loop(self):
        while not self.kill_signal:
            for sn, data in list(self.devices.items()):
                new_emg = random.randint(1800, 2200) + (random.randint(-1200, 1200) if random.random() > 0.88 else 0)
                new_hr = random.randint(72, 78) if random.random() > 0.1 else random.randint(58, 108)
                new_ox = random.randint(97, 99) if random.random() > 0.05 else random.randint(91, 95)
                new_temp = round(36.6 + random.uniform(-0.4, 0.4), 1)

                data['emg'].append(new_emg)
                data['hr'], data['ox'], data['temp'] = new_hr, new_ox, new_temp
                
                ts = datetime.now().strftime("%H:%M:%S")
                data['history']['hr'].append({'time': ts, 'val': new_hr})
                data['history']['ox'].append({'time': ts, 'val': new_ox})
                data['history']['temp'].append({'time': ts, 'val': new_temp})

                if sn == self.active_serial:
                    if new_hr > CRITICAL_HR_HIGH or new_hr < CRITICAL_HR_LOW:
                        self.root.after(0, self.log_event, f"Cardiac Alert: {new_hr} BPM", "CRITICAL")
                    if new_ox < CRITICAL_OX_LOW:
                        self.root.after(0, self.log_event, f"O2 Desaturation: {new_ox}%", "CRITICAL")
                
                self.root.after(0, self.refresh_ui)
            time.sleep(0.1)

    def refresh_ui(self):
        if self.active_serial in self.devices:
            d = self.devices[self.active_serial]
            self.lbl_hr.config(text=str(d['hr']), foreground="#d63031" if (d['hr']>100 or d['hr']<60) else "#2d3436")
            self.lbl_ox.config(text=str(d['ox']), foreground="#d63031" if d['ox']<94 else "#2d3436")
            self.lbl_temp.config(text=str(d['temp']))

            ydata = list(d['emg'])
            self.line.set_data(range(len(ydata)), ydata)
            
            # --- Draw Thresholds ---
            # Remove old threshold lines/labels
            for item in self.ax.get_children():
                if hasattr(item, 'is_threshold_line'):
                    item.remove()

            for name, val in d['thresholds'].items():
                l = self.ax.axhline(y=val, color='red', linestyle='--', alpha=0.6)
                t = self.ax.text(MAX_DATA_POINTS-5, val+50, name, color='red', fontweight='bold')
                l.is_threshold_line = True
                t.is_threshold_line = True

            self.ax.set_xlim(0, MAX_DATA_POINTS)
            self.canvas.draw_idle()

    # --- NEW EXPLICIT USE CASE FUNCTIONS FROM DOC ---

    def verify_eligibility(self):
        """UC01: Verify Eligibility"""
        self.log_event("Verifying prosthetic system user eligibility...", "INFO")
        # Simulating random eligibility check outcome for testing
        eligible = random.choice([True, False])
        if eligible:
            self.log_event("Eligibility Verified Successfully.", "INFO")
            return True
        else:
            self.log_event("User is not eligible.", "CRITICAL")
            return False

    def download_frontend_with_qr_code(self):
        """UC02: Download Frontend with QR Code"""
        self.log_event("Generating QR code for frontend desktop application download...", "INFO")
        # Test generation stub
        qr_success = random.choice([True, False])
        if qr_success:
            self.log_event("QR code scan successful. Providing link. Application downloaded.", "INFO")
        else:
            self.log_event("QR code scan failed. Retrying configuration link generation...", "INFO")

    def connect_device_wirelessly(self):
        """UC03: Connect Device Wirelessly"""
        self.log_event("Scanning for wireless prosthetic devices...", "INFO")
        connection_success = random.choice([True, False])
        if connection_success:
            self.log_event(f"Connection established successfully with device: {self.active_serial}", "INFO")
        else:
            self.log_event("Wireless connection failed. Showing retry option.", "CRITICAL")

    def register_device_uc(self, serial_number):
        """UC04: Register Device Wrapper"""
        self.log_event(f"Initiating registration for serial number: {serial_number}", "INFO")
        if len(serial_number) == 15:
            self.register_device(serial_number)
            self.log_event(f"Device {serial_number} successfully registered and linked.", "INFO")
        else:
            self.log_event("Invalid serial number error displayed.", "CRITICAL")

    def manage_devices(self):
        """UC05: Manage Devices"""
        self.log_event("Opening device manager and compiling device list records.", "INFO")
        if not self.devices:
            self.log_event("Device list context is empty.", "INFO")
        else:
            self.log_event(f"Displaying current active devices records count: {len(self.devices)}", "INFO")

    def remove_device(self, serial_number):
        """UC06: Remove Device Logic Handler"""
        if serial_number in self.devices:
            del self.devices[serial_number]
            self.log_event(f"Device {serial_number} completely removed from system records.", "INFO")
        else:
            self.log_event("Removal action cancelled or hardware ID matching failed.", "INFO")

    def view_connected_devices(self):
        """UC07: View Connected Devices"""
        self.log_event("Retrieving list of actively connected devices...", "INFO")
        connected = [sn for sn, d in self.devices.items()]
        if connected:
            self.log_event(f"Currently connected hardware: {', '.join(connected)}", "INFO")
        else:
            self.log_event("No connected devices found to display.", "INFO")

    def view_iob_information(self):
        """UC08: View IOB Information"""
        self.log_event("Retrieving Internet of Bodies telemetry data packages...", "INFO")
        if self.active_serial in self.devices:
            self.log_event(f"IOB telemetry linked to {self.active_serial} is healthy.", "INFO")
        else:
            self.log_event("No active IOB payload data available.", "INFO")

    def view_emg_readings(self):
        """UC09: View EMG Readings (Returns test stream point via RNG)"""
        # Generates a random dummy raw input signal point for verification testing
        rng_emg_signal = random.randint(0, 4095)
        return rng_emg_signal

    def view_vital_readings(self):
        """UC10: View Vital Readings"""
        if self.active_serial in self.devices:
            d = self.devices[self.active_serial]
            self.log_event(f"Fetched Vitals -> HR: {d['hr']} BPM, SpO2: {d['ox']}%, Temp: {d['temp']}°C", "INFO")
        else:
            self.log_event("Error: Vital metrics stream structurally unavailable.", "CRITICAL")

    def set_motion_thresholds(self, gesture_name, value):
        """UC11: Set Motion Thresholds"""
        if 0 <= value <= 4095:
            self.devices[self.active_serial]['thresholds'][gesture_name] = value
            self.log_event(f"Threshold set: {gesture_name} at value {value}", "INFO")
        else:
            self.log_event("Invalid threshold bounds configuration captured.", "CRITICAL")

    def adjust_motion_threshold_parameters(self):
        """UC12: Adjust Motion Threshold Parameters"""
        self.log_event("Fine-tuning configured movement baseline parameter bounds...", "INFO")
        # Dummy verification parameter adjust logic
        self.log_event("Parameters adjusted and updated values saved successfully.", "INFO")

    def perform_device_motion(self):
        """UC13: Perform Device Motion (Uses random stream trigger for testing)"""
        # Fetching a random test EMG raw value stream point
        current_signal = self.view_emg_readings()
        
        # Test baseline detection benchmark evaluation
        if current_signal > 3000:
            self.log_event(f"Muscle potential strong ({current_signal} mV). Executing hand grasp movement.", "INFO")
        else:
            self.log_event(f"Weak signal threshold recorded ({current_signal} mV). Action motion bypassed.", "INFO")

    def adjust_motion_intensity(self, intensity_value):
        """UC14: Adjust Motion Intensity"""
        self.log_event(f"Requesting intensity structural scaling adjustments to: {intensity_value}", "INFO")
        if isinstance(intensity_value, (int, float)):
            self.log_event("Motion speed and terminal kinetic strength configurations successfully saved.", "INFO")
        else:
            self.log_event("Error processing intensity modifications: Invalid format.", "CRITICAL")


if __name__ == "__main__":
    root = tk.Tk()
    app = ModernProstheticApp(root)
    root.mainloop()
