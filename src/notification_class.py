from enum import Enum
from PIL import Image

class NotificationType(str, Enum):
    sms = "sms"
    email = "email"
    webhook_get = "webhook_get"

class Notification:
    type: NotificationType
    def __init__(self, type: NotificationType):
        if not isinstance(type, NotificationType):
            raise TypeError("The type must be an instance of NotificationType.")
        self.type = type

class ImageNotification(Notification):
    image: Image.Image
    include_image: bool = True
    def __init__(self, type: NotificationType, **kwargs):
        super().__init__(NotificationType.sms)
        for key, value in kwargs.items():
            self.__dict__[key] = value

class NotificationSMS(ImageNotification):
    to: str
    preset: str
    def __init__(self, **kwargs):
        super().__init__(NotificationType.sms, **kwargs)
        for key, value in kwargs.items():
            self.__dict__[key] = value

class NotificationEmail(ImageNotification):
    to: str
    preset: str
    def __init__(self, **kwargs):
        super().__init__(NotificationType.email, **kwargs)
        for key, value in kwargs.items():
            self.__dict__[key] = value

class NotificationWebhookGET(ImageNotification):
    url: str
    def __init__(self, **kwargs):
        super().__init__(NotificationType.webhook_get, **kwargs)
        for key, value in kwargs.items():
            self.__dict__[key] = value
