import base64
import os
import logging
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

FONT_SIZES = {
    "x-small": 0.7,
    "small": 0.9,
    "normal": 1.0,
    "large": 1.2,
    "x-large": 1.5,
}


class LetterPicture(BasePlugin):
    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        image_data = None
        image_path = settings.get("imageFile")
        if image_path and os.path.exists(image_path):
            ext = os.path.splitext(image_path)[1].lower().lstrip(".")
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            with open(image_path, "rb") as f:
                image_data = f"data:image/{mime};base64,{base64.b64encode(f.read()).decode()}"
        else:
            if image_path:
                logger.warning(f"Image file not found: {image_path}")

        template_params = {
            "title": settings.get("title", ""),
            "message": settings.get("message", ""),
            "image_data": image_data,
            "layout": settings.get("layout", "image-left"),
            "font_scale": FONT_SIZES.get(settings.get("fontSize", "normal"), 1.0),
            "image_size": int(settings.get("imageSize", 45)),
            "text_align": settings.get("textAlign", "left"),
            "plugin_settings": settings,
        }

        return self.render_image(dimensions, "letter_picture.html", "letter_picture.css", template_params)

    def cleanup(self, settings):
        image_path = settings.get("imageFile")
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                logger.info(f"Deleted image file: {image_path}")
            except Exception as e:
                logger.warning(f"Failed to delete image file {image_path}: {e}")
