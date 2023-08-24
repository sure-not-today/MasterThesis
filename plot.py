import matplotlib.pyplot as plt
import pandas as pd

# Load the CSV data using pandas
contdf = pd.read_csv('mcmd2/container_log.csv')
dronedf = pd.read_csv('mcmd2/dronelog1.csv')

# Extract data from the DataFrame
dates = pd.to_datetime(contdf['Date'])
values = df['Value']

# Create the plot
plt.figure(figsize=(10, 6))
plt.plot(dates, values, marker='o', linestyle='-')
plt.title('CSV Data Plot')
plt.xlabel('Date')
plt.ylabel('Value')
plt.grid(True)
plt.xticks(rotation=45)
plt.tight_layout()

# Show the plot
plt.show()