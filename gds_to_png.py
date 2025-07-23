import gdspy
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Load the GDS file
lib = gdspy.GdsLibrary()
lib.read_gds("test.gds")

# Get the top cell
top_cell = lib.top_level()[0]

# Get all polygons and layers
polygons = top_cell.get_polygons(by_spec=True)

# Create plot
fig, ax = plt.subplots()
colors = ['red', 'green', 'blue', 'orange', 'purple', 'cyan']

for i, ((layer, datatype), poly_list) in enumerate(polygons.items()):
    color = colors[i % len(colors)]
    for points in poly_list:
        polygon = patches.Polygon(points, closed=True, facecolor=color, edgecolor='black', linewidth=0.5, alpha=0.6)
        ax.add_patch(polygon)

ax.set_aspect('equal')
ax.autoscale()
plt.axis('off')
plt.tight_layout()
plt.savefig("gds_image.png", dpi=300)
plt.show()
