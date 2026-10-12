#!/usr/bin/env python3
"""
Embed PNG assets as Base64 into explorer_standalone.html
"""

import base64
import os
import re

ASSETS_DIR = "assets"
HTML_FILE = "explorer_standalone.html"

def encode_image(path):
    """Read image and return Base64 encoded data URL."""
    with open(path, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode('ascii')
    return f'data:image/png;base64,{b64}'


def generate_embedded_data():
    """Generate JavaScript with embedded image data."""
    lines = []

    # Read data.js for HEADS info
    with open(os.path.join(ASSETS_DIR, "data.js"), 'r') as f:
        data_js = f.read()

    lines.append("// === EMBEDDED DATA START ===")
    lines.append("// Auto-generated data for variant explorer\n")

    # Copy HEADS definition
    lines.append(data_js)

    # FRAMEWORKS (20 head framework images)
    lines.append("\nconst FRAMEWORKS = {")
    for i in range(20):
        path = os.path.join(ASSETS_DIR, f"framework_{i:02d}.png")
        data_url = encode_image(path)
        lines.append(f'  {i}: "{data_url}",')
    lines.append("};")

    # EYES (20 eye variants)
    lines.append("\nconst EYES = {")
    for i in range(20):
        path = os.path.join(ASSETS_DIR, "variants", "eyes", f"eyes_{i:02d}.png")
        data_url = encode_image(path)
        lines.append(f'  {i}: "{data_url}",')
    lines.append("};")

    # NOSES (20 nose variants)
    lines.append("\nconst NOSES = {")
    for i in range(20):
        path = os.path.join(ASSETS_DIR, "variants", "noses", f"noses_{i:02d}.png")
        data_url = encode_image(path)
        lines.append(f'  {i}: "{data_url}",')
    lines.append("};")

    # MOUTHS (20 mouth variants)
    lines.append("\nconst MOUTHS = {")
    for i in range(20):
        path = os.path.join(ASSETS_DIR, "variants", "mouths", f"mouths_{i:02d}.png")
        data_url = encode_image(path)
        lines.append(f'  {i}: "{data_url}",')
    lines.append("};")

    lines.append("// === EMBEDDED DATA END ===")

    return "\n".join(lines)


def update_html():
    """Update the HTML file with new embedded data."""
    with open(HTML_FILE, 'r') as f:
        html = f.read()

    # Find and replace the embedded data section
    pattern = r'// === EMBEDDED DATA START ===.*?// === EMBEDDED DATA END ==='
    new_data = generate_embedded_data()

    if re.search(pattern, html, re.DOTALL):
        html = re.sub(pattern, new_data, html, flags=re.DOTALL)
        print("Replaced existing embedded data.")
    else:
        print("ERROR: Could not find embedded data section in HTML!")
        return False

    with open(HTML_FILE, 'w') as f:
        f.write(html)

    print(f"Updated {HTML_FILE} successfully!")
    return True


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    update_html()
