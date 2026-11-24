# Generate stylesheet with GNOME SVG icons as CSS variables.
#
# Fetch icons from official git repos and convert them to inline CSS variables
# with light and dark color variants for Firefox without modifying UI CSS.
#
# Git is required to run the script.
#
# Partially inspired by https://gitlab.gnome.org/World/design/icon-library/-/blob/master/update-icons.py

import json
import logging
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TypedDict
from urllib.parse import quote

ABS_PATH = Path(__file__).resolve().parent
SRC_PATH = ABS_PATH / "src"
ICONS_FILE = ABS_PATH / "icons.json"
CSS_FILE = ABS_PATH / "icons.css"
ICONS_REPO_URL = "https://gitlab.gnome.org/GNOME/adwaita-icon-theme.git"
ICONS_REPO_PATH = SRC_PATH / "adwaita-icon-theme"
ICONS_KIT_REPO_URL = (
    "https://gitlab.gnome.org/Teams/Design/icon-development-kit-www.git"
)
ICONS_KIT_REPO_PATH = SRC_PATH / "icon-development-kit-www"
ICONS_DEV_KIT_REPO_URL = (
    "https://gitlab.gnome.org/Teams/Design/icon-development-kit.git"
)
ICONS_DEV_KIT_REPO_PATH = SRC_PATH / "icon-development-kit"

LIGHT_ICON_COLOR = "#2f2f2f"
DARK_ICON_COLOR = "#ffffff"

ET.register_namespace("", "http://www.w3.org/2000/svg")


class IconsDefinition(TypedDict):
    icons: list[str]


def sync_repo(repo_url: str, repo_path: Path) -> None:
    """Clone the repository into src if missing, otherwise pull latest changes."""
    if not repo_path.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, repo_path.name],
            cwd=SRC_PATH,
            check=True,
        )
    else:
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo_path,
            check=True,
        )


def write_icon_vars(css, icons_svg: dict[str, str]) -> None:
    for name, svg in icons_svg.items():
        css.write(f'\t--gnome-icon-{name}: url("data:image/svg+xml,{svg}");\n')


def main():
    SRC_PATH.mkdir(parents=True, exist_ok=True)
    sync_repo(ICONS_REPO_URL, ICONS_REPO_PATH)
    sync_repo(ICONS_KIT_REPO_URL, ICONS_KIT_REPO_PATH)
    sync_repo(ICONS_DEV_KIT_REPO_URL, ICONS_DEV_KIT_REPO_PATH)

    # Get icons name to path mappings
    icon_paths = {
        **lookup_icons(ICONS_KIT_REPO_PATH / "img" / "symbolic"),  # Extra GNOME icons kit
        **lookup_icons(ICONS_REPO_PATH / "Adwaita" / "symbolic"),  # Core GNOME icons
        **lookup_icons(
            ICONS_DEV_KIT_REPO_PATH / "icons", require_symbolic=False
        ),  # Icon development kit
        **lookup_icons(ABS_PATH / "custom", False),  # Custom icons
    }

    # Load definition of icons needed by the theme
    with open(ICONS_FILE, "r") as f:
        icons_def: IconsDefinition = json.load(f)

    # Process icons SVGs for CSS
    icons_svg_light: dict[str, str] = {}
    icons_svg_dark: dict[str, str] = {}
    for icon in icons_def["icons"]:
        if icon not in icon_paths:
            logging.warning(f"No icon file found for '{icon}'")
            continue

        icon_path = icon_paths[icon]
        icons_svg_light[icon] = quote(
            process_svg(icon_path, LIGHT_ICON_COLOR), safe=" =:/'"
        )
        icons_svg_dark[icon] = quote(
            process_svg(icon_path, DARK_ICON_COLOR), safe=" =:/'"
        )

    # Write CSS file
    with open(CSS_FILE, "w") as css:
        css.write(":root {\n")
        write_icon_vars(css, icons_svg_light)
        css.write("}\n")
        if icons_svg_dark:
            # Dark mode variants for all icons without modifying Firefox UI CSS
            css.write("\n@media (prefers-color-scheme: dark) {\n")
            css.write(":root {\n")
            write_icon_vars(css, icons_svg_dark)
            css.write("}\n")
            css.write("}\n")


def lookup_icons(
    icons_folder: Path, has_subdirs=True, require_symbolic=True
) -> dict[str, Path]:
    """Finds all symbolic icons in a folder and maps their name to their Path."""
    lookup: dict[str, Path] = {}

    if require_symbolic:
        glob_pattern = "**/*-symbolic.svg" if has_subdirs else "*-symbolic.svg"
    else:
        glob_pattern = "**/*.svg" if has_subdirs else "*.svg"

    for path in icons_folder.glob(glob_pattern):
        name = path.stem if require_symbolic else f"{path.stem}-symbolic"
        lookup[name] = path

    return lookup


def process_svg(filename: Path, icon_color: str) -> str:
    """
    Process SVG's XML to be one liner and set icon color for light/dark mode
    """
    tree = ET.parse(filename)
    root = tree.getroot()

    # Apply target color to fills (excluding none) and strokes
    for tag in ("{http://www.w3.org/2000/svg}g", "{http://www.w3.org/2000/svg}path"):
        for elem in root.iter(tag):
            fill = elem.attrib.get("fill")
            if fill and fill != "none":
                elem.set("fill", icon_color)
            if "stroke" in elem.attrib:
                elem.set("stroke", icon_color)

    # Strip line breaks and indentation
    for elem in root.iter("*"):
        if elem.text is not None:
            elem.text = elem.text.strip()
        if elem.tail is not None:
            elem.tail = elem.tail.strip()

    text = ET.tostring(root, "unicode")
    text = text.replace('"', "'")  # Use single quotes

    return text


main()
