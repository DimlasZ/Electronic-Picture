import logging
from inky.auto import auto
from display.abstract_display import AbstractDisplay

try:
    import lgpio
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

logger = logging.getLogger(__name__)

BUTTONS = [5, 6, 16, 24]
BUTTON_LABELS = ['A', 'B', 'C', 'D']

class InkyDisplay(AbstractDisplay):

    """
    Handles the Inky e-paper display.

    This class initializes and manages interactions with the Inky display,
    ensuring proper image rendering and configuration storage.

    The Inky display driver supports auto configuration.
    """
   
    def initialize_display(self):
        
        """
        Initializes the Inky display device.

        Sets the display border and stores the display resolution in the device configuration.

        Raises:
            ValueError: If the resolution cannot be retrieved or stored.
        """
        
        self.inky_display = auto()
        self.inky_display.set_border(self.inky_display.BLACK)

        # Set up button listeners for Inky Impression physical buttons (A, B, C, D)
        if GPIO_AVAILABLE:
            self._gpio_handle = lgpio.gpiochip_open(0)
            self._gpio_callbacks = []
            for pin, label in zip(BUTTONS, BUTTON_LABELS):
                lgpio.gpio_claim_alert(self._gpio_handle, pin, lgpio.FALLING_EDGE, lgpio.SET_PULL_UP)
                lgpio.gpio_set_debounce_micros(self._gpio_handle, pin, 100000)
                cb = lgpio.callback(self._gpio_handle, pin, lgpio.FALLING_EDGE,
                                    lambda chip, gpio, level, tick, l=label, p=pin:
                                    logger.info(f"Button {l} pressed (GPIO pin {p})"))
                self._gpio_callbacks.append(cb)
            logger.info("Button listeners registered for GPIO pins: %s", BUTTONS)
        else:
            logger.warning("lgpio not available, button listeners not registered.")

        # store display resolution in device config
        if not self.device_config.get_config("resolution"):
            self.device_config.update_value(
                "resolution",
                [int(self.inky_display.width), int(self.inky_display.height)], 
                write=True)

    def display_image(self, image, image_settings=[]):
        
        """
        Displays the provided image on the Inky display.

        The image has been processed by adjusting orientation and resizing 
        before being sent to the display.

        Args:
            image (PIL.Image): The image to be displayed.
            image_settings (list, optional): Additional settings to modify image rendering.

        Raises:
            ValueError: If no image is provided.
        """

        logger.info("Displaying image to Inky display.")
        if not image:
            raise ValueError(f"No image provided.")

        # Display the image on the Inky display
        inky_saturation = self.device_config.get_config('image_settings').get("inky_saturation", 0.5)
        logger.info(f"Inky Saturation: {inky_saturation}")
        self.inky_display.set_image(image, saturation=inky_saturation)
        self.inky_display.show()