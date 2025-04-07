from enum import Enum
from typing import Mapping

from viam.utils import ValueTypes


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
    include_image: bool = True
    def __init__(self, notificationType: NotificationType, conf:Mapping[str, ValueTypes]):
        super().__init__(notificationType)
        if "include_image" in conf and isinstance(conf["include_image"], (bool, str)):
            self.include_image = bool(conf["include_image"])

class NotificationSMS(ImageNotification):
    to: list[str]
    preset: str
    def __init__(self, conf:Mapping[str, ValueTypes]):
        super().__init__(NotificationType.sms, conf)
        if "to" in conf:
            if isinstance(conf["to"], str):
                self.to = [conf["to"]]
            elif isinstance(conf["to"], list):
                if all(isinstance(item, str) for item in conf["to"]):
                    self.to = conf["to"]
                else:
                    raise ValueError("The 'to' field must be a list of strings.")
        else:
            raise ValueError("The 'to' field must be a string.")
        if "preset" in conf and isinstance(conf["preset"], str):
            self.preset = conf["preset"]
        else:
            raise ValueError("The 'preset' field must be a string.")

class NotificationEmail(ImageNotification):
    to: list[str]
    preset: str
    def __init__(self, conf:Mapping[str, ValueTypes]):
        super().__init__(NotificationType.email, conf)
        if "to" in conf:
            if isinstance(conf["to"], str):
                self.to = [conf["to"]]
            elif isinstance(conf["to"], list):
                if all(isinstance(item, str) for item in conf["to"]):
                    self.to = conf["to"]
                else:
                    raise ValueError("The 'to' field must be a list of strings.")
        else:
            raise ValueError("The 'to' field must be a string.")
        if "preset" in conf and isinstance(conf["preset"], str):
            self.preset = conf["preset"]
        else:
            raise ValueError("The 'preset' field must be a string.")

class NotificationWebhookGET(ImageNotification):
    url: str
    def __init__(self, conf:Mapping[str, ValueTypes]):
        super().__init__(NotificationType.webhook_get, conf)
        if "url" in conf and isinstance(conf["url"], str):
            self.url = conf["url"]
        else:
            raise ValueError("The 'url' field must be a string.")
