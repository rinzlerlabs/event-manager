from enum import Enum
from typing import List, Mapping, cast
import re
from datetime import datetime, timezone, timedelta

from viam.utils import ValueTypes, struct_to_dict

from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.components.arm import Arm
from viam.components.base import Base
from viam.components.board import Board
from viam.components.camera import Camera
from viam.components.encoder import Encoder
from viam.components.gantry import Gantry
from viam.components.generic import Generic as GenericComponent
from viam.components.gripper import Gripper
from viam.components.input.input import Controller
from viam.components.motor import Motor
from viam.components.movement_sensor import MovementSensor
from viam.components.power_sensor import PowerSensor
from viam.components.sensor import Sensor
from viam.components.servo import Servo
from viam.services.slam import SLAM
from viam.services.mlmodel import MLModel
from viam.services.motion import Motion
from viam.services.discovery import Discovery
from viam.services.navigation import Navigation
from viam.services.vision import VisionClient


from src.events import Event

class Modes(str,Enum):
    active = "active"
    inactive = "inactive"
    none = "none"

class ResourceType(str, Enum):
    component = "component"
    service = "service"

class ResourceSubType(str, Enum):
    # Component types
    arm = "arm"
    base = "base"
    board = "board"
    button = "button"
    camera = "camera"
    encoder = "encoder"
    gantry = "gantry"
    generic = "generic"
    gripper = "gripper"
    input_controller = "input_controller"
    motor = "motor"
    movement_sensor = "movement_sensor"
    power_sensor = "power_sensor"
    sensor = "sensor"
    servo = "servo"
    switch = "switch"
    unknown = "unknown"
    # Service types
    slam = "slam"
    mlmodel = "mlmodel"
    motion = "motion"
    pose_tracker = "pose_tracker"
    discovery = "discovery"
    navigation = "navigation"
    vision = "vision"

class Resource:
    Type: ResourceType
    SubType: ResourceSubType
    Resource: ResourceBase

    def __init__(self, type: ResourceType, subtype: ResourceSubType, resource: ResourceBase):
        if not isinstance(type, ResourceType):
            raise TypeError("The type must be an instance of ResourceType.")
        if not isinstance(subtype, ResourceSubType):
            raise TypeError("The subtype must be an instance of ResourceSubType.")
        if not isinstance(resource, ResourceBase):
            raise TypeError("The resource must be an instance of ResourceBase.")
        if not resource:
            raise ValueError("The resource cannot be None.")
        self.Type = type
        self.SubType = subtype
        self.Resource = resource

class ModeOverride:
    Mode: Modes
    Until: float

    def __init__(self, config: ComponentConfig):
        mode = config.attributes.fields.get("mode", None)
        if mode is None:
            raise ValueError("The value for 'mode' cannot be None.")
        self.Mode = Modes(mode.string_value)
        
        until = config.attributes.fields.get("until", None)
        if until is None:
            raise ValueError("The value for 'until' cannot be None.")
        until_str = until.string_value
        self.Until = iso8601_to_timestamp(until_str)

class Config:
    Mode: Modes
    ModeOverride: str|None = None
    Resources: Mapping[str, Resource]
    Events: List[Event]
    SmsModuleName: str|None = None
    EmailModuleName: str|None = None
    AppApiKey: str|None = None
    AppApiKeyId: str|None = None
    Dependencies: Mapping[ResourceName, ResourceBase] = {}
    
    def __init__(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        if not isinstance(config, ComponentConfig):
            raise TypeError("The configuration must be a dictionary.")
        if not config:
            raise ValueError("The configuration cannot be empty.")
        
        # First populate the simple fields
        sms_module = config.attributes.fields.get("sms_module", None)
        if sms_module is not None and sms_module.string_value != "":
            self.SmsModuleName = sms_module.string_value
        email_module = config.attributes.fields.get("email_module", None)
        if email_module is not None and email_module.string_value != "":
            self.EmailModuleName = email_module.string_value
        app_api_key = config.attributes.fields.get("app_api_key", None)
        if app_api_key is not None and app_api_key.string_value != "":
            self.AppApiKey = app_api_key.string_value
        app_api_key_id = config.attributes.fields.get("app_api_key_id", None)
        if app_api_key_id is not None and app_api_key_id.string_value != "":
            self.AppApiKeyId = app_api_key_id.string_value

        self.Dependencies = dependencies
        
        # Then populate the complex fields
        self.__set_mode(config)
        self.__set_resources(config, dependencies)
        self.__set_events(config)
        
    def __set_events(self, config: ComponentConfig):
        if "events" not in config.attributes.fields:
            raise KeyError("The key 'events' is missing from the configuration.")
        events_val = config.attributes.fields.get("events", None)
        if events_val is None:
            raise ValueError("The value for 'events' cannot be None.")
        if events_val.list_value is None:
            raise ValueError("The value for 'events' must be a list.")
        events = events_val.list_value.values
        if events is None:
            raise ValueError("The value for 'events' cannot be None.")
        
        self.Events = []
        for event_struct in events:
            if event_struct.struct_value is None:
                raise ValueError("The value for 'events' must be a list of dictionaries.")
            event = struct_to_dict(event_struct.struct_value)
            if not isinstance(event, Mapping):
                raise TypeError("Each event must be a dictionary.")
            self.Events.append(Event(**event))

    def __set_mode(self, config: ComponentConfig):
        if "mode" not in config.attributes.fields:
            raise KeyError("The key 'mode' is missing from the configuration.")
        mode_val = config.attributes.fields.get("mode")
        if mode_val is None:
            raise ValueError("The value for 'mode' cannot be None.")
        mode_str = mode_val.string_value
        if mode_str not in [mode.value for mode in Modes]:
            raise ValueError(f"The value for 'mode' must be one of the defined modes: {','.join(Modes.__members__.values())}")
        self.Mode = Modes(mode_str)
    
    def __set_resources(self, config: ComponentConfig, deps: Mapping[ResourceName, ResourceBase]):
        if "resources" not in config.attributes.fields:
            raise KeyError("The key 'resources' is missing from the configuration.")
        resources_val = config.attributes.fields.get("resources", None)
        if resources_val is None:
            raise ValueError("The value for 'resources' cannot be None.")
        
        resources = struct_to_dict(resources_val.struct_value)
        if not isinstance(resources, Mapping):
            raise TypeError("The value for 'resources' must be a dictionary.")
        
        self.Resources = {}
        for resource_id, resource in resources.items():
            if not isinstance(resource_id, str):
                raise TypeError("The keys of 'resources' must be strings.")
            if not isinstance(resource, Mapping):
                raise TypeError("The values of 'resources' must be dictionaries.")
            if "type" not in resource or "subtype" not in resource:
                raise KeyError("Each resource must have 'type' and 'subtype' keys.")
            if not isinstance(resource["type"], str) or not isinstance(resource["subtype"], str):
                raise TypeError("'type' and 'subtype' values must be strings.")
            depName = getDependencyName(resource["type"], resource["subtype"])
            if depName not in deps:
                raise ValueError(f"Dependency '{depName}' not found in dependencies.")
            
            self.Resources[resource_id] = Resource(
                type=ResourceType(resource["type"]),
                subtype=ResourceSubType(resource["subtype"]),
                resource=deps[depName]
            )

    def get_effective_mode(self):
        if self.ModeOverride is None:
            return self.Mode
        if not isinstance(self.ModeOverride, ModeOverride):
            raise TypeError("The ModeOverride must be an instance of ModeOverride.")
        if self.ModeOverride.Until < datetime.now().timestamp():
            return self.Mode
        return self.ModeOverride.Mode

def getDependencyName(type: str, subtype: str):
    if type == ResourceType.component:
        if subtype == ResourceSubType.arm:
            return Arm.get_resource_name(subtype)
        elif subtype == ResourceSubType.base:
            return Base.get_resource_name(subtype)
        elif subtype == ResourceSubType.board:
            return Board.get_resource_name(subtype)
        elif subtype == ResourceSubType.camera:
            return Camera.get_resource_name(subtype)
        elif subtype == ResourceSubType.encoder:
            return Encoder.get_resource_name(subtype)
        elif subtype == ResourceSubType.gantry:
            return Gantry.get_resource_name(subtype)
        elif subtype == ResourceSubType.generic:
            return GenericComponent.get_resource_name(subtype)
        elif subtype == ResourceSubType.gripper:
            return Gripper.get_resource_name(subtype)
        elif subtype == ResourceSubType.input_controller:
            return Controller.get_resource_name(subtype)
        elif subtype == ResourceSubType.motor:
            return Motor.get_resource_name(subtype)
        elif subtype == ResourceSubType.movement_sensor:
            return MovementSensor.get_resource_name(subtype)
        elif subtype == ResourceSubType.power_sensor:
            return PowerSensor.get_resource_name(subtype)
        elif subtype == ResourceSubType.sensor:
            return Sensor.get_resource_name(subtype)
        elif subtype == ResourceSubType.servo:
            return Servo.get_resource_name(subtype)
        else:
            raise ValueError(f"Unknown component subtype: {subtype}")
    elif type == ResourceType.service:
        if subtype == ResourceSubType.slam:
            return SLAM.get_resource_name(subtype)
        elif subtype == ResourceSubType.mlmodel:
            return MLModel.get_resource_name(subtype)
        elif subtype == ResourceSubType.motion:
            return Motion.get_resource_name(subtype)
        elif subtype == ResourceSubType.discovery:
            return Discovery.get_resource_name(subtype)
        elif subtype == ResourceSubType.navigation:
            return Navigation.get_resource_name(subtype)
        elif subtype == ResourceSubType.vision:
            return VisionClient.get_resource_name(subtype)
        else:
            raise ValueError(f"Unknown service subtype: {subtype}")
    else:
        raise ValueError(f"Unknown resource type: {type}")

def iso8601_to_timestamp(iso8601_string):
    # Regular expression to match ISO8601 format
    iso8601_regex = r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
    match = re.match(iso8601_regex, iso8601_string)
    
    if not match:
        raise ValueError("Invalid ISO8601 format")

    year, month, day, hour, minute, second = map(int, match.groups()[:6])
    microsecond = int(float(match.group(7) or '0') * 1000000)
    tz_string = match.group(8)

    if tz_string == 'Z':
        tzinfo = timezone.utc
    elif tz_string:
        # Handle timezone offset
        tz_hours, tz_minutes = map(int, tz_string.replace(':', '')[:-2].split(':'))
        tzinfo = timezone(timedelta(hours=tz_hours, minutes=tz_minutes))
    else:
        tzinfo = None  # Naive datetime

    dt = datetime(year, month, day, hour, minute, second, microsecond, tzinfo=tzinfo)
    
    # Convert to UTC if it's not already
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc)
    
    # Return Unix timestamp
    return dt.timestamp()
