import serial
import csv
import time

PORT = "/dev/ttyACM0"
BAUD = 9600

arduino = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)

with open("sensor_data.csv", "a", newline="") as file:

    writer = csv.writer(file)

    # Header
    writer.writerow(["MQ3", "MQ137", "MQ138"])

    print("Arduino connected")
    print("Collecting sensor data...")

    try:
        while True:
            line = arduino.readline().decode("utf-8").strip()

            if line:
                values = line.split(",")

                if len(values) == 3:
                    mq3 = int(values[0])
                    mq137 = int(values[1])
                    mq138 = int(values[2])

                    print(
                        f"MQ-3: {mq3} | "
                        f"MQ-137: {mq137} | "
                        f"MQ-138: {mq138}"
                    )

                    writer.writerow([mq3, mq137, mq138])
                    file.flush()

    except KeyboardInterrupt:
        print("\nData collection stopped.")

arduino.close()
