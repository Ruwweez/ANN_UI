import tkinter as tk
from tkinter import ttk, messagebox
import time
import csv
import os

import serial
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# =========================
# ARDUINO / SENSOR SETTINGS
# =========================
PORT = "/dev/ttyACM0"
BAUD = 9600
DATA_FILE = "sensor_data.csv"

SENSOR_NAMES = ["MQ3", "MQ137", "MQ138"]


class ENoseApp:

    def __init__(self, root):

        self.root = root
        self.root.title("Mushroom E-Nose")
        self.root.geometry("1000x700")

        self.running = False
        self.start_time = time.time()
        self.arduino = None

        # TITLE
        title_label = ttk.Label(
            self.root,
            text="Mushroom E-Nose",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=10)

        # MAIN FRAME
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # SENSOR FRAME
        sensor_frame = tk.Frame(main_frame)
        sensor_frame.pack(fill="x", padx=20, pady=10)

        self.sensor_labels = []

        for sensor_name in SENSOR_NAMES:
            label = ttk.Label(
                sensor_frame,
                text=f"{sensor_name}: ---",
                font=("Arial", 12)
            )
            label.pack(side="left", padx=30)
            self.sensor_labels.append(label)

        # CLASSIFICATION FRAME
        classification_frame = tk.Frame(main_frame)
        classification_frame.pack(fill="x", padx=20, pady=10)

        self.result_label = ttk.Label(
            classification_frame,
            text="WAITING",
            font=("Arial", 14, "bold")
        )
        self.result_label.pack()

        # GRAPH FRAME
        graph_frame = tk.Frame(main_frame)
        graph_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.figure, self.ax = plt.subplots(figsize=(8, 3))

        self.canvas = FigureCanvasTkAgg(
            self.figure,
            master=graph_frame
        )
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # STATUS
        self.status_label = ttk.Label(
            self.root,
            text="Status: Stopped",
            font=("Arial", 12)
        )
        self.status_label.pack(pady=5)

        # BUTTONS
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5)

        ttk.Button(
            button_frame,
            text="Start",
            command=self.start_test
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame,
            text="Stop",
            command=self.stop_test
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame,
            text="Save Data",
            command=self.save_data
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame,
            text="Heatmap",
            command=self.show_heatmap
        ).pack(side="left", padx=5)

        # GRAPH / SESSION DATA
        self.time_data = []
        self.sensor_data = [[], [], []]

        # Close serial connection properly when window is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # =========================
    # START SENSOR READING
    # =========================
    def start_test(self):

        if self.running:
            return

        try:
            self.arduino = serial.Serial(
                PORT,
                BAUD,
                timeout=0.1
            )

            # Same startup delay used in sensor_reader.py
            time.sleep(2)

        except serial.SerialException as e:
            messagebox.showerror(
                "Connection Error",
                f"Could not connect to Arduino on {PORT}.\n\n{e}"
            )
            self.status_label.config(
                text="Status: Arduino connection failed"
            )
            return

        # Reset current session
        self.running = True
        self.start_time = time.time()
        self.time_data = []
        self.sensor_data = [[], [], []]

        self.prepare_data_file()

        self.status_label.config(
            text="Status: Connected / Testing"
        )

        self.result_label.config(
            text="ANALYZING"
        )

        self.update_data()

    # =========================
    # STOP SENSOR READING
    # =========================
    def stop_test(self):

        self.running = False

        if self.arduino is not None:
            try:
                self.arduino.close()
            except serial.SerialException:
                pass
            self.arduino = None

        self.status_label.config(
            text="Status: Test Stopped"
        )

        self.result_label.config(
            text="WAITING"
        )

    # =========================
    # PREPARE sensor_data.csv
    # =========================
    def prepare_data_file(self):

        # Add the header only when the file is new or empty.
        needs_header = (
            not os.path.exists(DATA_FILE)
            or os.path.getsize(DATA_FILE) == 0
        )

        if needs_header:
            with open(DATA_FILE, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(SENSOR_NAMES)

    # =========================
    # READ ARDUINO + UPDATE UI
    # =========================
    def update_data(self):

        if not self.running:
            return

        try:
            # Read all currently available serial lines.
            # Keeping only valid 3-value MQ readings.
            while (
                self.arduino is not None
                and self.arduino.in_waiting > 0
            ):

                line = (
                    self.arduino
                    .readline()
                    .decode("utf-8", errors="ignore")
                    .strip()
                )

                if not line:
                    continue

                values = line.split(",")

                if len(values) != 3:
                    continue

                try:
                    mq3 = int(values[0])
                    mq137 = int(values[1])
                    mq138 = int(values[2])
                except ValueError:
                    continue

                sensor_values = [mq3, mq137, mq138]
                current_time = time.time() - self.start_time

                self.time_data.append(current_time)

                for i in range(3):
                    self.sensor_data[i].append(sensor_values[i])

                    self.sensor_labels[i].config(
                        text=f"{SENSOR_NAMES[i]}: {sensor_values[i]}"
                    )

                # Automatically save each valid reading,
                # matching the original sensor_reader.py behavior.
                with open(DATA_FILE, "a", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerow(sensor_values)
                    file.flush()

                self.update_graph()

        except serial.SerialException as e:
            self.running = False
            self.status_label.config(
                text="Status: Arduino Disconnected"
            )

            messagebox.showerror(
                "Serial Error",
                str(e)
            )

            if self.arduino is not None:
                try:
                    self.arduino.close()
                except serial.SerialException:
                    pass
                self.arduino = None

            return

        # Non-blocking Tkinter loop
        self.root.after(100, self.update_data)

    # =========================
    # UPDATE REAL-TIME GRAPH
    # =========================
    def update_graph(self):

        self.ax.clear()

        self.ax.set_title("MQ Sensor Data Over Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Sensor Values")

        for i in range(3):
            self.ax.plot(
                self.time_data,
                self.sensor_data[i],
                label=SENSOR_NAMES[i]
            )

        self.ax.legend()
        self.figure.tight_layout()
        self.canvas.draw_idle()

    # =========================
    # SAVE CURRENT SESSION COPY
    # =========================
    def save_data(self):

        if not self.time_data:
            messagebox.showwarning(
                "Save Data",
                "No sensor data has been collected yet."
            )
            return

        filename = f"sensor_data_{int(time.time())}.csv"

        with open(filename, "w", newline="") as file:

            writer = csv.writer(file)

            writer.writerow([
                "Time",
                "MQ3",
                "MQ137",
                "MQ138"
            ])

            for i in range(len(self.time_data)):

                writer.writerow([
                    self.time_data[i],
                    self.sensor_data[0][i],
                    self.sensor_data[1][i],
                    self.sensor_data[2][i]
                ])

        messagebox.showinfo(
            "Save Data",
            f"Session saved as:\n{filename}"
        )

    # =========================
    # GENERATE + DISPLAY HEATMAP
    # =========================
    def show_heatmap(self):

        try:
            data = pd.read_csv(DATA_FILE)

        except FileNotFoundError:
            messagebox.showwarning(
                "Heatmap",
                "No sensor_data.csv file exists yet."
            )
            return

        # Same columns and processing used in heatmap.py
        required_columns = ["MQ3", "MQ137", "MQ138"]

        if not all(column in data.columns for column in required_columns):
            messagebox.showerror(
                "Heatmap Error",
                "sensor_data.csv does not contain MQ3, MQ137, and MQ138 columns."
            )
            return

        data = data[required_columns]
        data = data.apply(pd.to_numeric, errors="coerce")
        data = data.dropna()

        if len(data) < 2:
            messagebox.showwarning(
                "Heatmap",
                "At least 2 valid sensor readings are needed."
            )
            return

        correlation = data.corr()

        heatmap_window = tk.Toplevel(self.root)
        heatmap_window.title("MQ Sensor Correlation Heatmap")
        heatmap_window.geometry("760x600")

        heatmap_figure, heatmap_ax = plt.subplots(
            figsize=(7, 5)
        )

        sns.heatmap(
            correlation,
            annot=True,
            cmap="coolwarm",
            vmin=-1,
            vmax=1,
            ax=heatmap_ax
        )

        heatmap_ax.set_title(
            "MQ Sensor Correlation Heatmap"
        )

        heatmap_figure.tight_layout()

        # Save the image just like the original heatmap.py
        heatmap_figure.savefig(
            "sensor_heatmap.png",
            dpi=300
        )

        heatmap_canvas = FigureCanvasTkAgg(
            heatmap_figure,
            master=heatmap_window
        )

        heatmap_canvas.draw()

        heatmap_canvas.get_tk_widget().pack(
            fill="both",
            expand=True
        )

        # Keep references attached to the window
        # so Tkinter/Matplotlib does not garbage-collect them.
        heatmap_window.figure = heatmap_figure
        heatmap_window.canvas = heatmap_canvas

    # =========================
    # CLOSE APPLICATION
    # =========================
    def on_close(self):

        self.running = False

        if self.arduino is not None:
            try:
                self.arduino.close()
            except serial.SerialException:
                pass

        self.root.destroy()


# =========================
# MAIN
# =========================
root = tk.Tk()
app = ENoseApp(root)
root.mainloop()
