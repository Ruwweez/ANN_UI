import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load sensor data
data = pd.read_csv("sensor_data.csv")

# Keep only numeric sensor columns
data = data[["MQ3", "MQ137", "MQ138"]]

# Convert values to numbers
data = data.apply(pd.to_numeric, errors="coerce")

# Remove invalid/missing rows
data = data.dropna()

# Calculate correlation
correlation = data.corr()

# Create heatmap
plt.figure(figsize=(7, 5))

sns.heatmap(
    correlation,
    annot=True,
    cmap="coolwarm",
    vmin=-1,
    vmax=1
)

plt.title("MQ Sensor Correlation Heatmap")
plt.tight_layout()

plt.savefig("sensor_heatmap.png", dpi=300)

print("Heatmap saved as sensor_heatmap.png")
