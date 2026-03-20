import math
import pygame

from ai_player import AIPlayer
from assets import load_background_surface, load_tilemap_surface
from audio import get_audio
from collision_manager import CollisionManager
from environment import LevelEnvironment
from level_config import get_level, MAX_LEVEL, ArenaShape
from orbs import OrbManager
from player import Player
from water import AnimatedWater
from tile_system import TMXTileManager, TileState
from hazards import HazardManager
from ui import GameHUD, EliminationScreen
from settings import (
    BACKGROUND_COLOR,
    DEBUG_DRAW_WALKABLE,
    DEBUG_VISUALS_ENABLED,
    DEBUG_WALKABLE_COLOR,
    MODE_VS_COMPUTER,
    MODE_LOCAL_MULTIPLAYER,
    TARGET_FPS,
    USE_AI_PLAYER,
    WINDOW_SIZE,
    WINDOW_TITLE,
    SOUND_PLAYER_FALL,
    SOUND_PLAYER_ELIMINATED,
    SOUND_PLAYER_VICTORY,
    SOUND_SPLASH,
    SOUND_COUNTDOWN_BEEP,
    SOUND_COUNTDOWN_GO,
)


class GameManager:
    """Main game application wrapper with full feature integration."""

    def __init__(
        self,
        screen=None,
        clock=None,
        player_name: str = "Player",
        game_mode: str = MODE_VS_COMPUTER,
        selected_characters: list[str] | None = None,
        start_level: int = 1,
        forced_arena: "ArenaShape | None" = None,
        num_players: int = 1,
    ):
        if screen is None or clock is None:
            pygame.init()
        self.screen = screen or pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption(WINDOW_TITLE)
        self.clock = clock or pygame.time.Clock()
        self.running = True
        self.player_name = player_name
        self.game_mode = game_mode
        self.selected_characters = selected_characters or []
        self.num_players = num_players

        # ── Level state ────────────────────────────────────────────────────
        self.current_level_number = max(1, min(start_level, MAX_LEVEL))
        self.level_config = get_level(self.current_level_number)
        self._forced_arena = forced_arena   # player-chosen arena overrides level default
        self._level_complete = False
        self._level_transition_timer = 0.0
        self._level_transition_duration = 2.5  # seconds of fanfare before next level
        self._level_banner_alpha = 0
        self._countdown_timer = 0.0
        self._countdown_beeps_fired = set()

        # Load assets
        self.background_surface = load_background_surface(WINDOW_SIZE)
        (
            self.map_surface,
            self.tmx_data,
            self.walkable_mask,
            self.walkable_bounds,
            self.map_scale_x,
            self.map_scale_y,
            self.map_offset,
        ) = load_tilemap_surface(WINDOW_SIZE)
        self.walkable_debug_surface = None
        self.original_walkable_mask = self.walkable_mask.copy() if self.walkable_mask else None

        # Initialize game systems with level config
        offset = self.map_offset if self.map_offset else (0, 0)
        scale_x = self.map_scale_x if self.map_scale_x else 1.0
        scale_y = self.map_scale_y if self.map_scale_y else 1.0
        self.tile_manager = TMXTileManager(
            self.tmx_data, scale_x, scale_y, offset,
            level_config=self.level_config,
            forced_arena=self._forced_arena,
        )
        self.collision_manager = CollisionManager()
        self.hazard_manager = HazardManager(
            self.collision_manager,
            level_config=self.level_config,
        )
        self.hud = GameHUD()
        self.water = AnimatedWater()
        self.environment = LevelEnvironment(self.current_level_number)
        self.orb_manager = OrbManager(self.current_level_number)

        # Initialize players
        self.players = []
        self.eliminated_players = []
        self.elimination_screen = None
        self._build_players()

        self.hud.set_player_info(player_name, len(self.players), len(self.players))
        self.hud.set_level(self.current_level_number, self.level_config.name)

        self.game_over = False
        self.audio = get_audio()
        self.audio.play_music()
        self.audio.preload_directory()

        # Wire AI players to targets and tile manager
        self._wire_ai_players()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_l:
                    for player in self.players:
                        player.reset()
                elif event.key == pygame.K_r and self.game_over:
                    self._restart_game()

    def update(self, dt: float, keys):
        if keys[pygame.K_ESCAPE]:
            self.running = False
            return

        # Level-complete transition
        if self._level_complete:
            self._level_transition_timer += dt
            self._level_banner_alpha = min(255, int(self._level_transition_timer / self._level_transition_duration * 255))
            if self._level_transition_timer >= self._level_transition_duration:
                self._load_next_level()
            return

        if self.game_over:
            if self.elimination_screen:
                self.elimination_screen.update(dt)
            return

        # Grace-period countdown beeps (3, 2, 1, GO)
        grace = self.tile_manager.grace_period - self.tile_manager.grace_timer
        for beat in (3, 2, 1):
            if grace <= beat and beat not in self._countdown_beeps_fired:
                self._countdown_beeps_fired.add(beat)
                self.audio.play_sfx(SOUND_COUNTDOWN_BEEP, volume=0.6, max_instances=1)
        if grace <= 0 and 0 not in self._countdown_beeps_fired:
            self._countdown_beeps_fired.add(0)
            self.audio.play_sfx(SOUND_COUNTDOWN_GO, volume=0.7, max_instances=1)

        # Update game systems
        self.environment.update(dt)
        self.water.update(dt)
        self.tile_manager.update(dt)

        # Update walkable mask with disappeared/crumbling tiles
        self.walkable_mask = self.tile_manager.get_updated_walkable_mask(self.original_walkable_mask)

        self.hazard_manager.update(dt)
        self.hud.update(dt)

        # Update orb manager (spawning, collection, buffs)
        alive_list = [p for p in self.players if p not in self.eliminated_players]
        self.orb_manager.update(dt, self.walkable_bounds, alive_list, self)

        # Apply orb freeze: pause tile timers and slow hazards
        if hasattr(self, '_orb_freeze_timer'):
            self.tile_manager.disappear_timer = max(
                0.0, self.tile_manager.disappear_timer - dt
            )
            from tile_system import TileState as _TS
            for _tile in self.tile_manager.tiles.values():
                if _tile.state == _TS.WARNING:
                    _tile.warning_timer = max(0.0, _tile.warning_timer - dt)
            for _blt in self.hazard_manager.bullets:
                _blt.speed = max(15, _blt.speed * 0.5)

        # Update players
        for player in self.players[:]:
            if player in self.eliminated_players:
                continue

            # Reset per-frame immunity flag before power apply
            if hasattr(player, '_immune_to_hazards'):
                player._immune_to_hazards = False

            was_falling_before = player.is_falling()

            if player.is_ai:
                player.update_ai(dt, self.walkable_mask, self.walkable_bounds)
            else:
                player.update(dt, keys, self.walkable_mask, self.walkable_bounds)

            # Let the player's power interact with the game world
            if hasattr(player, 'power'):
                player.power.apply_to_game(self)

            # Play fall sound when player starts falling
            if not was_falling_before and player.is_falling():
                self.audio.play_sfx(SOUND_PLAYER_FALL)

            # Check water contact
            self._check_water_contact(player)

            # Check hazard collisions — skip if power or orb grants immunity
            immune = getattr(player, '_immune_to_hazards', False)
            if not immune and self.hazard_manager.check_player_collision(player):
                absorbed = False
                # Check orb shield first
                if getattr(player, '_orb_shield', False):
                    player._orb_shield = False
                    absorbed = True
                    try:
                        from settings import SOUND_POWER_KNIGHT
                        self.audio.play_sfx(SOUND_POWER_KNIGHT, volume=0.6, max_instances=1)
                    except Exception:
                        pass
                # Then check power armour
                if not absorbed and hasattr(player, 'power') and hasattr(player.power, 'on_hazard_hit'):
                    absorbed = player.power.on_hazard_hit()
                if not absorbed:
                    self._eliminate_player(player, "hit by hazard")

            # Check if player fell off screen
            if player.position.y > WINDOW_SIZE[1] + 100:
                self._eliminate_player(player, "fell off")

        # Update player count in HUD
        alive_count = len(self.players) - len(self.eliminated_players)
        self.hud.set_player_info(self.player_name, alive_count, len(self.players))

        # Check win condition: human player is last one standing (all AIs eliminated)
        human_players = [p for p in self.players if not p.is_ai]
        ai_players = [p for p in self.players if p.is_ai]
        all_ai_eliminated = all(p in self.eliminated_players for p in ai_players)
        human_alive = any(p not in self.eliminated_players for p in human_players)

        if ai_players and all_ai_eliminated and human_alive and not self.game_over:
            self._trigger_level_complete()
        elif alive_count == 0 or (human_players and all(p in self.eliminated_players for p in human_players)):
            self._trigger_game_over()

    def draw(self):
        self.screen.fill(BACKGROUND_COLOR)

        # Draw procedural level environment (sky, terrain, particles)
        self.environment.draw_background(self.screen)

        # Draw water (terrain-edge animation, if theme active)
        self.water.draw(self.screen)

        # Determine which players draw behind map
        players_behind = [p for p in self.players if p.draws_behind_map()]
        players_front = [p for p in self.players if not p.draws_behind_map()]

        # Draw players behind map
        for player in players_behind:
            player.draw(self.screen)

        # Draw TMX map with tile disappearance
        self._draw_tmx_map_with_tiles()

        # Draw warning/crumble overlays and debris particles
        self.tile_manager.draw_warning_overlays(self.screen)

        # Draw walkable debug overlay
        self._draw_walkable_debug()

        # Draw players in front of map
        for player in players_front:
            player.draw(self.screen)

        # Draw hazards
        self.hazard_manager.draw(self.screen)

        # Draw magic orbs
        self.orb_manager.draw(self.screen)

        # Draw HUD
        self.hud.draw(self.screen)

        # Draw environment foreground effects (embers, mist, arcs)
        self.environment.draw_foreground(self.screen)

        # Draw per-player power indicators
        self._draw_power_hud()

        # Draw level-complete banner
        if self._level_complete:
            self._draw_level_complete_banner()

        # Draw elimination screen if game over
        if self.elimination_screen:
            self.elimination_screen.draw(self.screen)

        pygame.display.flip()

    def _check_water_contact(self, player):
        if not self.water.has_surface():
            return
        if player.is_drowning():
            return
        if not player.is_falling():
            return

        feet_rect = player.get_feet_rect()
        if feet_rect.bottom < self.water.surface_top():
            return

        player.start_drowning(self.water.surface_top(), player.fall_draw_behind)
        self.water.trigger_splash(player.rect.centerx)

        if player not in self.eliminated_players:
            self._eliminate_player(player, "drowned")

    def _eliminate_player(self, player, reason: str):
        """Mark a player as eliminated."""
        if player not in self.eliminated_players:
            self.eliminated_players.append(player)
            self.audio.play_sfx(SOUND_PLAYER_ELIMINATED, volume=0.80, max_instances=2)
            print(f"Player eliminated: {reason}")

    def _trigger_level_complete(self):
        """Human player outlasted all AIs — advance to next level."""
        if self._level_complete:
            return
        self._level_complete = True
        self._level_transition_timer = 0.0
        bonus = self.level_config.score_bonus if self.level_config else 0
        self.hud.add_score(bonus)
        self.audio.play_sfx(SOUND_PLAYER_VICTORY, volume=0.85, max_instances=1)

    def _trigger_game_over(self, victory: bool = False):
        """Trigger game over state."""
        if not self.game_over:
            self.game_over = True
            alive = [p for p in self.players if p not in self.eliminated_players]
            if alive or victory:
                self.audio.play_sfx(SOUND_PLAYER_VICTORY, volume=0.85, max_instances=1)
            self.elimination_screen = EliminationScreen(
                self.player_name,
                self.hud.survival_time,
                self.hud.score,
                "victory" if victory else "eliminated"
            )
            self.elimination_screen.show()

    def _build_players(self):
        """Construct human and AI players.
        VS Computer: human gets 2 powers; Level N spawns N AIs with escalating power count.
        Local Multiplayer: each human player gets 2 powers; no AI spawned.
        """
        from powers import get_ai_powers

        if self.game_mode == MODE_VS_COMPUTER:
            primary_char = self._character_choice(0)
            self.players.append(Player(
                character_name=primary_char, player_index=0, power_count=2
            ))
            if USE_AI_PLAYER:
                # Level N = N AI opponents
                n_ais = self.current_level_number
                for i in range(n_ais):
                    ai = AIPlayer(player_index=i + 1)
                    # Give AI level-appropriate powers
                    ai_powers = get_ai_powers(self.current_level_number)
                    ai.powers = ai_powers
                    self.players.append(ai)

        elif self.game_mode == MODE_LOCAL_MULTIPLAYER:
            # Define control schemes for up to 4 local players
            control_schemes = [
                {'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a,
                 'right': pygame.K_d, 'jump': pygame.K_SPACE, 'power': pygame.K_q,
                 'cycle': pygame.K_TAB},
                {'up': pygame.K_UP, 'down': pygame.K_DOWN, 'left': pygame.K_LEFT,
                 'right': pygame.K_RIGHT, 'jump': pygame.K_RSHIFT, 'power': pygame.K_p,
                 'cycle': pygame.K_RCTRL},
                {'up': pygame.K_i, 'down': pygame.K_k, 'left': pygame.K_j,
                 'right': pygame.K_l, 'jump': pygame.K_o, 'power': pygame.K_COMMA,
                 'cycle': pygame.K_SEMICOLON},
                {'up': pygame.K_t, 'down': pygame.K_g, 'left': pygame.K_f,
                 'right': pygame.K_h, 'jump': pygame.K_y, 'power': pygame.K_SLASH,
                 'cycle': pygame.K_PERIOD},
            ]
            # Create players based on num_players
            for i in range(self.num_players):
                controls = control_schemes[i] if i < len(control_schemes) else control_schemes[0]
                char_idx = i % len(self.selected_characters) if self.selected_characters else 0
                self.players.append(Player(
                    controls=controls,
                    character_name=self._character_choice(char_idx) if self.selected_characters else "Caveman",
                    player_index=i,
                    power_count=2
                ))
        else:
            self.players.append(Player(
                character_name=self._character_choice(0), player_index=0, power_count=2
            ))

    def _wire_ai_players(self):
        """Give AI players a reference to the human player, tile manager, and configure behaviour."""
        human = next((p for p in self.players if not p.is_ai), None)
        ai_profile = self.level_config.ai if self.level_config else None
        for p in self.players:
            if p.is_ai:
                if human:
                    p.set_target(human)
                p.set_tile_manager(self.tile_manager)
                # Apply level-specific behaviour tuning
                if ai_profile and hasattr(p, 'configure'):
                    p.configure(ai_profile)
        if human and self.level_config:
            self.tile_manager.set_target_player(human)

    def _restart_game(self):
        """Restart the current level."""
        self.game_over = False
        self._level_complete = False
        self._level_transition_timer = 0.0
        self._level_banner_alpha = 0
        self._countdown_beeps_fired = set()
        self.elimination_screen = None
        self.eliminated_players.clear()

        self.tile_manager.reset()
        self.walkable_mask = self.original_walkable_mask.copy() if self.original_walkable_mask else None
        self.hazard_manager.reset()
        self.orb_manager.reset()
        # Clear any active orb freeze
        if hasattr(self, '_orb_freeze_timer'): del self._orb_freeze_timer
        self.hud.reset()
        self.hud.set_level(self.current_level_number, self.level_config.name)

        for player in self.players:
            player.reset()
        self.hud.set_player_info(self.player_name, len(self.players), len(self.players))

    def _load_next_level(self):
        """Advance to the next level, rebuilding AI and tile system."""
        self.current_level_number += 1
        if self.current_level_number > MAX_LEVEL:
            # All levels beaten — show victory and loop back
            self.current_level_number = MAX_LEVEL
            self._trigger_game_over(victory=True)
            return

        self.level_config = get_level(self.current_level_number)
        self.game_over = False
        self._level_complete = False
        self._level_transition_timer = 0.0
        self._countdown_beeps_fired = set()
        self.elimination_screen = None
        self.eliminated_players.clear()

        # Rebuild tile manager with new config
        offset = self.map_offset if self.map_offset else (0, 0)
        scale_x = self.map_scale_x if self.map_scale_x else 1.0
        scale_y = self.map_scale_y if self.map_scale_y else 1.0
        self.tile_manager = TMXTileManager(
            self.tmx_data, scale_x, scale_y, offset,
            level_config=self.level_config,
            forced_arena=self._forced_arena,
        )
        self.walkable_mask = self.original_walkable_mask.copy() if self.original_walkable_mask else None

        # Rebuild hazard manager with new config
        self.hazard_manager = HazardManager(
            self.collision_manager, level_config=self.level_config
        )
        self.environment = LevelEnvironment(self.current_level_number)
        self.orb_manager = OrbManager(self.current_level_number)

        # Rebuild players — keep human character choices
        self.players.clear()
        self._build_players()
        self._wire_ai_players()

        self.hud.reset()
        self.hud.set_player_info(self.player_name, len(self.players), len(self.players))
        self.hud.set_level(self.current_level_number, self.level_config.name)

    def _draw_tmx_map_with_tiles(self):
        """Draw TMX map layers, letting missing tiles reveal the background.

        map_surface was rendered excluding the destructible layer (assets.py
        passes exclude_layers=DESTRUCTIBLE_LAYER_NAMES).  Blitting it first
        means the gaps where tiles have disappeared show the background beneath
        instead of the original tile artwork.  draw_active_tiles then repaints
        only the tiles that are still alive (NORMAL or WARNING state).
        """
        if not self.tmx_data or not self.map_surface:
            return

        # Draw background tint for current level
        if self.level_config and self.level_config.bg_tint[3] > 0:
            r, g, b, a = self.level_config.bg_tint
            tint_surf = pygame.Surface(WINDOW_SIZE, pygame.SRCALPHA)
            tint_surf.fill((r, g, b, a))
            self.screen.blit(tint_surf, (0, 0))

        # Base map without destructible layer — tinted for current level
        tinted_map = self.environment.tint_map_surface(self.map_surface)
        self.screen.blit(tinted_map, (0, 0))

        # Repaint surviving destructible tiles on top
        self.tile_manager.draw_active_tiles(self.screen)

    def _draw_level_complete_banner(self):
        """Animated full-screen 'Level Complete' banner during transition."""
        alpha = min(255, self._level_banner_alpha)
        if alpha <= 0:
            return

        cx, cy = WINDOW_SIZE[0] // 2, WINDOW_SIZE[1] // 2

        # Dark overlay
        overlay = pygame.Surface(WINDOW_SIZE, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, min(180, alpha)))
        self.screen.blit(overlay, (0, 0))

        try:
            font_big  = pygame.font.SysFont("consolas", 54, bold=True)
            font_med  = pygame.font.SysFont("consolas", 28)
            font_small = pygame.font.SysFont("consolas", 20)
        except Exception:
            return

        # Pulsing green "LEVEL COMPLETE"
        pulse = 0.5 + 0.5 * math.sin(self._level_transition_timer * math.pi * 3)
        g = int(180 + 75 * pulse)
        title_surf = font_big.render("LEVEL COMPLETE!", True, (60, g, 80))
        title_surf.set_alpha(alpha)
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, cy - 70)))

        # Next level name
        next_num = self.current_level_number + 1
        if next_num <= MAX_LEVEL:
            next_cfg = get_level(next_num)
            next_text = f"Next: Level {next_num} — {next_cfg.name}"
            next_surf = font_med.render(next_text, True, (200, 220, 255))
            next_surf.set_alpha(alpha)
            self.screen.blit(next_surf, next_surf.get_rect(center=(cx, cy)))

        # Score bonus
        bonus = self.level_config.score_bonus if self.level_config else 0
        bonus_surf = font_med.render(f"+{bonus} pts", True, (255, 215, 0))
        bonus_surf.set_alpha(alpha)
        self.screen.blit(bonus_surf, bonus_surf.get_rect(center=(cx, cy + 40)))

        # Progress bar
        progress = min(1.0, self._level_transition_timer / self._level_transition_duration)
        bar_w = 320
        bar_h = 8
        bar_x = cx - bar_w // 2
        bar_y = cy + 80
        pygame.draw.rect(self.screen, (50, 50, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            pygame.draw.rect(self.screen, (60, 200, 100), (bar_x, bar_y, fill_w, bar_h), border_radius=4)

    def _draw_power_hud(self):
        """Draw each human player's multi-power row with active power highlighted."""
        try:
            font_name = pygame.font.SysFont("consolas", 12)
            font_key  = pygame.font.SysFont("consolas", 10)
        except Exception:
            return

        human_players = [p for p in self.players if not p.is_ai]
        if not human_players:
            return

        icon_size = 36      # smaller icons to fit multiple powers
        gap       = 4
        info_w    = 130

        for pidx, player in enumerate(human_players):
            if not hasattr(player, 'powers') or not player.powers:
                continue

            n_powers = len(player.powers)
            row_w    = n_powers * (icon_size + gap) - gap + info_w + 16
            bx = (WINDOW_SIZE[0] // 2 - row_w // 2) + pidx * (row_w + 24)
            by = WINDOW_SIZE[1] - icon_size - 18

            # Panel background
            panel_rect = pygame.Rect(bx - 8, by - 6, row_w + 16, icon_size + 12)
            panel_surf = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
            panel_surf.fill((10, 10, 20, 170))
            active_col = player.active_power.COLOR
            pygame.draw.rect(panel_surf, (*active_col, 160),
                             panel_surf.get_rect(), 2, border_radius=8)
            self.screen.blit(panel_surf, panel_rect.topleft)

            # Draw all power icons in a row
            for i, pw in enumerate(player.powers):
                ix = bx + i * (icon_size + gap)
                iy = by
                ir = pygame.Rect(ix, iy, icon_size, icon_size)
                is_active = (i == player._power_index)

                # Highlight active power with bright border
                if is_active:
                    highlight = pygame.Surface((icon_size + 4, icon_size + 4), pygame.SRCALPHA)
                    pygame.draw.rect(highlight, (255, 255, 255, 200),
                                     highlight.get_rect(), 2, border_radius=6)
                    self.screen.blit(highlight, (ix - 2, iy - 2))

                pw.draw_hud_icon(self.screen, ir)

                # Dim inactive powers slightly
                if not is_active:
                    dim = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
                    dim.fill((0, 0, 0, 100))
                    self.screen.blit(dim, ir.topleft)

                # Cooldown arc on each icon
                if pw.cooldown_remaining > 0:
                    frac = pw.cooldown_fraction
                    arc_r = pygame.Rect(ix - 2, iy - 2, icon_size + 4, icon_size + 4)
                    pygame.draw.arc(self.screen, (200, 200, 200),
                                    arc_r, math.pi/2,
                                    math.pi/2 + math.tau * frac, 2)

            # Active power info to the right of the icon row
            tx = bx + n_powers * (icon_size + gap) + 8
            active = player.active_power
            nm = font_name.render(active.NAME, True, active.COLOR)
            self.screen.blit(nm, (tx, by + 2))

            desc = font_name.render(active.DESCRIPTION[:30], True, (155, 155, 168))
            self.screen.blit(desc, (tx, by + 15))

            # Key hints
            power_key = pygame.key.name(player.controls.get('power', 0)).upper()
            cycle_key = pygame.key.name(player.controls.get('cycle', pygame.K_TAB)).upper()
            status = ("READY" if active.ready else
                      f"{active.cooldown_remaining:.1f}s" if not active.active else "ACTIVE")
            sc = ((80, 255, 120) if active.ready else
                  (255, 220, 60) if active.active else (180, 180, 180))
            ks = font_key.render(
                f"[{power_key}] {status}  [{cycle_key}] cycle", True, sc
            )
            self.screen.blit(ks, (tx, by + 28))

            # Orb shield indicator
            if getattr(player, '_orb_shield', False):
                sh = font_key.render("  SHIELD ACTIVE", True, (255, 220, 50))
                self.screen.blit(sh, (tx, by + 40))

    def _draw_walkable_debug(self):
        if not (DEBUG_VISUALS_ENABLED and DEBUG_DRAW_WALKABLE) or self.walkable_mask is None:
            return

        if self.walkable_debug_surface is None:
            color = (*DEBUG_WALKABLE_COLOR, 90)
            self.walkable_debug_surface = self.walkable_mask.to_surface(
                setcolor=color, unsetcolor=(0, 0, 0, 0)
            )

        self.screen.blit(self.walkable_debug_surface, (0, 0))

    def _character_choice(self, index: int) -> str | None:
        if not self.selected_characters:
            return None
        if 0 <= index < len(self.selected_characters):
            return self.selected_characters[index]
        return self.selected_characters[-1]

    def run(self):
        while self.running:
            dt = self.clock.tick(TARGET_FPS) / 1000.0
            self.handle_events()
            keys = pygame.key.get_pressed()
            self.update(dt, keys)
            self.draw()

        if hasattr(self, "audio"):
            self.audio.stop_music()
        pygame.quit()


# Backward compatibility for older imports.
Game = GameManager