from enum import Enum
from typing import Mapping

from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.utils import ValueTypes, struct_to_dict

from .action_class import Action
from .notification_class import (NotificationEmail, NotificationSMS, NotificationType,
                                 NotificationWebhookGET)
from .rules import (RuleCall, RuleClassifier, RuleDetector, RuleTime,
                    RuleTracker, RuleLogicType, RuleType)
from .common import Resource, ResourceType, ResourceSubType, Modes

class EventState(str, Enum):
    setup = "setup"
    monitoring = "monitoring"
    paused = "paused"
    triggered = "triggered"
    actioning = "actioning"

class Event():
    name: str
    state: EventState = EventState.paused
    capture_video: bool = False
    video_capture_resource: str
    event_video_capture_padding_secs: float = 10
    pause_alerting_on_event_secs: float = 300
    detection_hz: int = 5
    is_triggered: bool = False
    last_triggered: float = 0
    paused_until: float = 0
    pause_reason: str = ""
    modes: list[Modes] = [Modes.inactive]
    rule_logic_type: RuleLogicType = RuleLogicType.AND
    rules: list[RuleDetector|RuleClassifier|RuleTime|RuleTracker|RuleCall]
    notifications: list[NotificationSMS|NotificationEmail|NotificationWebhookGET]
    actions: list[Action]
    actions_paused: bool = False
    triggered_rules: dict = {}
    triggered_camera: str = ""
    triggered_label: str = ""
    trigger_sequence_count: int = 1
    sequence_count_current: int = 0
    resources: Mapping[str, Resource]

    def __init__(self, config: Mapping[str, ValueTypes], dependencies: Mapping[ResourceName, ResourceBase]):
        if "name" not in config:
            raise KeyError("The key 'name' is missing from the event configuration.")
        if not isinstance(config["name"], str):
            raise TypeError("The value for 'name' must be a string.")
        self.name = config["name"]

        if "state" in config:
            if not isinstance(config["state"], str):
                raise TypeError("The value for 'state' must be a string.")
            self.state = EventState(config["state"])

        if "capture_video" in config:
            if not isinstance(config["capture_video"], bool):
                raise TypeError("The value for 'capture_video' must be a boolean.")
            self.capture_video = config["capture_video"]

        if "video_capture_resource" in config:
            if not isinstance(config["video_capture_resource"], str):
                raise TypeError("The value for 'video_capture_resource' must be a string.")
            self.video_capture_resource = config["video_capture_resource"]
        
        if "event_video_capture_padding_secs" in config:
            if not isinstance(config["event_video_capture_padding_secs"], float):
                raise TypeError("The value for 'event_video_capture_padding_secs' must be an integer.")
            self.event_video_capture_padding_secs = config["event_video_capture_padding_secs"]

        if "pause_alerting_on_event_secs" in config:
            if not isinstance(config["pause_alerting_on_event_secs"], float):
                raise TypeError("The value for 'pause_alerting_on_event_secs' must be an integer.")
            self.pause_alerting_on_event_secs = config["pause_alerting_on_event_secs"]

        if "detection_hz" in config:
            if not isinstance(config["detection_hz"], float):
                raise TypeError("The value for 'detection_hz' must be an integer.")
            self.detection_hz = int(config["detection_hz"])

        if "modes" in config:
            if not isinstance(config["modes"], list):
                raise TypeError("The value for 'modes' must be a list.")
            for mode in config["modes"]:
                if not isinstance(mode, str):
                    raise TypeError("Each mode in 'modes' must be a string.")
                if mode not in Modes.__members__:
                    raise ValueError(f"Invalid mode: {mode}")
                self.modes.append(Modes[mode])

        if "rule_logic_type" in config:
            if not isinstance(config["rule_logic_type"], str):
                raise TypeError("The value for 'rule_logic_type' must be a string.")
            if config["rule_logic_type"] not in RuleLogicType.__members__:
                raise ValueError(f"Invalid value for 'rule_logic_type': {config['rule_logic_type']}")
            self.rule_logic_type = RuleLogicType[config["rule_logic_type"]]

        if "rules" not in config:
            raise KeyError("The key 'rules' is missing from the event configuration.")
        if not isinstance(config["rules"], list):
            raise TypeError("The value for 'rules' must be a list.")
        self.rules = []
        for rule in config["rules"]:
            if not isinstance(rule, dict):
                raise TypeError("Each rule in 'rules' must be a dictionary.")
            if "type" not in rule:
                raise KeyError("The key 'type' is missing from the rule configuration.")
            if rule["type"] == RuleType.detection:
                self.rules.append(RuleDetector(**rule))
            elif rule["type"] == RuleType.classification:
                self.rules.append(RuleClassifier(**rule))
            elif rule["type"] == RuleType.time:
                self.rules.append(RuleTime(**rule))
            elif rule["type"] == RuleType.tracker:
                self.rules.append(RuleTracker(**rule))
            elif rule["type"] == RuleType.call:
                self.rules.append(RuleCall(**rule))
            else:
                raise ValueError(f"Invalid rule type: {rule['type']}")

        if "notifications" not in config:
            raise KeyError("The key 'notifications' is missing from the event configuration.")
        if not isinstance(config["notifications"], list):
            raise TypeError("The value for 'notifications' must be a list.")
        self.notifications = []
        for notification in config["notifications"]:
            if not isinstance(notification, dict):
                raise TypeError("Each notification in 'notifications' must be a dictionary.")
            if "type" not in notification:
                raise KeyError("The key 'type' is missing from the notification configuration.")
            if notification["type"] == NotificationType.sms:
                self.notifications.append(NotificationSMS(**notification))
            elif notification["type"] == NotificationType.email:
                self.notifications.append(NotificationEmail(**notification))
            elif notification["type"] == NotificationType.webhook_get:
                self.notifications.append(NotificationWebhookGET(**notification))
            else:
                raise ValueError(f"Invalid notification type: {notification['type']}")

        if "actions" in config:
            if not isinstance(config["actions"], list):
                raise TypeError("The value for 'actions' must be a list.")
            self.actions = []
            for action in config["actions"]:
                if not isinstance(action, dict):
                    raise TypeError("Each action in 'actions' must be a dictionary.")
                self.actions.append(Action(**action))

        if "trigger_sequence_count" in config:
            if not isinstance(config["trigger_sequence_count"], float):
                raise TypeError("The value for 'trigger_sequence_count' must be an integer.")
            self.trigger_sequence_count = int(config["trigger_sequence_count"])

    def __init2__(self, **kwargs):
        # these are optional
        self.__dict__["actions"] = []
        self.__dict__["notifications"] = []

        for key, value in kwargs.items():
            if isinstance(value, list):
                if key == "notifications":
                    for item in value:
                        if item["type"] == "sms":
                            for s in item["to"]:
                                sms = {
                                    "preset": item["preset"],
                                    "to": s
                                }
                                self.__dict__[key].append(NotificationSMS(**sms))
                        elif item["type"] == "email":
                            for s in item["to"]:
                                email = {
                                    "preset": item["preset"],
                                    "to": s
                                }
                                self.__dict__[key].append(NotificationEmail(**email))
                        elif item["type"] == "webhook_get":
                            self.__dict__[key].append(NotificationWebhookGET(**item))
                elif key == "rules":
                    self.__dict__["rules"] = []
                    for item in value:
                        if item["type"] == "detection":
                            self.__dict__[key].append(RuleDetector(**item))
                        elif item["type"] == "classification":
                            self.__dict__[key].append(RuleClassifier(**item))
                        elif item["type"] == "time":
                            self.__dict__[key].append(RuleTime(**item))
                        elif item["type"] == "tracker":
                            self.__dict__[key].append(RuleTracker(**item))
                        elif item["type"] == "call":
                            self.__dict__[key].append(RuleCall(**item))
                elif key == "modes":
                    self.__dict__["modes"] = []
                    for item in value:
                        self.__dict__[key].append(item)
                elif key == "actions":
                    for item in value:
                        self.__dict__[key].append(Action(**item))
            else:
                self.__dict__[key] = value

