from PIL import Image
import os

def resize_image(input_path, output_path, size=(800, 800)):
    with Image.open(input_path) as img:
        img.thumbnail(size)  # Resize while maintaining aspect ratio
        img.save(output_path)


image_paths=['/root/Telegram-Trading-Bot-Prod/exponentialfactor-graphics/expfactor0.png', '/root/Telegram-Trading-Bot-Prod/exponentialfactor-graphics/expfactor20.png', '/root/Telegram-Trading-Bot-Prod/exponentialfactor-graphics/expfactor50.png', '/root/Telegram-Trading-Bot-Prod/exponentialfactor-graphics/expfactor70.png', '/root/Telegram-Trading-Bot-Prod/exponentialfactor-graphics/expfactor100.png']

for path in image_paths:
    resize_image(path, path)
