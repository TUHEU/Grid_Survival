from pathlib import Path

BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "Assets"

MAP_PATH = ASSETS_DIR / "maps" / "level_1.tmx"
BACKGROUND_PATH = ASSETS_DIR / "Background" / "background.jpg"

WINDOW_SIZE = (1280, 720)
WINDOW_TITLE = "GRID SURVIVAL"
BACKGROUND_COLOR = (18, 18, 22)
TARGET_FPS = 60

PLAYER_SPRITE_DIR = ASSETS_DIR / "Characters" / "Caveman" / "running" / "Front - Running"
PLAYER_FRAME_DURATION = 1 / 24  # seconds per frame
PLAYER_SCALE = 1 # set to tuple like (48, 64) if you prefer explicit sizing
PLAYER_START_POS = (WINDOW_SIZE[0] // 2, WINDOW_SIZE[1] // 2)
