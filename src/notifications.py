import base64
from datetime import datetime, timezone
import json
import logging
import urllib
import urllib.request
from abc import abstractmethod
from enum import Enum
from io import BytesIO
from typing import Mapping

import phonenumbers
from PIL import Image
from viam.resource.base import ResourceBase
from .common import Resource
from viam.utils import ValueTypes


def validate_phone_number(phone_number: str) -> bool:
    """
    Validates a phone number using the phonenumbers library.
    Returns True if the phone number is valid, False otherwise.
    """
    try:
        parsed_number = phonenumbers.parse(phone_number, "US")
        return phonenumbers.is_valid_number(parsed_number)
    except phonenumbers.NumberParseException:
        return False

class Notifier:
    _logger: logging.Logger
    _resource: ResourceBase|None = None
    def __init__(self, logger:logging.Logger, resource:ResourceBase|None=None):
        if logger is None:
            raise ValueError("The logger cannot be None.")
        if not isinstance(logger, logging.Logger):
            raise TypeError("The logger must be an instance of logging.Logger.")
        self._logger = logger
        if resource is not None and not isinstance(resource, ResourceBase):
            raise TypeError("The resource must be an instance of ResourceBase.")
        self._resource = resource
    
    @abstractmethod
    async def notify(self, event_name:str, trigger_label:str, trigger_source:str, image:Image.Image|None=None):
        raise NotImplementedError("The eval method must be implemented in subclasses.")

    @classmethod
    def from_config(cls, logger:logging.Logger, conf:Mapping[str, ValueTypes], resources:Mapping[str, Resource]) -> "Notifier":
        """
        Factory method to create a Notifier instance based on the configuration.
        """
        if "type" not in conf:
            raise ValueError("The 'type' field is required in the configuration.")
        
        notifier_type = conf["type"]
        if notifier_type == NotificationType.sms:
            if "sms_module" not in resources:
                raise ValueError("The 'sms_module' resource is required for SMS notifications.")
            resource = resources["sms_module"]
            if not isinstance(resource, Resource):
                raise TypeError("The 'sms_module' resource must be an instance of Resource.")
            return SmsNotifier(logger, conf, resource=resource.resource)
        elif notifier_type == NotificationType.email:
            if "email_module" not in resources:
                raise ValueError("The 'email_module' resource is required for SMS notifications.")
            resource = resources["email_module"]
            if not isinstance(resource, Resource):
                raise TypeError("The 'email_module' resource must be an instance of Resource.")
            return EmailNotifier(logger, conf, resource=resource.resource)
        elif notifier_type == NotificationType.webhook_get:
            return WebhookNotifier(logger, conf)
        else:
            raise ValueError(f"Unknown notifier type: {notifier_type}")

class SmsNotifier(Notifier):
    to: list[str]
    preset: str
    include_image: bool = True

    def __init__(self, logger:logging.Logger, conf:Mapping[str, ValueTypes], resource:ResourceBase):
        super().__init__(logger, resource=resource)
        if "to" in conf:
            if isinstance(conf["to"], str):
                if not validate_phone_number(conf["to"]):
                    raise ValueError("The 'to' field must be a valid phone number.")
                self.to = [conf["to"]]
            elif isinstance(conf["to"], list):
                if all(isinstance(item, str) for item in conf["to"]):
                    for phone_number in conf["to"]:
                        if not validate_phone_number(phone_number):
                            raise ValueError("The 'to' field must be a valid phone number.")
                    self.to = conf["to"]
                else:
                    raise ValueError("The 'to' field must be a list of strings.")
        else:
            raise ValueError("The 'to' field must be a string.")
        
        if "preset" in conf and isinstance(conf["preset"], str):
            self.preset = conf["preset"]
        else:
            raise ValueError("The 'preset' field must be a string.")

    async def notify(self, event_name:str, trigger_label:str, trigger_source:str, image:Image.Image|None=None):
        self._logger.debug("Sending SMS notification")
        if not self._resource:
            self._logger.warning("No SMS module defined, can't send notification SMS")
            return
        notification_args = {
            "command": "send", 
            "template_vars": {
                "event_name": event_name, 
                "triggered_label": trigger_label, 
                "triggered_camera": trigger_source
                }
            }
        if self.include_image:
            if image is None or not isinstance(image, Image.Image):
                self._logger.warning("Image is not a valid Image object, sending notification without image")
            else:
                buffered = BytesIO()
                image.save(buffered, format="JPEG")
                img_base64_str = base64.b64encode(buffered.getvalue()).decode("ascii")
                notification_args["template_vars"]["image_base64"] = img_base64_str
                notification_args["template_vars"]["image_mime_type"] = "image/jpeg"
        notification_args["preset"]= self.preset
        if len(self.to) > 1:
            # TODO: handle multiple SMS recipients which is going to blow up the "check_sms_response" function
            self._logger.warning("Multiple SMS recipients not supported, sending to first recipient only")
            self.to = [self.to[0]]
        for to in self.to:
            notification_args["to"] = to
            try:
                res = await self._resource.do_command(notification_args)
                if "error" in res:
                    self._logger.error(f"Error sending SMS to {to}: {res['error']}")
            except Exception as e:
                self._logger.error(f'Unexpected error, notification not sent {e}')
        pass

    async def check_sms_response(self, since:float) -> str|None:
        formatted_time = datetime.fromtimestamp(since, timezone.utc).strftime('%d/%m/%Y %H:%M:%S')
        sms_args = { "command": "get", "number": 1, "from": self.to, "time_start": formatted_time }
        self._logger.debug(sms_args)
        if self._resource is None:
            self._logger.warning("No SMS module defined, can't check for SMS response")
            return None
        res = await self._resource.do_command(sms_args)
        if res is None:
            self._logger.warning("No response from SMS module")
            return None
        if "messages" in res and isinstance(res["messages"], list) and len(res["messages"]) > 0:
            self._logger.debug(res)
            return res["messages"][0]["body"]

class EmailNotifier(Notifier):
    to: list[str]
    preset: str
    include_image: bool = False
    def __init__(self, logger:logging.Logger, conf:Mapping[str, ValueTypes], resource:ResourceBase):
        super().__init__(logger, resource=resource)
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

    async def notify(self, event_name:str, trigger_label:str, trigger_source:str, image:Image.Image|None=None):
        self._logger.debug("Sending email notification")
        if not self._resource:
            self._logger.warning("No email module defined, can't send notification email")
            return
        notification_args = {
            "command": "send", 
            "template_vars": {
                "event_name": event_name, 
                "triggered_label": trigger_label, 
                "triggered_camera": trigger_source
                }
            }
        if self.include_image:
            if image is None or not isinstance(image, Image.Image):
                self._logger.warning("Image is not a valid Image object, sending notification without image")
            else:
                buffered = BytesIO()
                image.save(buffered, format="JPEG")
                img_base64_str = base64.b64encode(buffered.getvalue()).decode("ascii")
                notification_args["template_vars"]["image_base64"] = img_base64_str
        notification_args["preset"]= self.preset
        notification_args["to"] = self.to # Unlike SMS, we can send to multiple email addresses
        try:
            res = await self._resource.do_command(notification_args)
            if "error" in res:
                self._logger.error(f"Error sending email: {res['error']}")
        except Exception as e:
            self._logger.error(f'Unexpected error, notification not sent {e}')
        pass

class WebhookNotifier(Notifier):
    url: str

    def __init__(self, logger:logging.Logger, conf:Mapping[str, ValueTypes]):
        super().__init__(logger, resource=None)
        if "url" in conf and isinstance(conf["url"], str):
            self.url = conf["url"]
        else:
            raise ValueError("The 'url' field must be a string.")
        
    async def notify(self, event_name:str, trigger_label:str, trigger_source:str, image:Image.Image|None=None):
        self._logger.debug("Sending webhook notification")
        notification_args = {
            "command": "send", 
            "template_vars": {
                "event_name": event_name, 
                "triggered_label": trigger_label, 
                "triggered_camera": trigger_source
                }
            }
        try:
            data = json.dumps(notification_args).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            request = urllib.request.Request(self.url, method="GET", headers=headers, data=data)
            urllib.request.urlopen(request).read()
            return
        except Exception as e:
            self._logger.error(f"Error in webhook GET: {e}")
            return

class NotificationType(str, Enum):
    sms = "sms"
    email = "email"
    webhook_get = "webhook_get"
