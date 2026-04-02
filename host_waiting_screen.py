import math
import sys

import pygame

from lan_prompts import draw_lan_backdrop
from scenes.common import _draw_rounded_rect, _load_font
from settings import (
    FONT_PATH_BODY,
    FONT_PATH_HEADING,
    WINDOW_SIZE,
)


def _draw_waiting_panel(
    screen,
    title: str,
    lines: list[str],
    *,
    accent=(180, 80, 255),
    success=False,
):
    width, height = WINDOW_SIZE
    font_title = _load_font(FONT_PATH_HEADING, 34, bold=True)
    font_body = _load_font(FONT_PATH_BODY, 24)
    font_small = _load_font(FONT_PATH_BODY, 18)
    anim_time = pygame.time.get_ticks() / 1000.0
    draw_lan_backdrop(screen, anim_time)

    panel = pygame.Rect(0, 0, min(860, width - 120), 280)
    panel.center = (width // 2, height // 2)
    border = (60, 220, 80) if success else accent
    pulse = 0.5 + 0.5 * math.sin(anim_time * 2.8)
    glow = pygame.Surface((panel.width + 20, panel.height + 20), pygame.SRCALPHA)
    pygame.draw.rect(
        glow,
        (border[0], border[1], border[2], int(28 + 20 * pulse)),
        glow.get_rect(),
        border_radius=24,
    )
    screen.blit(glow, (panel.left - 10, panel.top - 10), special_flags=pygame.BLEND_ADD)
    _draw_rounded_rect(screen, panel, (20, 28, 48), border, 3, 18)

    title_surf = font_title.render(title, True, (255, 255, 255))
    screen.blit(title_surf, title_surf.get_rect(center=(panel.centerx, panel.top + 48)))

    y = panel.top + 104
    for idx, line in enumerate(lines):
        font = font_body if idx == 0 else font_small
        color = accent if idx == 0 else (215, 220, 235)
        if success:
            color = (60, 220, 80) if idx == 0 else (215, 220, 235)
        surf = font.render(line, True, color)
        screen.blit(surf, surf.get_rect(center=(panel.centerx, y)))
        y += 40 if idx == 0 else 30

    pygame.display.flip()


def host_waiting_screen(screen, clock, host_ip, network):
    """Wait for a LAN client while keeping the host UI responsive."""
    while True:
        connected = network.poll_connection()
        lines = [
            f"Host IP: {host_ip}",
            "Share this address with the other player on your LAN.",
            "Press ESC to cancel.",
        ]
        _draw_waiting_panel(
            screen,
            "Waiting For Player To Join",
            lines,
            accent=(180, 80, 255),
        )

        if connected:
            peer_ip = network.peer_address[0] if network.peer_address else "Unknown"
            for _ in range(24):
                _draw_waiting_panel(
                    screen,
                    "Player Connected",
                    [
                        peer_ip,
                        "Preparing the match lobby...",
                    ],
                    success=True,
                )
                clock.tick(30)
            return True

        if network.last_error:
            return False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
        clock.tick(30)
