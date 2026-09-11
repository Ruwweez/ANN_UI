import tkinter as tk
from tkinter import ttk
import random
import time
import csv

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class ENoseApp:

    def __init__(self, root):

        self.root = root
        self.root.title("Mushroom E-Nose")
        self.root.geometry("1000x700")

        self.running = False
        self.start_time = time.time()

        #TITLE
        title_label = ttk.Label(
            self.root,
            text="Mushroom E-Nose",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=10)

        #MAIN FRAME
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        #SENSOR FRAME
        sensor_frame = tk.Frame(main_frame)
        sensor_frame.pack(fill="x", padx=20, pady=10)

        self.sensor_labels = []

        for i in range(4):
            label = ttk.Label(
                sensor_frame,
                text=f"Sensor {i + 1}: ---",
                font=("Arial", 12)
            )
            label.pack(side="left", padx=30)
            self.sensor_labels.append(label)

        #CLASSIFICATION FRAME
        classification_frame = tk.Frame(main_frame)
        classification_frame.pack(fill="x", padx=20, pady=10)

        self.result_label = ttk.Label(
            classification_frame,
            text="WAITING",
            font=("Arial", 14, "bold")
        )
        self.result_label.pack()

        #GRAPH FRAME
        graph_frame = tk.Frame(main_frame)
        graph_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.figure, self.ax = plt.subplots(figsize=(8, 3))

        self.canvas = FigureCanvasTkAgg(
            self.figure,
            master=graph_frame
        )
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        #STATUS
        self.status_label = ttk.Label(
            self.root,
            text="Status: Stopped",
            font=("Arial", 12)
        )
        self.status_label.pack(pady=5)

        #BUTTONS
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

        #GRAPH DATA
        self.time_data = []
        self.sensor_data = [[], [], [], []]

    #START
    def start_test(self):

        self.running = True
        self.start_time = time.time()

        self.status_label.config(
            text="Status: Connected / Testing"
        )

        self.result_label.config(
            text="ANALYZING"
        )

        self.update_data()

    #STOP
    def stop_test(self):

        self.running = False

        self.status_label.config(
            text="Status: Test Stopped"
        )

    #UPDATE
    def update_data(self):

        if not self.running:
            return

        current_time = time.time() - self.start_time
        self.time_data.append(current_time)

        # Temporary simulated sensor values
        values = [
            random.randint(350, 600),
            random.randint(300, 550),
            random.randint(400, 650),
            random.randint(250, 500)
        ]

        for i in range(4):

            self.sensor_data[i].append(values[i])

            self.sensor_labels[i].config(
                text=f"Sensor {i + 1}: {values[i]}"
            )

        #UPDATE GRAPH
        self.ax.clear()
        self.ax.set_title("Sensor Data Over Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Sensor Values")

        for i in range(4):
            self.ax.plot(
                self.time_data,
                self.sensor_data[i],
                label=f"Sensor {i + 1}"
            )

        self.ax.legend()
        self.canvas.draw()

        self.root.after(1000, self.update_data)

    #SAVE
    def save_data(self):

        if not self.time_data:
            return

        filename = f"sensor_data_{int(time.time())}.csv"

        with open(filename, "w", newline="") as f:

            writer = csv.writer(f)

            writer.writerow([
                "Time",
                "Sensor 1",
                "Sensor 2",
                "Sensor 3",
                "Sensor 4"
            ])

            for i in range(len(self.time_data)):

                writer.writerow([
                    self.time_data[i],
                    self.sensor_data[0][i],
                    self.sensor_data[1][i],
                    self.sensor_data[2][i],
                    self.sensor_data[3][i]
                ])


#MAIN
root = tk.Tk()

app = ENoseApp(root)

root.mainloop()