import pygame

i=0

def crop_to_sprite(image):
    """Crop image to bounding box of non-transparent pixels."""
    rect = image.get_bounding_rect()  # bounding box of non-transparent area
    cropped = pygame.Surface(rect.size, pygame.SRCALPHA)  # keep transparency
    cropped.blit(image, (0, 0), rect)
    return cropped

def resize(image):
    """Crop image to bounding box of non-transparent pixels."""
    resized=pygame.transform.scale(image,(64,64))
    #resized.blit(image, (0, 0), rect)
    return resized

# Init pygame (needed for image functions)
pygame.init()
pygame.display.set_mode((1, 1), pygame.HIDDEN)
while(i<231):
    if i < 10:
        sprite = pygame.image.load(f"Assets/assets_pixel_50x50/isometric_pixel_000{i}.png").convert_alpha()
    elif i>=10 and i<100:
        sprite = pygame.image.load(f"Assets/assets_pixel_50x50/isometric_pixel_00{i}.png").convert_alpha()
    elif i >=100:
        sprite = pygame.image.load(f"Assets/assets_pixel_50x50/isometric_pixel_0{i}.png").convert_alpha()

    # Crop it
    cropped_sprite = crop_to_sprite(sprite)

    resized_sprite = resize(cropped_sprite)

    # Save to new file
    pygame.image.save(resized_sprite, f"Assets/cropped/{i}.png")
    i+=1

print("✅ Saved cropped sprite as sprite_cropped.png")