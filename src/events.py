from enum import Enum
from typing import Any, Mapping, cast
from logging import Logger

from viam.resource.base import ResourceBase
from viam.utils import ValueTypes

from .actions import Action
from .common import (Resource, ResourceSubType, ResourceType, MODE_INACTIVE, MODE_ACTIVE)
from .notifications import Notifier
from .rules import (RuleCall, RuleClassifier, RuleDetector, RuleLogicType,
                    RuleTime, RuleTracker, RuleType)


class EventState(str, Enum):
    setup = "setup"
    monitoring = "monitoring"
    paused = "paused"
    triggered = "triggered"
    actioning = "actioning"

class EventConfigParser:
    @staticmethod
    def parse_name(config:Mapping[str, ValueTypes]) -> str:
        if "name" not in config:
            raise KeyError("The key 'name' is missing from the event configuration.")
        if not isinstance(config["name"], str):
            raise TypeError("The value for 'name' must be a string.")
        return str(config["name"])
    
    @staticmethod
    def parse_state(config:Mapping[str, ValueTypes]) -> EventState:
        if "state" in config:
            if not isinstance(config["state"], str):
                raise TypeError("The value for 'state' must be a string.")
            return EventState(config["state"])
        return EventState.paused
    @staticmethod
    def parse_capture_video(config:Mapping[str, ValueTypes]) -> bool:
        if "capture_video" in config:
            if not isinstance(config["capture_video"], bool):
                raise TypeError("The value for 'capture_video' must be a boolean.")
            return config["capture_video"]
        return False
    @staticmethod
    def parse_video_capture_resource(config:Mapping[str, ValueTypes], dependencies:Mapping[str, Resource]) -> ResourceBase|None:
        if "video_capture_resource" in config:
            if not isinstance(config["video_capture_resource"], str):
                raise TypeError("The value for 'video_capture_resource' must be a string.")
            if config["video_capture_resource"] not in dependencies:
                raise ValueError(f"Dependency '{config['video_capture_resource']}' not found in dependencies.")
            if dependencies[config["video_capture_resource"]] is None:
                raise ValueError(f"Dependency '{config['video_capture_resource']}' cannot be None.")
            dependency = dependencies[config["video_capture_resource"]]
            if dependency.type != ResourceType.component or \
                (dependency.sub_type != ResourceSubType.camera and dependency.sub_type != ResourceSubType.generic):
                raise ValueError(f"Dependency '{config['video_capture_resource']}' must be a camera or generic component.")
            return dependencies[config["video_capture_resource"]].resource
        return None
    @staticmethod
    def parse_event_video_capture_padding_secs(config:Mapping[str, ValueTypes], default_value:float=10) -> float:
        if "event_video_capture_padding_secs" in config:
            if not isinstance(config["event_video_capture_padding_secs"], (int,float,str)):
                raise TypeError("The value for 'event_video_capture_padding_secs' must be an integer.")
            try:
                return float(config["event_video_capture_padding_secs"])
            except ValueError:
                raise ValueError("The value for 'event_video_capture_padding_secs' must be an integer.")
        return default_value
    @staticmethod
    def parse_pause_alerting_on_event_secs(config:Mapping[str, ValueTypes], default_value:float=300) -> float:
        if "pause_alerting_on_event_secs" in config:
            if not isinstance(config["pause_alerting_on_event_secs"], (int,float,str)):
                raise TypeError("The value for 'pause_alerting_on_event_secs' must be an integer.")
            try:
                return float(config["pause_alerting_on_event_secs"])
            except ValueError:
                raise ValueError("The value for 'pause_alerting_on_event_secs' must be an integer.")
        return default_value
    @staticmethod
    def parse_detection_hz(config:Mapping[str, ValueTypes], default_value:int=10) -> int:
        if "detection_hz" in config:
            if not isinstance(config["detection_hz"], (int,float,str)):
                raise TypeError("The value for 'detection_hz' must be an integer.")
            try:
                return int(config["detection_hz"])
            except ValueError:
                raise ValueError("The value for 'detection_hz' must be an integer.")
        return default_value
    @staticmethod
    def parse_modes(config:Mapping[str, ValueTypes]) -> list[str]:
        if "modes" in config:
            if not isinstance(config["modes"], list):
                raise TypeError("The value for 'modes' must be a list.")
            for mode in config["modes"]:
                if not isinstance(mode, str):
                    raise TypeError("Each mode in 'modes' must be a string.")
            return config["modes"]
        return [MODE_INACTIVE]
    @staticmethod
    def parse_rule_logic_type(config:Mapping[str, ValueTypes], default_value:RuleLogicType=RuleLogicType.AND) -> RuleLogicType:
        if "rule_logic_type" in config:
            if not isinstance(config["rule_logic_type"], str):
                raise TypeError("The value for 'rule_logic_type' must be a string.")
            if config["rule_logic_type"] not in RuleLogicType.__members__:
                raise ValueError(f"Invalid value for 'rule_logic_type': {config['rule_logic_type']}")
            return RuleLogicType[config["rule_logic_type"]]
        return default_value
    @staticmethod
    def parse_rules(logger:Logger, config:Mapping[str, ValueTypes], dependencies:Mapping[str, Resource]) -> list[RuleDetector|RuleClassifier|RuleTime|RuleTracker|RuleCall]:
        if "rules" not in config:
            raise KeyError("The key 'rules' is missing from the event configuration.")
        if not isinstance(config["rules"], list):
            raise TypeError("The value for 'rules' must be a list.")
        rules = []
        for rule in config["rules"]:
            if not isinstance(rule, Mapping):
                raise TypeError("Each rule in 'rules' must be a dictionary.")
            if "type" not in rule:
                raise KeyError("The key 'type' is missing from the rule configuration.")
            rule = cast(Mapping[str, ValueTypes], rule)
            if rule["type"] == RuleType.detection:
                rules.append(RuleDetector(logger, rule, dependencies))
            elif rule["type"] == RuleType.classification:
                rules.append(RuleClassifier(logger, rule, dependencies))
            elif rule["type"] == RuleType.time:
                rules.append(RuleTime(logger, rule))
            elif rule["type"] == RuleType.tracker:
                rules.append(RuleTracker(logger, rule, dependencies))
            elif rule["type"] == RuleType.call:
                rules.append(RuleCall(logger, rule, dependencies))
            else:
                raise ValueError(f"Invalid rule type: {rule['type']}")
        return rules
    @staticmethod
    def parse_notifiers(logger:Logger, config:Mapping[str, ValueTypes], dependencies:Mapping[str, Resource]) -> list[Notifier]:
        if "notifications" not in config:
            raise KeyError("The key 'notifications' is missing from the event configuration.")
        if not isinstance(config["notifications"], list):
            raise TypeError("The value for 'notifications' must be a list.")
        notifiers = []
        for notification_config in config["notifications"]:
            if not isinstance(notification_config, dict):
                raise TypeError("Each notification in 'notifications' must be a dictionary.")
            if "type" not in notification_config:
                raise KeyError("The key 'type' is missing from the notification configuration.")
            notifiers.append(Notifier.from_config(logger, notification_config, dependencies))
        return notifiers
    @staticmethod
    def parse_actions(logger:Logger, config:Mapping[str, ValueTypes], dependencies:Mapping[str, Resource]) -> list[Action]:
        actions = []
        if "actions" in config:
            if not isinstance(config["actions"], list):
                raise TypeError("The value for 'actions' must be a list.")
            for action in config["actions"]:
                if not isinstance(action, dict):
                    raise TypeError("Each action in 'actions' must be a dictionary.")
                actions.append(Action(logger, action, dependencies))
        return actions
    @staticmethod
    def parse_trigger_sequence_count(config:Mapping[str, ValueTypes], default_value:int=1) -> int:
        if "trigger_sequence_count" in config:
            if not isinstance(config["trigger_sequence_count"], (int,float,str)):
                raise TypeError("The value for 'trigger_sequence_count' must be an integer.")
            return int(config["trigger_sequence_count"])
        return default_value

class Event():
    logger: Logger
    name: str
    state: EventState = EventState.paused
    capture_video: bool = False
    video_capture_resource: ResourceBase|None = None
    event_video_capture_padding_secs: float = 10
    pause_alerting_on_event_secs: float = 300
    detection_hz: int = 5
    is_triggered: bool = False
    last_triggered: float = 0
    paused_until: float = 0
    pause_reason: str = ""
    modes: list[str] = [MODE_INACTIVE]
    rule_logic_type: RuleLogicType = RuleLogicType.AND
    rules: list[RuleDetector|RuleClassifier|RuleTime|RuleTracker|RuleCall]
    notifiers: list[Notifier]
    actions: list[Action]
    actions_paused: bool = False
    triggered_rules:list[dict[str, Any]] = []
    triggered_camera: str = ""
    triggered_label: str = ""
    trigger_sequence_count: int = 1
    sequence_count_current: int = 0
    resources: Mapping[str, Resource]

    def __init__(self, logger:Logger, config: Mapping[str, ValueTypes], dependencies: Mapping[str, Resource]):
        if logger is None:
            raise ValueError("The logger cannot be None.")
        if not isinstance(logger, Logger):
            raise TypeError("The logger must be an instance of Logger.")
        self.logger = logger
        self.name = EventConfigParser.parse_name(config)
        self.state = EventConfigParser.parse_state(config)
        self.capture_video = EventConfigParser.parse_capture_video(config)
        self.video_capture_resource = EventConfigParser.parse_video_capture_resource(config, dependencies)
        self.event_video_capture_padding_secs = EventConfigParser.parse_event_video_capture_padding_secs(config, self.event_video_capture_padding_secs)
        self.pause_alerting_on_event_secs = EventConfigParser.parse_pause_alerting_on_event_secs(config, self.pause_alerting_on_event_secs)
        self.detection_hz = EventConfigParser.parse_detection_hz(config, self.detection_hz)
        self.modes = EventConfigParser.parse_modes(config)
        self.rule_logic_type = EventConfigParser.parse_rule_logic_type(config, RuleLogicType.AND)
        self.rules = EventConfigParser.parse_rules(logger, config, dependencies)
        self.notifiers = EventConfigParser.parse_notifiers(logger, config, dependencies)
        self.actions = EventConfigParser.parse_actions(logger, config, dependencies)
        self.trigger_sequence_count = EventConfigParser.parse_trigger_sequence_count(config, 1)
        

    def flip_action_status(self, direction:bool):
        action:Action
        for action in self.actions:
            action.taken = direction
    
    
