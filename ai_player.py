"""Basic AI controller for the animated map-based player."""

import random

import pygame

from player import Player
from settings import (
    AI_DECISION_INTERVAL,
    AI_EDGE_MARGIN_WEIGHT,
    AI_LOOKAHEAD_DISTANCE,
    PLAYER_START_POS,
    PLAYER_SPEED,
)

# Spread AIs so they don't all start stacked on the same tile
_AI_SPAWN_OFFSETS = [
    (-120, -80), (120, -80), (-120,  80), (120,  80),
    (   0,-120), (  0, 120), (-200,   0), (200,   0),
]


class AIPlayer(Player):
    """Simple rule-based AI that wanders safely on the walkable surface."""

    def __init__(self, position=None, profile=None, player_index: int = 1):
        # Stagger spawns so AIs don't stack
        slot = (player_index - 1) % len(_AI_SPAWN_OFFSETS)
        dx, dy = _AI_SPAWN_OFFSETS[slot]
        cx, cy = PLAYER_START_POS
        spawn = position or (cx + dx, cy + dy)

        super().__init__(position=spawn, player_index=player_index)
        self.is_ai = True
        self._rng = random.Random(player_index)
        self._decision_timer = 0.0
        self._current_direction = pygame.Vector2(0, 0)
        self._desired_direction = pygame.Vector2(0, 0)
        self._smooth_speed = 5.0

        # Behaviour params (defaults = passive wanderer)
        self._chase_weight       = 0.0
        self._sabotage_radius    = 0.0
        self._use_power          = False
        self._power_use_interval = 15.0
        self._power_timer        = 0.0
        self._decision_interval  = AI_DECISION_INTERVAL
        self._lookahead          = AI_LOOKAHEAD_DISTANCE

        # Injected by _wire_ai_players
        self._target_player = None
        self._tile_manager  = None

        # Apply profile if provided
        if profile is not None:
            self._apply_profile(profile)

    def reset(self):
        super().reset()
        self._decision_timer = 0.0
        self._power_timer    = 0.0
        self._current_direction.update(0, 0)
        self._desired_direction.update(0, 0)

    def _apply_profile(self, profile):
        import math as _m
        from settings import PLAYER_SPEED as _PS
        self.speed              = _PS * getattr(profile, 'speed_multiplier', 1.0) * self.power.speed_multiplier
        self._decision_interval = getattr(profile, 'decision_interval', AI_DECISION_INTERVAL)
        self._lookahead         = getattr(profile, 'lookahead', AI_LOOKAHEAD_DISTANCE)
        self._chase_weight      = getattr(profile, 'chase_weight', 0.0)
        self._sabotage_radius   = getattr(profile, 'sabotage_radius', 0.0)
        self._use_power         = getattr(profile, 'use_power', False)
        self._power_use_interval= getattr(profile, 'power_use_interval', 15.0)

    def configure(self, profile):
        """Called by game._wire_ai_players after construction."""
        self._apply_profile(profile)

    def set_target(self, player):
        self._target_player = player

    def set_tile_manager(self, manager):
        self._tile_manager = manager

    def update_ai(self, dt: float, walkable_mask, walkable_bounds):
        self._decision_timer += dt

        needs_new_direction = self._decision_timer >= self._decision_interval
        if self._current_direction.length_squared() > 0:
            probe = self.position + self._current_direction * self._lookahead
            if not self._is_over_platform(probe, walkable_mask):
                needs_new_direction = True

        if needs_new_direction:
            self._decision_timer = 0.0
            self._desired_direction = self._choose_direction(walkable_mask, walkable_bounds)

        # 🔥 Smooth interpolation toward desired direction
        self._current_direction = self._current_direction.lerp(
            self._desired_direction,
            min(1, dt * self._smooth_speed)
        )

        # Prevent jitter
        if self._current_direction.length() < 0.05:
            self._current_direction.update(0, 0)

        # Normalize movement
        move_dir = self._current_direction
        if move_dir.length_squared() > 0:
            move_dir = move_dir.normalize()

        self._update_with_move_vector(
            dt, move_dir, walkable_mask, walkable_bounds, jump_pressed=False,
        )

        # Tick power and activate if ready + enabled
        self.power.update(dt, self)
        self._power_timer += dt
        if self._use_power and self._power_timer >= self._power_use_interval:
            if self.power.ready:
                self.power.try_activate(self)
                self._power_timer = 0.0

        # Sabotage: trigger WARNING on tiles near human player
        if self._sabotage_radius > 0 and self._target_player and self._tile_manager:
            self._try_sabotage()

    def _choose_direction(self, walkable_mask, walkable_bounds) -> pygame.Vector2:
        candidates = [
            pygame.Vector2(0, 0),
            pygame.Vector2(1, 0),   pygame.Vector2(-1, 0),
            pygame.Vector2(0, 1),   pygame.Vector2(0, -1),
            pygame.Vector2(1, 1).normalize(),  pygame.Vector2(-1, 1).normalize(),
            pygame.Vector2(1, -1).normalize(), pygame.Vector2(-1, -1).normalize(),
        ]
        scored = [(self._score_direction(d, walkable_mask, walkable_bounds), d)
                  for d in candidates]
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][0]
        return self._rng.choice([d for s, d in scored if s == best])

    def _score_direction(self, direction: pygame.Vector2, walkable_mask, walkable_bounds) -> float:
        probe = self.position
        if direction.length_squared() > 0:
            probe = self.position + direction.normalize() * self._lookahead

        if not self._is_over_platform(probe, walkable_mask):
            return -10000.0

        score = 100.0

        if direction.length_squared() > 0:
            further = probe + direction.normalize() * self._lookahead
            if self._is_over_platform(further, walkable_mask):
                score += 35.0

        if walkable_bounds is not None:
            feet = self._feet_rect(probe)
            margin = min(
                feet.left  - walkable_bounds.left,
                walkable_bounds.right  - feet.right,
                feet.top   - walkable_bounds.top,
                walkable_bounds.bottom - feet.bottom,
            )
            score += float(margin) * AI_EDGE_MARGIN_WEIGHT

        # Chase human player
        if self._chase_weight > 0 and self._target_player and direction.length_squared() > 0:
            to_target = self._target_player.position - self.position
            dist = to_target.length()
            if dist > 1:
                alignment = direction.dot(to_target / dist)
                score += alignment * self._chase_weight * 80.0

        if direction.length_squared() == 0:
            score -= 8.0
        if (direction.length_squared() > 0
                and self._current_direction.length_squared() > 0
                and abs(direction.angle_to(self._current_direction)) < 30):
            score += 5.0
        score += self._rng.uniform(0, 3)
        return score

    def _try_sabotage(self):
        """Trigger WARNING on a tile near the human player."""
        if self._decision_timer > 0.05:
            return
        import math as _m
        from tile_system import TileState
        tx = self._target_player.position.x
        ty = self._target_player.position.y
        cands = [t for t in self._tile_manager.tiles.values()
                 if t.state == TileState.NORMAL
                 and _m.hypot(t.pixel_x - tx, t.pixel_y - ty) <= self._sabotage_radius]
        if cands:
            self._rng.choice(cands).set_warning()