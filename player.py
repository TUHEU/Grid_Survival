import pygame

from animation import SpriteAnimation, load_frames_from_directory
from settings import (
    PLAYER_ANIMATION_PATHS,
    PLAYER_DEFAULT_DIRECTION,
    PLAYER_FRAME_DURATION,
    PLAYER_SCALE,
    PLAYER_SPEED,
    PLAYER_START_POS,
)


class Player:
    """Animated player entity with directional movement."""

    def __init__(self, position=PLAYER_START_POS):
        self.position = pygame.Vector2(position)
        self.speed = PLAYER_SPEED
        self.state = "idle"
        self.facing = PLAYER_DEFAULT_DIRECTION
        self.animations = self._load_animations()
        self.current_animation = self.animations[self.state][self.facing]
        self.rect = self.current_animation.image.get_rect(center=position)

    def _load_animations(self):
        animations = {}
        for state, dirs in PLAYER_ANIMATION_PATHS.items():
            animations[state] = {}
            for direction, path in dirs.items():
                frames = load_frames_from_directory(path, scale=PLAYER_SCALE)
                animations[state][direction] = SpriteAnimation(
                    frames, frame_duration=PLAYER_FRAME_DURATION
                )
        return animations

    def _set_state(self, state: str, direction: str):
        if self.state == state and self.facing == direction:
            return

        self.state = state
        self.facing = direction
        self.current_animation = self.animations[state][direction]
        self.current_animation.reset()

    def _input_vector(self, keys) -> pygame.Vector2:
        direction = pygame.Vector2(0, 0)
        if keys[pygame.K_w]:
            direction.y -= 1
        if keys[pygame.K_s]:
            direction.y += 1
        if keys[pygame.K_a]:
            direction.x -= 1
        if keys[pygame.K_d]:
            direction.x += 1
        return direction

    def _determine_facing(self, direction: pygame.Vector2) -> str:
        if direction.y < 0:
            return "up"
        if direction.y > 0:
            return "down"
        if direction.x < 0:
            return "left"
        if direction.x > 0:
            return "right"
        return self.facing

    def update(self, dt: float, keys):
        move_vector = self._input_vector(keys)

        if move_vector.length_squared() > 0:
            facing = self._determine_facing(move_vector)
            move_vector = move_vector.normalize() * self.speed * dt
            self.position += move_vector
            self._set_state("run", facing)
        else:
            self._set_state("idle", self.facing)

        self.current_animation.update(dt)
        self.rect = self.current_animation.image.get_rect(
            center=(round(self.position.x), round(self.position.y))
        )

    def draw(self, surface: pygame.Surface):
        surface.blit(self.current_animation.image, self.rect.topleft)
