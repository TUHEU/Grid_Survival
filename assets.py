import math
import pygame

from settings import (
    BACKGROUND_PATH,
    MAP_PATH,
    WALKABLE_LAYER_NAMES,
    WALKABLE_OBJECT_CLASS_NAMES,
)

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


def _build_colliders(
    tmx_data,
    layer_names=None,
    object_class_names=None,
    scale_x=1.0,
    scale_y=1.0,
):
    colliders = []
    target_layers = {name.lower() for name in (layer_names or []) if name}
    target_classes = {name.lower() for name in (object_class_names or []) if name}

    if target_layers:
        for layer in tmx_data.layers:
            if getattr(layer, "name", "").lower() not in target_layers:
                continue
            if not hasattr(layer, "tiles"):
                continue

            for x, y, _ in layer.tiles():
                px, py = _tile_to_pixel(x, y, layer, tmx_data)
                rect = pygame.Rect(
                    int(round(px * scale_x)),
                    int(round(py * scale_y)),
                    int(math.ceil(tmx_data.tilewidth * scale_x)),
                    int(math.ceil(tmx_data.tileheight * scale_y)),
                )
                colliders.append(rect)

    if target_classes:
        for layer in tmx_data.layers:
            if not hasattr(layer, "objects"):
                continue
            layer_offset_x = getattr(layer, "offsetx", 0)
            layer_offset_y = getattr(layer, "offsety", 0)

            for obj in layer:
                obj_class = (
                    getattr(obj, "class", None)
                    or getattr(obj, "type", None)
                    or ""
                ).lower()
                if obj_class not in target_classes:
                    continue

                width = getattr(obj, "width", 0)
                height = getattr(obj, "height", 0)
                rect = pygame.Rect(
                    int(round((obj.x + layer_offset_x) * scale_x)),
                    int(round((obj.y + layer_offset_y) * scale_y)),
                    int(math.ceil(width * scale_x)),
                    int(math.ceil(height * scale_y)),
                )
                colliders.append(rect)

    return colliders


def load_tilemap_surface(window_size):
    """Load the TMX tilemap, scale it, and build collider rects.

    Returns a tuple of (scaled_surface, tmx_data, colliders).
    """
    if load_pygame is None:
        print("Install pytmx (pip install pytmx) to render Tiled maps.")
        return None, None, []

    if not MAP_PATH.exists():
        print(f"Map file not found: {MAP_PATH}")
        return None, None, []

    tmx_data = load_pygame(MAP_PATH.as_posix())
    raw_surface = _render_tmx_to_surface(tmx_data)
    if raw_surface.get_width() == 0 or raw_surface.get_height() == 0:
        scale_x = scale_y = 1.0
    else:
        scale_x = window_size[0] / raw_surface.get_width()
        scale_y = window_size[1] / raw_surface.get_height()

    scaled_surface = pygame.transform.smoothscale(raw_surface, window_size)
    colliders = _build_colliders(
        tmx_data,
        WALKABLE_LAYER_NAMES,
        WALKABLE_OBJECT_CLASS_NAMES,
        scale_x,
        scale_y,
    )
    return scaled_surface, tmx_data, colliders


def load_background_surface(window_size):
    """Load and scale the background image if it exists."""
    if not BACKGROUND_PATH.exists():
        print(f"Background image not found: {BACKGROUND_PATH}")
        return None

    image = pygame.image.load(BACKGROUND_PATH.as_posix()).convert()
    return pygame.transform.smoothscale(image, window_size)
