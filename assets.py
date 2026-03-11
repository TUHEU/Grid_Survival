import math
import pygame

from settings import BACKGROUND_PATH, MAP_PATH

try:
    from pytmx.util_pygame import load_pygame
except ImportError:  # pragma: no cover - informs developer about missing dependency
    load_pygame = None


def _calculate_surface_size(tmx_data):
    if tmx_data.orientation == "isometric":
        width = (tmx_data.width + tmx_data.height) * (tmx_data.tilewidth / 2)
        height = (tmx_data.width + tmx_data.height) * (tmx_data.tileheight / 2)
    else:
        width = tmx_data.width * tmx_data.tilewidth
        height = tmx_data.height * tmx_data.tileheight

    return math.ceil(width), math.ceil(height)


def _tile_to_pixel(x, y, layer, tmx_data):
    layer_offset_x = getattr(layer, "offsetx", 0)
    layer_offset_y = getattr(layer, "offsety", 0)
    tile_offset = getattr(tmx_data, "tileoffset", (0, 0)) or (0, 0)
    tile_offset_x, tile_offset_y = tile_offset

    if tmx_data.orientation == "isometric":
        half_width = tmx_data.tilewidth / 2
        half_height = tmx_data.tileheight / 2
        origin_x = tmx_data.height * half_width
        pixel_x = (x - y) * half_width + origin_x
        pixel_y = (x + y) * half_height
    else:
        pixel_x = x * tmx_data.tilewidth
        pixel_y = y * tmx_data.tileheight

    pixel_x += layer_offset_x + tile_offset_x
    pixel_y += layer_offset_y + tile_offset_y
    return int(round(pixel_x)), int(round(pixel_y))


def _render_tmx_to_surface(tmx_data) -> pygame.Surface:
    """Draw all visible tiles from the TMX data onto a surface."""
    map_width, map_height = _calculate_surface_size(tmx_data)
    surface = pygame.Surface((map_width, map_height), pygame.SRCALPHA)

    for layer in tmx_data.visible_layers:
        if hasattr(layer, "tiles"):
            for x, y, image in layer.tiles():
                pos = _tile_to_pixel(x, y, layer, tmx_data)
                surface.blit(image, pos)

    return surface


def load_tilemap_surface(window_size):
    """Load and scale the TMX tilemap to the requested size.

    Returns a tuple of (scaled_surface, tmx_data) so callers can reuse metadata.
    """
    if load_pygame is None:
        print("Install pytmx (pip install pytmx) to render Tiled maps.")
        return None, None

    if not MAP_PATH.exists():
        print(f"Map file not found: {MAP_PATH}")
        return None, None

    tmx_data = load_pygame(MAP_PATH.as_posix())
    raw_surface = _render_tmx_to_surface(tmx_data)
    scaled_surface = pygame.transform.smoothscale(raw_surface, window_size)
    return scaled_surface, tmx_data


def load_background_surface(window_size):
    """Load and scale the background image if it exists."""
    if not BACKGROUND_PATH.exists():
        print(f"Background image not found: {BACKGROUND_PATH}")
        return None

    image = pygame.image.load(BACKGROUND_PATH.as_posix()).convert()
    return pygame.transform.smoothscale(image, window_size)
