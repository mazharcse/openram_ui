# import gdsfactory as gf

# # Load GDS layout
# c = gf.import_gds("test.gds")

# # Save to SVG (vector, supports color)
# c.write_svg("layout.svg")

# # Optional: convert SVG to PNG using cairosvg
# import cairosvg
# cairosvg.svg2png(url="layout.svg", write_to="layout.png")

import gdsfactory as gf
import cairosvg

# Load the GDS file into a gdsfactory Component
component = gf.import_gds("test.gds")

# Write to SVG (colorful, layer-based layout)
component.write_svg("layout.svg")

# Convert to PNG if needed
cairosvg.svg2png(url="layout.svg", write_to="layout.png")

