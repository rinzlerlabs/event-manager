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

class NotificationSMS(Notification):
    to: str
    preset: str
    image: Image.Image
    include_image: bool = True
    def __init__(self, **kwargs):
        super().__init__(NotificationType.sms)
        for key, value in kwargs.items():
            self.__dict__[key] = value

class NotificationEmail(Notification):
    to: str
    preset: str
    image: Image.Image
    include_image: bool = False
    
    def __init__(self, **kwargs):
        super().__init__(NotificationType.email)
        for key, value in kwargs.items():
            self.__dict__[key] = value

class NotificationWebhookGET(Notification):
    url: str
    image: Image.Image
    def __init__(self, **kwargs):
        super().__init__(NotificationType.webhook_get)
        for key, value in kwargs.items():
            self.__dict__[key] = value
