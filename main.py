from pathlib import Path
import pygame

try:
    from pytmx.util_pygame import load_pygame
except ImportError:  # pragma: no cover - guidance for missing dependency
    load_pygame = None

BASE_DIR = Path(__file__).parent
MAP_PATH = BASE_DIR / "Assets" / "maps" / "level 1.tmx"
BACKGROUND_PATH = BASE_DIR / "Assets" / "Background" / "background.jpg"
BACKGROUND_COLOR = (18, 18, 22)
WINDOW_SIZE = (1280, 720)
TARGET_FPS = 60


def load_tilemap(map_path: Path):
    """Load the Tiled map if pytmx is available and the file exists."""
    if load_pygame is None:
        print("Install pytmx (pip install pytmx) to render Tiled maps.")
        return None

    resolved_path = Path(map_path)
    if not resolved_path.exists():
        print(f"Map file not found: {resolved_path}")
        return None

    return load_pygame(resolved_path.as_posix())


def draw_tilemap(surface: pygame.Surface, tmx_data):
    """Render all visible tile layers to the target surface."""
    for layer in tmx_data.visible_layers:
        if hasattr(layer, "tiles"):
            for x, y, image in layer.tiles():
                surface.blit(image, (x * tmx_data.tilewidth, y * tmx_data.tileheight))


def main():
    pygame.init()

    # Initialize a tiny display first so pygame surfaces can convert correctly during TMX load.
    pygame.display.set_mode((1, 1))
    tmx_data = load_tilemap(MAP_PATH)
    if tmx_data:
        map_width = tmx_data.width * tmx_data.tilewidth
        map_height = tmx_data.height * tmx_data.tileheight
        map_surface = pygame.Surface((map_width, map_height), pygame.SRCALPHA)
        draw_tilemap(map_surface, tmx_data)
    else:
        map_width, map_height = 1280, 720
        map_surface = None

    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("GRID SURVIVAL")

    background_surface = None
    if BACKGROUND_PATH.exists():
        bg_image = pygame.image.load(BACKGROUND_PATH.as_posix())
        background_surface = pygame.transform.smoothscale(
            bg_image.convert(), WINDOW_SIZE
        )
    else:
        print(f"Background image not found: {BACKGROUND_PATH}")

    scaled_map_surface = (
        pygame.transform.smoothscale(map_surface, WINDOW_SIZE)
        if map_surface
        else None
    )

    clock = pygame.time.Clock()
    running = True

    while running:
        dt = clock.tick(TARGET_FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            running = False

        screen.fill(BACKGROUND_COLOR)
        if background_surface:
            screen.blit(background_surface, (0, 0))
        if scaled_map_surface:
            screen.blit(scaled_map_surface, (0, 0))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()