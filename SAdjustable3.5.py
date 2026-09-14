import tkinter as tk
from tkinter import ttk
import random
import time
import csv
import math
import sys

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MultipleLocator
from matplotlib.colors import ListedColormap

#Serial support for the real Arduino sensor board. If pyserial isn't
#installed (e.g. testing on a dev machine with no hardware attached),
#the app falls back to simulated values instead of crashing.
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# --- DARK MODE COLORS ---
BG_COLOR = "#1e1e1e"
FG_COLOR = "#e0e0e0"
ACCENT_COLOR = "#2d2d2d"
BUTTON_BG = "#3a3a3a"
BUTTON_ACTIVE_BG = "#505050"

# Update interval for sensor logging, in milliseconds
UPDATE_INTERVAL_MS = 4000

# --- ARDUINO SERIAL CONNECTION ---
SERIAL_PORT = "/dev/ttyACM0"
SERIAL_BAUD = 9600

# --- REAL SENSOR CHANNELS (from the Arduino gas sensor board) ---
SENSOR_NAMES = ["MQ3", "MQ137", "MQ138"]
NUM_SENSORS = len(SENSOR_NAMES)

# The original desktop layout was designed at this width - all font
# sizes and paddings below are scaled relative to it so the same code
# auto-fits a much smaller panel (e.g. a 3.5" LCD, commonly 480x320).
DESIGN_WIDTH = 1000

# Typical 3.5" touchscreen resolution (e.g. Raspberry Pi 3.5" LCD/HDMI
# panels). Used as a fallback target when running on a normal dev
# monitor, so the window previews at the same size the real panel
# would use. If Tkinter reports an actual small screen (running on
# the real hardware), that real resolution is used instead.
TARGET_LCD_WIDTH = 480
TARGET_LCD_HEIGHT = 320

plt.style.use("dark_background")


class ENoseApp:

    def __init__(self, root):

        self.root = root
        self.root.title("Mushroom E-Nose (3.5\" LCD)")

        #AUTO-FIT WINDOW SIZE TO THE TARGET DISPLAY
        #If Tkinter reports a small screen, we're likely already running
        #on the actual embedded panel - use its real resolution. If the
        #screen looks like a normal dev monitor, fall back to the
        #typical 3.5" panel resolution so the layout can be previewed
        #and tuned before deploying to the real hardware.
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        if screen_width <= TARGET_LCD_WIDTH + 40 and screen_height <= TARGET_LCD_HEIGHT + 40:
            window_width = screen_width
            window_height = screen_height
        else:
            window_width = TARGET_LCD_WIDTH
            window_height = TARGET_LCD_HEIGHT

        self.root.geometry(f"{window_width}x{window_height}")
        self.root.resizable(True, True)
        self.root.minsize(240, 160)

        #Scale factor applied to every font size / padding value below,
        #so the whole layout shrinks (or grows) to fit whatever window
        #size was chosen above.
        self.scale = window_width / DESIGN_WIDTH

        self.root.configure(bg=BG_COLOR)

        self.running = False
        self.start_time = time.time()
        self.after_id = None
        self.timer_after_id = None

        #ARDUINO CONNECTION
        #Tries once at startup. If it fails (no board, wrong port, or
        #pyserial missing), the app keeps running with simulated data
        #instead of crashing - useful for developing/testing the UI
        #without the hardware attached.
        self.arduino = None
        self.hardware_connected = False
        self._last_sensor_values = [0] * NUM_SENSORS

        if SERIAL_AVAILABLE:
            try:
                self.arduino = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2)
                time.sleep(2)
                self.hardware_connected = True
            except Exception:
                self.arduino = None
                self.hardware_connected = False

        #TTK DARK THEME SETUP
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "TLabel",
            background=BG_COLOR,
            foreground=FG_COLOR
        )

        style.configure(
            "TFrame",
            background=BG_COLOR
        )

        style.configure(
            "TButton",
            background=BUTTON_BG,
            foreground=FG_COLOR,
            borderwidth=1,
            focuscolor=BG_COLOR,
            padding=(self.spx(20), self.spx(14)),
            font=("Arial", self.fpt(12), "bold")
        )
        style.map(
            "TButton",
            background=[("active", BUTTON_ACTIVE_BG)],
            foreground=[("active", FG_COLOR)]
        )

        style.configure(
            "TCheckbutton",
            background=BG_COLOR,
            foreground=FG_COLOR,
            focuscolor=BG_COLOR
        )
        style.map(
            "TCheckbutton",
            background=[("active", BG_COLOR)],
            foreground=[("active", FG_COLOR)]
        )

        style.configure(
            "TCombobox",
            fieldbackground=BUTTON_BG,
            background=BUTTON_BG,
            foreground=FG_COLOR,
            arrowcolor=FG_COLOR,
            selectbackground=BUTTON_BG,
            selectforeground=FG_COLOR
        )
        self.root.option_add("*TCombobox*Listbox*Background", BUTTON_BG)
        self.root.option_add("*TCombobox*Listbox*Foreground", FG_COLOR)
        self.root.option_add(
            "*TCombobox*Listbox*selectBackground", BUTTON_ACTIVE_BG
        )

        #TITLE
        self.title_label = ttk.Label(
            self.root,
            text="Mushroom E-Nose",
            font=("Arial", self.fpt(16), "bold")
        )
        self.title_label.pack(pady=self.spx(6))

        #MAIN FRAME
        main_frame = tk.Frame(self.root, bg=BG_COLOR)
        main_frame.pack(fill="both", expand=True, padx=self.spx(10), pady=self.spx(4))

        #SENSOR FRAME
        sensor_frame = tk.Frame(main_frame, bg=BG_COLOR)
        sensor_frame.pack(fill="x", padx=self.spx(10), pady=self.spx(2))

        self.sensor_labels = []
        self.sensor_vars = []

        for i in range(NUM_SENSORS):

            sensor_item_frame = tk.Frame(sensor_frame, bg=BG_COLOR)
            sensor_item_frame.pack(side="left", padx=self.spx(10))

            var = tk.BooleanVar(value=True)
            self.sensor_vars.append(var)

            checkbox = ttk.Checkbutton(
                sensor_item_frame,
                variable=var,
                command=self.redraw_graph
            )
            checkbox.pack(side="left")

            label = ttk.Label(
                sensor_item_frame,
                text=f"{SENSOR_NAMES[i]}: ---",
                font=("Arial", self.fpt(9))
            )
            label.pack(side="left")
            self.sensor_labels.append(label)

        #CLASSIFICATION FRAME
        classification_frame = tk.Frame(main_frame, bg=BG_COLOR)
        classification_frame.pack(fill="x", padx=self.spx(10), pady=self.spx(2))

        result_row = tk.Frame(classification_frame, bg=BG_COLOR)
        result_row.pack()

        self.result_label = ttk.Label(
            result_row,
            text="WAITING",
            font=("Arial", self.fpt(11), "bold")
        )
        self.result_label.pack(side="left")

        self.timer_label = ttk.Label(
            result_row,
            text="",
            font=("Arial", self.fpt(11), "bold")
        )
        self.timer_label.pack(side="left", padx=(self.spx(6), 0))

        #GRAPH TYPE SELECTOR
        #Live/analysis graphs go here - each gets its own draw_<name>_plot()
        #method, listed in GRAPH_TYPES below.
        graph_type_frame = tk.Frame(main_frame, bg=BG_COLOR)
        graph_type_frame.pack(fill="x", padx=self.spx(10), pady=(self.spx(4), 0))

        self.graph_type_label = ttk.Label(
            graph_type_frame,
            text="Graph:",
            font=("Arial", self.fpt(9), "bold")
        )
        self.graph_type_label.pack(side="left", padx=(0, self.spx(6)))

        self.GRAPH_TYPES = [
            "Sensor Data Over Time",
            "Sensor Correlation Heatmap",
            "Profile Radar Chart (Sample)",
            "Profile Grouped Bar Chart (Sample)",
            "Profile Box Plot (Sample)",
            "Profile Parallel Coordinates (Sample)"
        ]

        self.graph_type_var = tk.StringVar(value=self.GRAPH_TYPES[0])

        self.graph_type_combo = ttk.Combobox(
            graph_type_frame,
            textvariable=self.graph_type_var,
            values=self.GRAPH_TYPES,
            state="readonly",
            width=self.spx(20),
            font=("Arial", self.fpt(8))
        )
        self.graph_type_combo.pack(side="left", fill="x", expand=True)
        self.graph_type_combo.bind(
            "<<ComboboxSelected>>",
            lambda event: self.on_graph_selected(self.graph_type_var)
        )

        #VOC PROFILE SELECTOR
        #Sample VOC/chemical profile plots (heatmaps, PCA biplot) - kept
        #separate from the graph-type selector above.
        profile_frame = tk.Frame(main_frame, bg=BG_COLOR)
        profile_frame.pack(fill="x", padx=self.spx(10), pady=(self.spx(3), 0))

        self.profile_label = ttk.Label(
            profile_frame,
            text="VOC:",
            font=("Arial", self.fpt(9), "bold")
        )
        self.profile_label.pack(side="left", padx=(0, self.spx(6)))

        self.PROFILE_TYPES = [
            "-",
            "VOC Heatmap (Peak Codes) (Sample)",
            "VOC Heatmap (Named Compounds) (Sample)",
            "PCA Biplot (Sample)"
        ]

        self.profile_var = tk.StringVar(value=self.PROFILE_TYPES[0])

        self.profile_combo = ttk.Combobox(
            profile_frame,
            textvariable=self.profile_var,
            values=self.PROFILE_TYPES,
            state="readonly",
            width=self.spx(20),
            font=("Arial", self.fpt(8))
        )
        self.profile_combo.pack(side="left", fill="x", expand=True)
        self.profile_combo.bind(
            "<<ComboboxSelected>>",
            lambda event: self.on_graph_selected(self.profile_var)
        )

        #ANN TRAINING PROFILE SELECTOR
        #Static diagnostic plots from a single ANN training run - kept
        #separate from the live/analysis graphs above.
        ann_profile_frame = tk.Frame(main_frame, bg=BG_COLOR)
        ann_profile_frame.pack(fill="x", padx=self.spx(10), pady=(self.spx(3), 0))

        self.ann_profile_label = ttk.Label(
            ann_profile_frame,
            text="ANN:",
            font=("Arial", self.fpt(9), "bold")
        )
        self.ann_profile_label.pack(side="left", padx=(0, self.spx(6)))

        self.ANN_PROFILE_TYPES = [
            "-",
            "Training State Plot (Sample)",
            "Performance Plot (Sample)",
            "Characteristic Plot (Sample)"
        ]

        self.ann_profile_var = tk.StringVar(value=self.ANN_PROFILE_TYPES[0])

        self.ann_profile_combo = ttk.Combobox(
            ann_profile_frame,
            textvariable=self.ann_profile_var,
            values=self.ANN_PROFILE_TYPES,
            state="readonly",
            width=self.spx(20),
            font=("Arial", self.fpt(8))
        )
        self.ann_profile_combo.pack(side="left", fill="x", expand=True)
        self.ann_profile_combo.bind(
            "<<ComboboxSelected>>",
            lambda event: self.on_graph_selected(self.ann_profile_var)
        )

        #Tracks whichever plot was chosen most recently, from either dropdown
        self.active_plot_name = self.GRAPH_TYPES[0]

        #GRAPH FRAME
        graph_frame = tk.Frame(main_frame, bg=BG_COLOR)
        graph_frame.pack(fill="both", expand=True, padx=self.spx(10), pady=self.spx(4))

        #Figure size starts proportional to the window; it is then kept
        #in sync with the actual widget size via the <Configure> handler
        #bound below, so the plot always auto-fits whatever space is left.
        dpi = 100
        self.figure_dpi = dpi
        self.figure = plt.figure(
            figsize=(window_width / dpi, max(window_height * 0.35 / dpi, 0.5)),
            dpi=dpi
        )
        self.figure.patch.set_facecolor(BG_COLOR)

        self.canvas = FigureCanvasTkAgg(
            self.figure,
            master=graph_frame
        )
        self.canvas.get_tk_widget().configure(bg=BG_COLOR, highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.get_tk_widget().bind("<Configure>", self.on_canvas_resize)

        #STATUS
        initial_status = (
            "Status: Arduino Connected"
            if self.hardware_connected
            else "Status: No Arduino (simulated)"
        )
        self.status_label = ttk.Label(
            self.root,
            text=initial_status,
            font=("Arial", self.fpt(9))
        )
        self.status_label.pack(pady=self.spx(2))

        #BUTTONS
        button_frame = tk.Frame(self.root, bg=BG_COLOR)
        button_frame.pack(pady=self.spx(6))

        ttk.Button(
            button_frame,
            text="Start",
            command=self.start_test
        ).pack(side="left", padx=self.spx(4))

        ttk.Button(
            button_frame,
            text="Stop",
            command=self.stop_test
        ).pack(side="left", padx=self.spx(4))

        ttk.Button(
            button_frame,
            text="Save",
            command=self.save_data
        ).pack(side="left", padx=self.spx(4))

        ttk.Button(
            button_frame,
            text="Reset",
            command=self.reset_graph
        ).pack(side="left", padx=self.spx(4))

        #GRAPH DATA
        self.time_data = []
        self.sensor_data = [[] for _ in range(NUM_SENSORS)]

        self.redraw_graph()

        #LIVE RESCALING ON WINDOW RESIZE
        #Recomputes self.scale and reapplies it to fonts/padding whenever
        #the user drags the window to a new size.
        self.root.bind("<Configure>", self.on_root_resize)

        #CLEAN EXIT
        #Make sure closing the window actually ends the Python process
        #(cancels pending timers, closes the matplotlib figure, then
        #exits) instead of leaving it running in the background.
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    #SCALING HELPERS
    #fpt() scales a base font point size; spx() scales a base pixel
    #value (padding, width). Both stay at a sane minimum so nothing
    #disappears entirely on very small panels.
    def fpt(self, base_size):
        return max(6, int(round(base_size * self.scale)))

    def spx(self, base_size):
        return max(1, int(round(base_size * self.scale)))

    #ROOT WINDOW RESIZE
    #Recomputes the scale factor whenever the window itself is resized
    #(ignores resize events bubbling up from child widgets) and, if it
    #changed meaningfully, reapplies it across the UI.
    def on_root_resize(self, event):

        if event.widget is not self.root:
            return

        new_scale = event.width / DESIGN_WIDTH

        if abs(new_scale - self.scale) < 0.01:
            return

        self.scale = new_scale
        self.apply_scale()

    #APPLY SCALE
    #Reapplies the current self.scale to every font/padding-sensitive
    #widget. ttk widgets sharing a style (buttons, comboboxes) update
    #automatically once the style itself is reconfigured; individually
    #styled labels are updated directly.
    def apply_scale(self):

        style = ttk.Style()

        style.configure(
            "TButton",
            padding=(self.spx(20), self.spx(14)),
            font=("Arial", self.fpt(12), "bold")
        )

        self.title_label.config(font=("Arial", self.fpt(16), "bold"))

        for label in self.sensor_labels:
            label.config(font=("Arial", self.fpt(9)))

        self.result_label.config(font=("Arial", self.fpt(11), "bold"))
        self.timer_label.config(font=("Arial", self.fpt(11), "bold"))

        self.graph_type_label.config(font=("Arial", self.fpt(9), "bold"))
        self.profile_label.config(font=("Arial", self.fpt(9), "bold"))
        self.ann_profile_label.config(font=("Arial", self.fpt(9), "bold"))

        for combo in (
            self.graph_type_combo, self.profile_combo, self.ann_profile_combo
        ):
            combo.configure(font=("Arial", self.fpt(8)), width=self.spx(20))

        self.status_label.config(font=("Arial", self.fpt(9)))

        #The graph itself already redraws at the new scale via
        #on_canvas_resize (triggered by the container's own resize),
        #but force a redraw here too in case the figure size didn't
        #change enough to trigger that on its own.
        self.redraw_graph()

    #CLEAN EXIT
    #Cancels any pending after() callbacks and closes the matplotlib
    #figure before tearing down the window, then explicitly exits the
    #process so closing the window always returns cleanly to the
    #shell/venv with nothing left running in the background.
    def on_close(self):

        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        if self.timer_after_id is not None:
            self.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None

        if self.arduino is not None:
            try:
                self.arduino.close()
            except Exception:
                pass

        plt.close(self.figure)

        self.root.destroy()
        sys.exit(0)

    #CANVAS RESIZE
    #Keeps the matplotlib figure's physical size in sync with the
    #actual pixel size of its container, so the plot always fills the
    #available space instead of leaving blank margins or clipping.
    def on_canvas_resize(self, event):

        if event.width < 10 or event.height < 10:
            return

        new_width_in = event.width / self.figure_dpi
        new_height_in = event.height / self.figure_dpi

        current_size = self.figure.get_size_inches()

        if (
            abs(current_size[0] - new_width_in) > 0.02
            or abs(current_size[1] - new_height_in) > 0.02
        ):
            self.figure.set_size_inches(new_width_in, new_height_in, forward=False)
            self.redraw_graph()

    #START
    def start_test(self):

        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        if self.timer_after_id is not None:
            self.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None

        self.running = True
        self.start_time = time.time()

        #Starting a new test should begin a clean graph, not append
        #onto whatever was left over from the previous run.
        self.time_data = []
        self.sensor_data = [[] for _ in range(NUM_SENSORS)]

        for i, label in enumerate(self.sensor_labels):
            label.config(text=f"{SENSOR_NAMES[i]}: ---")

        self.redraw_graph()

        self.status_label.config(
            text=(
                "Status: Connected / Testing"
                if self.hardware_connected
                else "Status: Testing (simulated)"
            )
        )

        self.result_label.config(
            text="ANALYZING"
        )

        self.update_data()
        self.update_timer()

    #STOP
    def stop_test(self):

        self.running = False

        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        if self.timer_after_id is not None:
            self.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None

        self.status_label.config(
            text="Status: Test Stopped"
        )

    #UPDATE
    def update_data(self):

        if not self.running:
            return

        current_time = time.time() - self.start_time
        self.time_data.append(current_time)

        values = self.read_sensor_values()

        for i in range(NUM_SENSORS):

            self.sensor_data[i].append(values[i])

            self.sensor_labels[i].config(
                text=f"{SENSOR_NAMES[i]}: {values[i]}"
            )

        #UPDATE GRAPH
        self.redraw_graph()

        self.after_id = self.root.after(UPDATE_INTERVAL_MS, self.update_data)

    #READ SENSOR VALUES
    #Reads one MQ3,MQ137,MQ138 line from the Arduino if connected.
    #Falls back to simulated values (and to the last good reading, if
    #a line comes back malformed) so a hiccup on the serial line never
    #crashes the update loop.
    def read_sensor_values(self):

        if self.hardware_connected and self.arduino is not None:
            try:
                line = self.arduino.readline().decode("utf-8").strip()

                if line:
                    parts = line.split(",")

                    if len(parts) == NUM_SENSORS:
                        values = [int(p) for p in parts]
                        self._last_sensor_values = values
                        return values

                return self._last_sensor_values

            except (serial.SerialException, ValueError, UnicodeDecodeError):
                self.hardware_connected = False
                self.status_label.config(
                    text="Status: Arduino disconnected - simulated"
                )

        values = [random.randint(200, 600) for _ in range(NUM_SENSORS)]
        self._last_sensor_values = values
        return values

    #TIMER
    def update_timer(self):

        if not self.running:
            return

        elapsed = time.time() - self.start_time

        self.timer_label.config(
            text=f"({self.format_elapsed(elapsed)})"
        )

        self.timer_after_id = self.root.after(1000, self.update_timer)

    #FORMAT ELAPSED TIME
    @staticmethod
    def format_elapsed(seconds):

        total_seconds = int(seconds)
        minutes = total_seconds // 60
        secs = total_seconds % 60

        return f"{minutes:02d}:{secs:02d}"

    #GRAPH SELECTION (called by either dropdown)
    def on_graph_selected(self, var):

        self.active_plot_name = var.get()
        self.redraw_graph()

    #REDRAW (dispatches to the method for whichever graph type is selected)
    def redraw_graph(self):

        graph_type = self.active_plot_name

        self.figure.clf()
        self.figure.patch.set_facecolor(BG_COLOR)

        if graph_type == "Sensor Correlation Heatmap":
            self.draw_sensor_correlation_heatmap()
        elif graph_type == "Training State Plot (Sample)":
            self.draw_training_state_plot()
        elif graph_type == "Performance Plot (Sample)":
            self.draw_performance_plot()
        elif graph_type == "Characteristic Plot (Sample)":
            self.draw_characteristic_plot()
        elif graph_type == "VOC Heatmap (Peak Codes) (Sample)":
            self.draw_voc_heatmap_peak_codes()
        elif graph_type == "VOC Heatmap (Named Compounds) (Sample)":
            self.draw_voc_heatmap_named_compounds()
        elif graph_type == "PCA Biplot (Sample)":
            self.draw_pca_biplot()
        elif graph_type == "Profile Radar Chart (Sample)":
            self.draw_profile_radar_chart()
        elif graph_type == "Profile Grouped Bar Chart (Sample)":
            self.draw_profile_grouped_bar_chart()
        elif graph_type == "Profile Box Plot (Sample)":
            self.draw_profile_box_plot()
        elif graph_type == "Profile Parallel Coordinates (Sample)":
            self.draw_profile_parallel_coordinates()
        else:
            self.draw_sensor_graph()

        self.canvas.draw()

    #SENSOR DATA OVER TIME PLOT
    def draw_sensor_graph(self):

        ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(
            right=0.72, bottom=0.32, left=0.16, top=0.86
        )

        ax.set_facecolor(BG_COLOR)
        ax.set_title(
            "Sensor Data Over Time", color=FG_COLOR, fontsize=self.fpt(11)
        )
        ax.set_xlabel("Time (s)", color=FG_COLOR, fontsize=self.fpt(9))
        ax.set_ylabel("Sensor Values", color=FG_COLOR, fontsize=self.fpt(9))
        ax.tick_params(colors=FG_COLOR, labelsize=self.fpt(7))

        #DYNAMIC X-AXIS TICK SPACING
        #Keeps roughly MAX_TICKS labels on screen no matter how long the
        #test runs, snapped to multiples of the 4s logging interval.
        MAX_TICKS = 12

        if len(self.time_data) >= 2:
            data_range = self.time_data[-1] - self.time_data[0]
            raw_interval = data_range / MAX_TICKS
            interval = max(4, math.ceil(raw_interval / 4) * 4)
            ax.set_xlim(self.time_data[0], self.time_data[-1])
        else:
            #No data yet (e.g. right after Reset) - show a clean,
            #fixed placeholder range instead of letting matplotlib
            #autoscale to a degenerate/empty range.
            interval = 4
            ax.set_xlim(0, 4)

        ax.xaxis.set_major_locator(MultipleLocator(interval))
        ax.tick_params(axis="x", rotation=45, colors=FG_COLOR)

        for spine in ax.spines.values():
            spine.set_color(FG_COLOR)

        for i in range(NUM_SENSORS):
            if self.sensor_vars[i].get():
                ax.plot(
                    self.time_data,
                    self.sensor_data[i],
                    label=f"{SENSOR_NAMES[i]}",
                    marker="o",
                    markersize=max(2, self.spx(5))
                )

        if any(var.get() for var in self.sensor_vars):
            legend = ax.legend(
                loc="upper left",
                bbox_to_anchor=(1.02, 1),
                borderaxespad=0,
                fontsize=self.fpt(7)
            )
            legend.get_frame().set_facecolor(ACCENT_COLOR)
            for text in legend.get_texts():
                text.set_color(FG_COLOR)

    #SENSOR CORRELATION HEATMAP (live data - based on heatmap.py)
    #Computes the Pearson correlation between the collected MQ sensor
    #channels, the same idea as the standalone heatmap.py script, but
    #drawn straight from the in-memory readings of the current run
    #instead of re-reading a saved CSV, and using plain matplotlib so
    #no seaborn/pandas dependency is required on the device.
    def draw_sensor_correlation_heatmap(self):

        ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.24, right=0.92, bottom=0.24, top=0.86)

        ax.set_facecolor(BG_COLOR)

        if len(self.time_data) < 2:
            ax.set_title(
                "Sensor Correlation Heatmap",
                color=FG_COLOR, fontsize=self.fpt(11)
            )
            ax.text(
                0.5, 0.5,
                "Not enough data yet -\nstart a test to collect readings.",
                color=FG_COLOR, ha="center", va="center",
                fontsize=self.fpt(9), transform=ax.transAxes
            )
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            return

        correlation = self._compute_correlation_matrix(self.sensor_data)

        image = ax.imshow(correlation, cmap="coolwarm", vmin=-1, vmax=1)

        ax.set_title(
            "MQ Sensor Correlation Heatmap",
            color=FG_COLOR, fontsize=self.fpt(11)
        )
        ax.set_xticks(range(NUM_SENSORS))
        ax.set_yticks(range(NUM_SENSORS))
        ax.set_xticklabels(SENSOR_NAMES, color=FG_COLOR, fontsize=self.fpt(8))
        ax.set_yticklabels(SENSOR_NAMES, color=FG_COLOR, fontsize=self.fpt(8))
        ax.tick_params(length=0)

        for spine in ax.spines.values():
            spine.set_visible(False)

        #Annotate each cell with its correlation value, matching the
        #annot=True behavior of the original seaborn heatmap.
        for row in range(NUM_SENSORS):
            for col in range(NUM_SENSORS):
                value = correlation[row][col]
                text_color = "white" if abs(value) > 0.5 else "black"
                ax.text(
                    col, row, f"{value:.2f}",
                    ha="center", va="center",
                    color=text_color, fontsize=self.fpt(9)
                )

        colorbar = self.figure.colorbar(image, ax=ax, fraction=0.05, pad=0.03)
        colorbar.outline.set_edgecolor(FG_COLOR)
        colorbar.ax.tick_params(
            color=FG_COLOR, labelcolor=FG_COLOR, length=0,
            labelsize=self.fpt(7)
        )

    #PEARSON CORRELATION MATRIX (pure Python, no numpy/pandas needed)
    @staticmethod
    def _compute_correlation_matrix(series_list):

        def pearson(a, b):
            n = len(a)
            mean_a = sum(a) / n
            mean_b = sum(b) / n

            cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
            std_a = math.sqrt(sum((x - mean_a) ** 2 for x in a))
            std_b = math.sqrt(sum((x - mean_b) ** 2 for x in b))

            if std_a == 0 or std_b == 0:
                return 0.0

            return cov / (std_a * std_b)

        size = len(series_list)
        return [
            [pearson(series_list[i], series_list[j]) for j in range(size)]
            for i in range(size)
        ]

    #TRAINING STATE PLOT (sample data for demonstration purposes only)
    def draw_training_state_plot(self):

        ax1 = self.figure.add_subplot(211)
        ax2 = self.figure.add_subplot(212)
        self.figure.subplots_adjust(hspace=0.7, right=0.95, bottom=0.15, top=0.9)

        epochs, gradient_values, val_fail_values = self._sample_training_state_data()

        for ax in (ax1, ax2):
            ax.set_facecolor(BG_COLOR)
            ax.tick_params(colors=FG_COLOR, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(FG_COLOR)

        #GRADIENT SUBPLOT
        ax1.set_yscale("log")
        ax1.plot(epochs, gradient_values, color="#4fd1c5", linewidth=1)
        ax1.set_title(
            f"Gradient = {gradient_values[-1]:.6f}, at epoch {epochs[-1]}",
            color=FG_COLOR,
            fontsize=10
        )
        ax1.set_ylabel("gradient", color=FG_COLOR, fontsize=9)

        #VALIDATION CHECKS SUBPLOT
        ax2.scatter(
            epochs,
            val_fail_values,
            color="#e6b800",
            edgecolor="#7a3b3b",
            s=18,
            zorder=3
        )
        ax2.plot(
            epochs,
            [0] * len(epochs),
            color="#4a6fa5",
            linewidth=1,
            zorder=1
        )
        ax2.set_title(
            f"Validation Checks = {max(val_fail_values)}, at epoch {epochs[-1]}",
            color=FG_COLOR,
            fontsize=10
        )
        ax2.set_ylabel("val fail", color=FG_COLOR, fontsize=9)
        ax2.set_xlabel(f"{epochs[-1]} Epochs", color=FG_COLOR, fontsize=9)

    #SAMPLE DATA GENERATOR FOR THE TRAINING STATE PLOT
    @staticmethod
    def _sample_training_state_data(num_epochs=253):

        epochs = list(range(num_epochs + 1))

        gradient_values = []
        value = 50.0

        for _ in epochs:
            value = max(
                0.005,
                value * random.uniform(0.85, 0.99) + random.uniform(-0.002, 0.002)
            )
            gradient_values.append(value)

        val_fail_values = []
        fails = 0

        for e in epochs:
            if e > 20 and random.random() < 0.15:
                fails = min(6, fails + 1)
            val_fail_values.append(random.randint(0, fails) if fails else 0)

        return epochs, gradient_values, val_fail_values

    #PERFORMANCE PLOT (sample data for demonstration purposes only)
    def draw_performance_plot(self):

        ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(right=0.95, bottom=0.18, top=0.88)

        epochs, train, validation, test, best_value, best_epoch = \
            self._sample_performance_data()

        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=FG_COLOR, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color(FG_COLOR)

        ax.set_yscale("log")
        ax.plot(epochs, train, color="#4a6fa5", linewidth=1, label="Train")
        ax.plot(epochs, validation, color="#4fd17a", linewidth=1, label="Validation")
        ax.plot(epochs, test, color="#e05c5c", linewidth=1, label="Test")
        ax.axhline(
            best_value,
            color=FG_COLOR,
            linewidth=1,
            linestyle=":",
            label="Best"
        )
        ax.plot(
            best_epoch,
            best_value,
            marker="o",
            markersize=10,
            markerfacecolor="none",
            markeredgecolor="#4fd17a",
            markeredgewidth=1.5
        )

        ax.set_title(
            f"Best Validation Performance is {best_value:.6f} at epoch {best_epoch}",
            color=FG_COLOR,
            fontsize=11
        )
        ax.set_ylabel("Cross-Entropy (crossentropy)", color=FG_COLOR, fontsize=9)
        ax.set_xlabel(f"{epochs[-1]} Epochs", color=FG_COLOR, fontsize=9)

        legend = ax.legend(loc="upper right", fontsize=8)
        legend.get_frame().set_facecolor(ACCENT_COLOR)
        for text in legend.get_texts():
            text.set_color(FG_COLOR)

    #SAMPLE DATA GENERATOR FOR THE PERFORMANCE PLOT
    @staticmethod
    def _sample_performance_data(num_epochs=253):

        epochs = list(range(num_epochs + 1))

        def decay_curve(start, floor, noise):
            values = []
            value = start
            for _ in epochs:
                value = max(floor, value * random.uniform(0.94, 0.99))
                values.append(value * random.uniform(1 - noise, 1 + noise))
            return values

        train = decay_curve(3.0, 0.015, 0.05)
        validation = decay_curve(3.0, 0.017, 0.07)
        test = decay_curve(3.2, 0.02, 0.09)

        best_epoch = min(
            range(len(validation)),
            key=lambda i: validation[i]
        )
        best_value = validation[best_epoch]

        return epochs, train, validation, test, best_value, best_epoch

    #CHARACTERISTIC PLOT (sample data for demonstration purposes only)
    def draw_characteristic_plot(self):

        ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(right=0.78, bottom=0.18, top=0.88)

        clusters = self._sample_characteristic_data()

        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=FG_COLOR, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color(FG_COLOR)

        ax.grid(True, color="#3a3a3a", linewidth=0.6)
        ax.set_axisbelow(True)

        for name, color, values in clusters:
            ax.scatter(
                range(1, len(values) + 1),
                values,
                color=color,
                label=name,
                s=40,
                edgecolor="none"
            )

        ax.set_title(
            "Characteristic plot based on the sensor values per cluster",
            color=FG_COLOR,
            fontsize=11
        )
        ax.set_xlabel("Sensors", color=FG_COLOR)
        ax.set_ylabel("Sensor Levels\n(Resistance)", color=FG_COLOR)
        ax.set_xlim(0, 8)

        legend = ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.02, 1),
            borderaxespad=0,
            fontsize=8
        )
        legend.get_frame().set_facecolor(ACCENT_COLOR)
        for text in legend.get_texts():
            text.set_color(FG_COLOR)

    #SAMPLE DATA GENERATOR FOR THE CHARACTERISTIC PLOT
    @staticmethod
    def _sample_characteristic_data():

        #Approximate baseline shapes per cluster, loosely modeled after
        #the reference figure, with light jitter added for variety.
        baselines = [
            ("Cluster 1", "#e6b800", [20, 20, 110, 480, 460, 350, 460]),
            ("Cluster 2", "#7fb3e6", [15, 15, 100, 500, 580, 370, 450]),
            ("Cluster 3", "#a0a0a0", [10, 10, 50, 190, 300, 160, 90]),
            ("Cluster 4", "#8a6d3b", [5, 5, 10, 20, 90, 20, 20])
        ]

        clusters = []

        for name, color, baseline in baselines:
            jittered = [
                max(0, value + random.uniform(-15, 15))
                for value in baseline
            ]
            clusters.append((name, color, jittered))

        return clusters

    #VOC HEATMAP - PEAK CODES (sample data for demonstration purposes only)
    def draw_voc_heatmap_peak_codes(self):

        row_labels = ["GF", "ABP", "AB", "LE"]
        col_labels = [
            "LY2/LG", "LY2/G", "LY2/AA", "LY2/Gh", "LY2/gCTl", "LY2/gCT",
            "T30/1", "P10/1", "P10/2", "P40/1", "T70/1", "T70/2",
            "PA/1", "PA/2", "P30/1", "P40/2", "P30/2", "T40/1", "TA/1"
        ]

        legend_labels = [
            "-2 x 10^12", "0.0", "2 x 10^12", "4 x 10^12",
            "6 x 10^12", "8 x 10^12", "1 x 10^13"
        ]
        colors = [
            "#e04040", "#9a9a9a", "#8fe0c8",
            "#e8e14a", "#5ad15a", "#1f6b2e", "#7a4a2a"
        ]

        data = self._sample_bin_indices(len(row_labels), len(col_labels))

        self._draw_bin_heatmap(
            data=data,
            row_labels=row_labels,
            col_labels=col_labels,
            colors=colors,
            legend_labels=legend_labels,
            title="VOC Heatmap - Peak Codes (sample data)"
        )

    #VOC HEATMAP - NAMED COMPOUNDS (sample data for demonstration purposes only)
    def draw_voc_heatmap_named_compounds(self):

        row_labels = ["ABP", "AB", "LE", "GF"]
        col_labels = [
            "2-Propanol", "Propanol", "Butanal-2-methyl", "Pentanal",
            "Propylacetate", "1-Butanol,3-methyl", "1-Butanol,2-methyl",
            "1-Pentanol", "Octane", "2,3-Butadienol", "4-Methyloctane",
            "Dimethylsulfone", "gamma-Valerolactone", "1-Octen-3-one",
            "2-Pentylfuran", "3-Octen-2-one", "d-Limonene",
            "Benzeneacetaldehyde", "gamma-Caprolactone", "gamma-Nonalactone",
            "2-Octenal-2-Butyl", "Linalool", "1-Dodecene", "Dodecane",
            "L-Camphor", "1-Hexenol", "3-Octenal", "1-Octen-3-ol",
            "3-Octanol", "Benzaldehyde", "Butanal-3-methyl"
        ]

        legend_labels = ["0.0", "5.0", "10.0", "15.0", "20.0", "25.0", "30.0"]
        colors = [
            "#e04040", "#4ecdc4", "#9a9a9a",
            "#e8e14a", "#8fe04a", "#2fae6a", "#155c2a"
        ]

        data = self._sample_bin_indices(len(row_labels), len(col_labels))

        self._draw_bin_heatmap(
            data=data,
            row_labels=row_labels,
            col_labels=col_labels,
            colors=colors,
            legend_labels=legend_labels,
            title="VOC Heatmap - Named Compounds (sample data)"
        )

    #SAMPLE DATA GENERATOR SHARED BY BOTH VOC HEATMAPS
    @staticmethod
    def _sample_bin_indices(num_rows, num_cols, num_bins=7):

        return [
            [random.randint(0, num_bins - 1) for _ in range(num_cols)]
            for _ in range(num_rows)
        ]

    #SHARED DISCRETE-COLOR HEATMAP RENDERER
    def _draw_bin_heatmap(self, data, row_labels, col_labels, colors,
                           legend_labels, title):

        ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.12, right=0.86, bottom=0.32, top=0.88)

        cmap = ListedColormap(colors)

        image = ax.imshow(
            data,
            cmap=cmap,
            vmin=-0.5,
            vmax=len(colors) - 0.5,
            aspect="auto"
        )

        ax.set_facecolor(BG_COLOR)
        ax.set_title(title, color=FG_COLOR, fontsize=11)

        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels(row_labels, color=FG_COLOR, fontstyle="italic", fontsize=10)

        ax.set_xticks(range(len(col_labels)))
        ax.set_xticklabels(
            col_labels, color=FG_COLOR, fontsize=7, rotation=90, ha="center"
        )

        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

        colorbar = self.figure.colorbar(
            image,
            ax=ax,
            ticks=range(len(colors)),
            fraction=0.05,
            pad=0.02
        )
        colorbar.ax.set_yticklabels(legend_labels, color=FG_COLOR, fontsize=8)
        colorbar.outline.set_edgecolor(FG_COLOR)
        colorbar.ax.tick_params(color=FG_COLOR, length=0)

    #PCA BIPLOT (sample data for demonstration purposes only)
    def draw_pca_biplot(self):

        ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.1, right=0.95, bottom=0.15, top=0.9)

        species_points, vectors = self._sample_pca_data()

        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=FG_COLOR, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color(FG_COLOR)

        ax.axhline(0, color="#c0504d", linewidth=1)
        ax.axvline(0, color="#c0504d", linewidth=1)

        for label, x, y in species_points:
            ax.scatter(x, y, color="#2f8f3f", s=40, zorder=3)
            ax.annotate(
                label,
                (x, y),
                textcoords="offset points",
                xytext=(6, 4),
                color=FG_COLOR,
                fontstyle="italic",
                fontsize=10
            )

        for label, x, y in vectors:
            ax.plot([0, x], [0, y], color="#4a6fa5", linewidth=0.8)
            ax.annotate(
                label,
                (x, y),
                textcoords="offset points",
                xytext=(3, 3),
                color=FG_COLOR,
                fontsize=6
            )

        ax.set_xlabel("PC 1: 66.28% (sample)", color=FG_COLOR)
        ax.set_ylabel("PC 2: 26.91% (sample)", color=FG_COLOR)
        ax.set_title("PCA Biplot (sample data)", color=FG_COLOR, fontsize=11)

    #SAMPLE DATA GENERATOR FOR THE PCA BIPLOT
    @staticmethod
    def _sample_pca_data(num_vectors=30):

        #Approximate quadrant positions loosely modeled after the
        #reference figure, with light jitter added for variety.
        species_baseline = [
            ("GF", -2.0, 4.1),
            ("AB", -2.7, -1.9),
            ("ABP", -2.1, -2.0),
            ("LE", 6.6, -0.1)
        ]

        species_points = [
            (label, x + random.uniform(-0.2, 0.2), y + random.uniform(-0.2, 0.2))
            for label, x, y in species_baseline
        ]

        vectors = []

        for i in range(1, num_vectors + 1):
            #Most vectors fan out to the right, a few point up-left,
            #matching the general shape of the reference figure.
            if random.random() < 0.15:
                angle = random.uniform(100, 170)
            else:
                angle = random.uniform(-40, 60)

            length = random.uniform(0.8, 2.4)
            x = length * math.cos(math.radians(angle))
            y = length * math.sin(math.radians(angle))
            vectors.append((f"C{i}", x, y))

        return species_points, vectors

    #STATIC SAMPLE DATASET SHARED BY ALL PROFILE COMPARISON PLOTS
    #Fixed values (not randomized) - a stable illustrative dataset.
    @staticmethod
    def _static_profile_data():

        categories = [
            ("GF", "#2a78d6", [420, 380, 460, 300]),
            ("ABP", "#eb6834", [180, 220, 160, 140]),
            ("AB", "#1baf7a", [500, 470, 510, 460]),
            ("LE", "#eda100", [350, 300, 330, 280])
        ]
        sensor_labels = ["Sensor 1", "Sensor 2", "Sensor 3", "Sensor 4"]

        return categories, sensor_labels

    #PROFILE RADAR CHART (static sample data)
    def draw_profile_radar_chart(self):

        categories, sensor_labels = self._static_profile_data()
        num_axes = len(sensor_labels)
        angles = [i / num_axes * 2 * math.pi for i in range(num_axes)]
        angles += angles[:1]

        ax = self.figure.add_subplot(111, projection="polar")
        self.figure.subplots_adjust(right=0.78, bottom=0.12, top=0.85)

        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=FG_COLOR)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(sensor_labels, color=FG_COLOR, fontsize=9)
        ax.set_rlabel_position(0)
        ax.tick_params(axis="y", colors=FG_COLOR, labelsize=7)
        ax.spines["polar"].set_color(FG_COLOR)
        ax.grid(color="#3a3a3a")

        for name, color, values in categories:
            plot_values = values + values[:1]
            ax.plot(angles, plot_values, color=color, linewidth=1.5, label=name)
            ax.fill(angles, plot_values, color=color, alpha=0.1)

        ax.set_title(
            "Sensor Profile Radar Chart (static sample)",
            color=FG_COLOR, fontsize=11, pad=20
        )

        legend = ax.legend(
            loc="upper left", bbox_to_anchor=(1.1, 1.1), fontsize=8
        )
        legend.get_frame().set_facecolor(ACCENT_COLOR)
        for text in legend.get_texts():
            text.set_color(FG_COLOR)

    #PROFILE GROUPED BAR CHART (static sample data)
    def draw_profile_grouped_bar_chart(self):

        categories, sensor_labels = self._static_profile_data()

        ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(right=0.82, bottom=0.15, top=0.88)

        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=FG_COLOR)
        for spine in ax.spines.values():
            spine.set_color(FG_COLOR)

        num_categories = len(categories)
        bar_width = 0.8 / num_categories
        x_positions = range(len(sensor_labels))

        for i, (name, color, values) in enumerate(categories):
            offsets = [
                x + (i - (num_categories - 1) / 2) * bar_width
                for x in x_positions
            ]
            ax.bar(offsets, values, width=bar_width, color=color, label=name)

        ax.set_xticks(list(x_positions))
        ax.set_xticklabels(sensor_labels, color=FG_COLOR)
        ax.set_ylabel("Sensor Value", color=FG_COLOR)
        ax.set_title(
            "Sensor Profile Grouped Bar Chart (static sample)",
            color=FG_COLOR, fontsize=11
        )

        legend = ax.legend(
            loc="upper left", bbox_to_anchor=(1.02, 1),
            borderaxespad=0, fontsize=8
        )
        legend.get_frame().set_facecolor(ACCENT_COLOR)
        for text in legend.get_texts():
            text.set_color(FG_COLOR)

    #PROFILE BOX PLOT (static sample data)
    def draw_profile_box_plot(self):

        #Fixed, non-random spreads per category for Sensor 1 -
        #illustrates variability within a category, not just the mean.
        box_data = [
            ("GF", [390, 405, 420, 435, 450], "#2a78d6"),
            ("ABP", [150, 170, 190, 200, 210], "#eb6834"),
            ("AB", [470, 490, 500, 510, 530], "#1baf7a"),
            ("LE", [320, 335, 350, 365, 380], "#eda100")
        ]

        ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.12, bottom=0.15, top=0.88, right=0.95)

        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=FG_COLOR)
        for spine in ax.spines.values():
            spine.set_color(FG_COLOR)

        box = ax.boxplot(
            [values for _, values, _ in box_data],
            labels=[name for name, _, _ in box_data],
            patch_artist=True,
            medianprops={"color": BG_COLOR}
        )

        for patch, (_, _, color) in zip(box["boxes"], box_data):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        for element in ("whiskers", "caps"):
            for line in box[element]:
                line.set_color(FG_COLOR)

        ax.set_ylabel("Sensor 1 Value", color=FG_COLOR)
        ax.set_title(
            "Sensor Profile Box Plot (static sample)",
            color=FG_COLOR, fontsize=11
        )

    #PROFILE PARALLEL COORDINATES (static sample data)
    def draw_profile_parallel_coordinates(self):

        categories, sensor_labels = self._static_profile_data()

        ax = self.figure.add_subplot(111)
        self.figure.subplots_adjust(right=0.82, bottom=0.15, top=0.88)

        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=FG_COLOR)
        for spine in ax.spines.values():
            spine.set_color(FG_COLOR)

        x_positions = range(len(sensor_labels))

        for name, color, values in categories:
            ax.plot(
                x_positions, values, color=color, marker="o",
                markersize=6, linewidth=1.5, label=name
            )

        ax.set_xticks(list(x_positions))
        ax.set_xticklabels(sensor_labels, color=FG_COLOR)
        ax.set_ylabel("Sensor Value", color=FG_COLOR)
        ax.set_title(
            "Sensor Profile Parallel Coordinates (static sample)",
            color=FG_COLOR, fontsize=11
        )

        legend = ax.legend(
            loc="upper left", bbox_to_anchor=(1.02, 1),
            borderaxespad=0, fontsize=8
        )
        legend.get_frame().set_facecolor(ACCENT_COLOR)
        for text in legend.get_texts():
            text.set_color(FG_COLOR)

    #RESET
    def reset_graph(self):

        self.running = False

        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        if self.timer_after_id is not None:
            self.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None

        self.time_data = []
        self.sensor_data = [[] for _ in range(NUM_SENSORS)]

        for i, label in enumerate(self.sensor_labels):
            label.config(text=f"{SENSOR_NAMES[i]}: ---")

        self.result_label.config(text="WAITING")
        self.timer_label.config(text="")
        self.status_label.config(
            text=(
                "Status: Arduino Connected"
                if self.hardware_connected
                else "Status: No Arduino (simulated)"
            )
        )

        self.redraw_graph()

    #SAVE
    def save_data(self):

        if not self.time_data:
            return

        filename = f"sensor_data_{int(time.time())}.csv"

        with open(filename, "w", newline="") as f:

            writer = csv.writer(f)

            writer.writerow(["Time", "Elapsed (mm:ss)"] + SENSOR_NAMES)

            for i in range(len(self.time_data)):

                writer.writerow(
                    [self.time_data[i], self.format_elapsed(self.time_data[i])]
                    + [self.sensor_data[s][i] for s in range(NUM_SENSORS)]
                )


#MAIN
root = tk.Tk()

app = ENoseApp(root)

root.mainloop()