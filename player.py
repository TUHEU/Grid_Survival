import pygame

from animation import SpriteAnimation, load_frames_from_directory
from settings import (
    PLAYER_FRAME_DURATION,
    PLAYER_SCALE,
    PLAYER_SPRITE_DIR,
    PLAYER_START_POS,
)


class Player:
    """Animated player entity."""

    def __init__(self, position=PLAYER_START_POS):
        frames = load_frames_from_directory(PLAYER_SPRITE_DIR, scale=PLAYER_SCALE)
        self.animation = SpriteAnimation(frames, frame_duration=PLAYER_FRAME_DURATION)
        self.position = pygame.Vector2(position)
        self.rect = self.animation.image.get_rect(center=position)

    def update(self, dt: float):
        self.animation.update(dt)
        self.rect.center = (round(self.position.x), round(self.position.y))

    def draw(self, surface: pygame.Surface):
        surface.blit(self.animation.image, self.rect.topleft)
