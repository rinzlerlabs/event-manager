import urllib
import base64
import json
from io import BytesIO
from datetime import datetime, timezone
import urllib.request
from . import events
from .notification_class import NotificationEmail, NotificationSMS, NotificationWebhookGET, ImageNotification, NotificationType
from .logger import LOGGER
from .common import Resource
from typing import Mapping


async def notify(event:events.Event, notification:NotificationEmail|NotificationSMS|NotificationWebhookGET, resources: Mapping[str, Resource]):
    notification_args = {"command": "send", "template_vars": {"event_name": event.name, "triggered_label": event.triggered_label, "triggered_camera": event.triggered_camera}}

    if isinstance(notification, NotificationEmail):
        if not "email_module" in resources:
            LOGGER.warning("No email module defined, can't send notification email")
            return
        notification_resource = resources["email_module"].resource
        notification_args["to"] = notification.to
        notification_args["preset"]= notification.preset
        if notification.include_image:
            buffered = BytesIO()
            notification.image.save(buffered, format="JPEG")
            img_base64_str = base64.b64encode(buffered.getvalue()).decode("ascii")
            notification_args["template_vars"]["image_base64"] = img_base64_str
    elif isinstance(notification, NotificationSMS):
        if not "sms_module" in resources:
            LOGGER.warning("No SMS module defined, can't send notification SMS")
            return
        notification_resource = resources["sms_module"].resource
        notification_args["to"] = notification.to
        notification_args["preset"]= notification.preset
        if notification.include_image:
            buffered = BytesIO()
            notification.image.save(buffered, format="JPEG")
            img_base64_str = base64.b64encode(buffered.getvalue()).decode("ascii")
            notification_args["template_vars"]["image_base64"] = img_base64_str
            notification_args["template_vars"]["image_mime_type"] = "image/jpeg"
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
    
    try:
        res = await notification_resource.do_command(notification_args)
        if "error" in res:
            LOGGER.error(f"Error sending {notification.type}: {res['error']}")
    except Exception as e:
        LOGGER.error(f'Unexpected error, notification not sent {e}')
        
    return   

async def check_sms_response(notifications:list[NotificationEmail|NotificationSMS|NotificationWebhookGET], since:float, resources: Mapping[str, Resource]):
    formatted_time = datetime.fromtimestamp(since, timezone.utc).strftime('%d/%m/%Y %H:%M:%S')
    for n in notifications:
        if isinstance(n, NotificationSMS):
            sms_args = { "command": "get", "number": 1, "from": n.to, "time_start": formatted_time }
            LOGGER.debug(sms_args)
            if not "sms_module" in resources:
                LOGGER.warning("No SMS module defined, can't check for SMS response")
                return
            res = await resources['sms_module'].resource.do_command(sms_args)
            if res is None:
                LOGGER.warning("No response from SMS module")
                return
            if "messages" in res and isinstance(res["messages"], list) and len(res["messages"]) > 0:
                LOGGER.debug(res)
                return res["messages"][0]["body"]
    return ""
