import base64
import json
import urllib
import urllib.request
from datetime import datetime, timezone
from io import BytesIO
from typing import Mapping

from PIL import Image

from . import events
from .common import Resource
from .logger import LOGGER
from .notification_class import (NotificationEmail,
                                 NotificationSMS,
                                 NotificationWebhookGET)


# TODO: There is a lot of duplicated code between the notify and check_sms_response functions, we should refactor this to use some common functions
async def notify(event:events.Event, notification:NotificationEmail|NotificationSMS|NotificationWebhookGET, resources: Mapping[str, Resource], image:Image.Image|None=None) -> None:
    notification_args = {"command": "send", "template_vars": {"event_name": event.name, "triggered_label": event.triggered_label, "triggered_camera": event.triggered_camera}}

    if isinstance(notification, NotificationEmail):
        if not "email_module" in resources:
            LOGGER.warning("No email module defined, can't send notification email")
            return
        notification_resource = resources["email_module"].resource
        if notification_resource is None:
            LOGGER.warning("No email module defined, can't send notification email")
            return
        if notification.include_image:
            if image is None or not isinstance(image, Image.Image):
                LOGGER.warning("Image is not a valid Image object, sending notification without image")
            else:
                buffered = BytesIO()
                image.save(buffered, format="JPEG")
                img_base64_str = base64.b64encode(buffered.getvalue()).decode("ascii")
                notification_args["template_vars"]["image_base64"] = img_base64_str
        notification_args["preset"]= notification.preset
        notification_args["to"] = notification.to # Unlike SMS, we can send to multiple email addresses
        try:
            res = await notification_resource.do_command(notification_args)
            if "error" in res:
                LOGGER.error(f"Error sending {notification.type}: {res['error']}")
        except Exception as e:
            LOGGER.error(f'Unexpected error, notification not sent {e}')
    elif isinstance(notification, NotificationSMS):
        if not "sms_module" in resources:
            LOGGER.warning("No SMS module defined, can't send notification SMS")
            return
        notification_resource = resources["sms_module"].resource
        if notification_resource is None:
            LOGGER.warning("No SMS module defined, can't send notification SMS")
            return
        if notification.include_image:
            if image is None or not isinstance(image, Image.Image):
                LOGGER.warning("Image is not a valid Image object, sending notification without image")
            else:
                buffered = BytesIO()
                image.save(buffered, format="JPEG")
                img_base64_str = base64.b64encode(buffered.getvalue()).decode("ascii")
                notification_args["template_vars"]["image_base64"] = img_base64_str
                notification_args["template_vars"]["image_mime_type"] = "image/jpeg"
        notification_args["preset"]= notification.preset
        if len(notification.to) > 1:
            # TODO: handle multiple SMS recipients which is going to blow up the "check_sms_response" function
            LOGGER.warning("Multiple SMS recipients not supported, sending to first recipient only")
            notification.to = [notification.to[0]]
        for to in notification.to:
            notification_args["to"] = to
            try:
                res = await notification_resource.do_command(notification_args)
                if "error" in res:
                    LOGGER.error(f"Error sending SMS to {to}: {res['error']}")
            except Exception as e:
                LOGGER.error(f'Unexpected error, notification not sent {e}')
    elif isinstance(notification, NotificationWebhookGET):
        try:
            data = json.dumps(notification_args).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            request = urllib.request.Request(notification.url, method="GET", headers=headers, data=data)
            urllib.request.urlopen(request).read()
            return
        except Exception as e:
            LOGGER.error(f"Error in webhook GET: {e}")
            return
    else:
        LOGGER.warning(f"Unknown notification type {notification.type}")
        return

    return   

async def check_sms_response(notifications:list[NotificationEmail|NotificationSMS|NotificationWebhookGET], since:float, resources: Mapping[str, Resource]) -> str|None:
    formatted_time = datetime.fromtimestamp(since, timezone.utc).strftime('%d/%m/%Y %H:%M:%S')
    for n in notifications:
        if isinstance(n, NotificationSMS):
            sms_args = { "command": "get", "number": 1, "from": n.to, "time_start": formatted_time }
            LOGGER.debug(sms_args)
            if not "sms_module" in resources:
                LOGGER.warning("No SMS module defined, can't check for SMS response")
                return None
            res = await resources['sms_module'].resource.do_command(sms_args)
            if res is None:
                LOGGER.warning("No response from SMS module")
                return None
            if "messages" in res and isinstance(res["messages"], list) and len(res["messages"]) > 0:
                LOGGER.debug(res)
                return res["messages"][0]["body"]
    return None
