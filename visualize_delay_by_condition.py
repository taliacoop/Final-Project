import csv
import matplotlib.pyplot as plt

# Read CSV file
csv_file = 'avg_delay_by_condition.csv'
conditions = []
delays = []
flight_counts = []

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        conditions.append(row['condition'])
        delays.append(float(row['average_delay']))
        flight_counts.append(int(row['flight_count']))

# Create visualization
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(conditions, delays, color='steelblue', alpha=0.7)

# Add value labels on bars
for i, (bar, delay, count) in enumerate(zip(bars, delays, flight_counts)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{delay:.1f} min\n(n={count})',
            ha='center', va='bottom', fontsize=9)

ax.set_xlabel('Weather Condition', fontsize=12, fontweight='bold')
ax.set_ylabel('Average Departure Delay (minutes)', fontsize=12, fontweight='bold')
ax.set_title('Average Departure Delay by Weather Condition', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3, linestyle='--')

plt.xticks(rotation=45, ha='right')
plt.tight_layout()

# Save figure
output_file = 'avg_delay_by_condition.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"Visualization saved to {output_file}")
plt.close()

