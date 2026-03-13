import pygame

from assets import load_background_surface, load_tilemap_surface
from player import Player
from settings import (
    BACKGROUND_COLOR,
    DEBUG_DRAW_WALKABLE,
    DEBUG_WALKABLE_COLOR,
    TARGET_FPS,
    WINDOW_SIZE,
    WINDOW_TITLE,
)


class Game:
    """Main game application wrapper."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption(WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True

        self.background_surface = load_background_surface(WINDOW_SIZE)
        self.map_surface, self.tmx_data, self.colliders = load_tilemap_surface(
            WINDOW_SIZE
        )
        self.player = Player()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def update(self, dt: float, keys):
        if keys[pygame.K_ESCAPE]:
            self.running = False
            return

        self.player.update(dt, keys, self.colliders)

    def draw(self):
        self.screen.fill(BACKGROUND_COLOR)
        if self.background_surface:
            self.screen.blit(self.background_surface, (0, 0))
        if self.map_surface:
            self.screen.blit(self.map_surface, (0, 0))
        self._draw_walkable_debug()
        self.player.draw(self.screen)
        pygame.display.flip()

    def _draw_walkable_debug(self):
        if not DEBUG_DRAW_WALKABLE or not self.colliders:
            return

        for rect in self.colliders:
            pygame.draw.rect(self.screen, DEBUG_WALKABLE_COLOR, rect, 1)

    def run(self):
        while self.running:
            dt = self.clock.tick(TARGET_FPS) / 1000.0
            self.handle_events()
            keys = pygame.key.get_pressed()
            self.update(dt, keys)
            self.draw()

        pygame.quit()
