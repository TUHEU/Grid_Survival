from pathlib import Path
import pygame


def _sort_key(path: Path):
    try:
        return int(path.stem)
    except ValueError:
        return path.stem


def load_frames_from_directory(directory: Path, scale=None, limit=None):
    """Load and optionally scale every frame inside *directory*."""
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Animation directory not found: {directory}")

    frame_paths = sorted(directory.glob("*.png"), key=_sort_key)
    if not frame_paths:
        raise ValueError(f"No .png frames found inside {directory}")

    if limit:
        frame_paths = frame_paths[:limit]

    frames = []
    for path in frame_paths:
        surface = pygame.image.load(path.as_posix()).convert_alpha()
        if scale:
            if isinstance(scale, (tuple, list)):
                surface = pygame.transform.smoothscale(surface, scale)
            else:
                new_size = (
                    int(surface.get_width() * scale),
                    int(surface.get_height() * scale),
                )
                surface = pygame.transform.smoothscale(surface, new_size)
        frames.append(surface)

    return frames


class SpriteAnimation:
    """Minimal animation controller for sprite frame lists."""

    def __init__(self, frames, frame_duration=0.1, loop=True):
        if not frames:
            raise ValueError("SpriteAnimation requires at least one frame")

        self.frames = frames
        self.frame_duration = frame_duration
        self.loop = loop
        self.current_index = 0
        self.time_accumulator = 0.0

    def update(self, dt: float):
        self.time_accumulator += dt
        while self.time_accumulator >= self.frame_duration:
            self.time_accumulator -= self.frame_duration
            self.current_index += 1
            if self.current_index >= len(self.frames):
                if self.loop:
                    self.current_index = 0
                else:
                    self.current_index = len(self.frames) - 1
                    break

    def reset(self):
        self.current_index = 0
        self.time_accumulator = 0.0

    @property
    def image(self):
        return self.frames[self.current_index]
