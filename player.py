"""
player.py — Player class.

Movement model
──────────────
Week 1 keeps movement simple:
  • Arrow keys move the player left / right / up / down by one full tile.
  • Movement is tweened (smooth slide) between tile centres using PLAYER_SPEED.
  • Gravity: when the tile underfoot disappears the player falls off-screen
    and becomes eliminated.

States
──────
IDLE      – standing on a tile, waiting for input.
MOVING    – sliding from one tile centre to an adjacent one.
FALLING   – no tile underfoot; falling downward off-screen.
ELIMINATED– has fallen completely off-screen.
"""

import pygame

from settings import (
    GRID_COLS,
    GRID_ROWS,
    ISO_GRID_OFFSET_X,
    ISO_GRID_OFFSET_Y,
    ISO_TILE_H,
    ISO_TILE_W,
    PLAYER_COLOR,
    PLAYER_FALL_SPEED,
    PLAYER_SIZE,
    PLAYER_SPEED,
)
from tile import DISAPPEARED

# ── Player states ────────────────────────────────────────────────────────────
IDLE       = "idle"
MOVING     = "moving"
FALLING    = "falling"
ELIMINATED = "eliminated"

# Key bindings for player 1
_MOVE_KEYS = {
    pygame.K_LEFT:  (-1,  0),
    pygame.K_RIGHT: ( 1,  0),
    pygame.K_UP:    ( 0, -1),
    pygame.K_DOWN:  ( 0,  1),
}


def _tile_centre(col: int, row: int) -> tuple[float, float]:
    """Return the isometric screen centre of a tile's top diamond face."""
    return (
        ISO_GRID_OFFSET_X + (col - row) * (ISO_TILE_W // 2),
        ISO_GRID_OFFSET_Y + (col + row) * (ISO_TILE_H // 2) + ISO_TILE_H // 2,
    )


class Player:
    """Single player-controlled character."""

    def __init__(self, start_col: int = 4, start_row: int = 2):
        self.col = start_col
        self.row = start_row

        cx, cy = _tile_centre(self.col, self.row)
        self.x: float = cx   # current pixel x (centre)
        self.y: float = cy   # current pixel y (centre)

        # Tween target
        self._target_x: float = cx
        self._target_y: float = cy

        self.state: str = IDLE
        self._fall_speed: float = PLAYER_FALL_SPEED

        # Survival time (seconds alive)
        self.alive_time: float = 0.0

    # ── Computed rect for drawing / collision ────────────────────────────────

    @property
    def rect(self) -> pygame.Rect:
        half = PLAYER_SIZE // 2
        return pygame.Rect(
            int(self.x) - half,
            int(self.y) - half,
            PLAYER_SIZE,
            PLAYER_SIZE,
        )

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def is_alive(self) -> bool:
        return self.state != ELIMINATED

    def reset(self, start_col: int = 4, start_row: int = 2) -> None:
        self.col = start_col
        self.row = start_row
        cx, cy = _tile_centre(self.col, self.row)
        self.x = cx
        self.y = cy
        self._target_x = cx
        self._target_y = cy
        self.state = IDLE
        self.alive_time = 0.0

    # ── Input ────────────────────────────────────────────────────────────────

    def handle_input(self, keys, grid) -> None:
        """Process keyboard input; only when IDLE and a tile is underfoot."""
        if self.state != IDLE:
            return

        for key, (dcol, drow) in _MOVE_KEYS.items():
            if keys[key]:
                new_col = self.col + dcol
                new_row = self.row + drow
                target_tile = grid.get_tile(new_col, new_row)

                # Only step onto a solid (non-disappeared) in-bounds tile
                if target_tile and target_tile.is_solid:
                    self.col = new_col
                    self.row = new_row
                    self._target_x, self._target_y = _tile_centre(new_col, new_row)
                    self.state = MOVING
                break  # process at most one direction per frame

    # ── Update ───────────────────────────────────────────────────────────────

    def update(self, dt: float, grid) -> None:
        if self.state == ELIMINATED:
            return

        # Count survival time
        self.alive_time += dt

        if self.state == MOVING:
            self._update_tween(dt)

        elif self.state == IDLE:
            self._check_fall(grid)

        elif self.state == FALLING:
            self._update_fall(dt)

    def _update_tween(self, dt: float) -> None:
        """Slide towards the target tile centre; snap when close enough."""
        dx = self._target_x - self.x
        dy = self._target_y - self.y
        dist = (dx * dx + dy * dy) ** 0.5
        step = PLAYER_SPEED * dt

        if dist <= step:
            self.x = self._target_x
            self.y = self._target_y
            self.state = IDLE
        else:
            self.x += dx / dist * step
            self.y += dy / dist * step

    def _check_fall(self, grid) -> None:
        """Start falling if the tile under the player's feet disappeared."""
        current_tile = grid.get_tile(self.col, self.row)
        if current_tile is None or current_tile.state == DISAPPEARED:
            self.state = FALLING

    def _update_fall(self, dt: float) -> None:
        """Move downward; mark eliminated when fully off-screen."""
        self._fall_speed += 600 * dt          # gravity acceleration
        self.y += self._fall_speed * dt
        # 800 px below 720 is safely off-screen
        if self.y > 800 + PLAYER_SIZE:
            self.state = ELIMINATED

    # ── Draw ─────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface) -> None:
        if self.state == ELIMINATED:
            return

        # Draw player as a small isometric diamond flush on the tile top face.
        ix = int(self.x)
        iy = int(self.y)
        hw = ISO_TILE_W // 4   # diamond half-width  (32 px)
        hh = ISO_TILE_H // 4   # diamond half-height (16 px)

        pts = [
            (ix,      iy - hh),   # top
            (ix + hw, iy),        # right
            (ix,      iy + hh),   # bottom
            (ix - hw, iy),        # left
        ]
        pygame.draw.polygon(surface, PLAYER_COLOR, pts)
        pygame.draw.polygon(surface, (255, 255, 255), pts, 2)
