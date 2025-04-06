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
# from viam.services.mlmodel import MLModel # Importing this takes a dependency on numpy, not doing that right now.
from viam.services.motion import Motion
from viam.services.discovery import Discovery
from viam.services.navigation import Navigation
from viam.services.vision import VisionClient
from viam.services.generic import Generic as GenericService

from .events import Event
from .common import ResourceType, ResourceSubType, Resource, Modes

class ModeOverride:
    mode: Modes
    until: float

    def __init__(self, config: ComponentConfig):
        mode = config.attributes.fields.get("mode", None)
        if mode is None:
            raise ValueError("The value for 'mode' cannot be None.")
        self.mode = Modes(mode.string_value)
        
        until = config.attributes.fields.get("until", None)
        if until is None:
            raise ValueError("The value for 'until' cannot be None.")
        until_str = until.string_value
        self.until = iso8601_to_timestamp(until_str)

class Config:
    __mode: Modes
    __mode_override: str|None = None
    resources: Mapping[str, Resource]
    events: List[Event]
    sms_module: ResourceBase|None = None
    email_module: ResourceBase|None = None
    app_api_key: str|None = None
    app_api_key_id: str|None = None
    dependencies: Mapping[ResourceName, ResourceBase] = {}
    
    def __init__(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        if not isinstance(config, ComponentConfig):
            raise TypeError("The configuration must be a dictionary.")
        if not config:
            raise ValueError("The configuration cannot be empty.")
        
        # First populate the simple fields
        sms_module = config.attributes.fields.get("sms_module", None)
        if sms_module is not None and sms_module.string_value != "":
            sms_module = sms_module.string_value
            if sms_module not in dependencies:
                raise ValueError(f"SMS module '{sms_module}' not found in dependencies.")
            sms_module_name = getDependencyName(ResourceType.service, ResourceSubType.generic, sms_module)
            self.sms_module = dependencies[sms_module_name]
        email_module = config.attributes.fields.get("email_module", None)
        if email_module is not None and email_module.string_value != "":
            email_module = email_module.string_value
            if email_module not in dependencies:
                raise ValueError(f"Email module '{email_module}' not found in dependencies.")
            email_module_name = getDependencyName(ResourceType.service, ResourceSubType.generic, email_module)
            self.email_module = dependencies[email_module_name]
        app_api_key = config.attributes.fields.get("app_api_key", None)
        if app_api_key is not None and app_api_key.string_value != "":
            self.app_api_key = app_api_key.string_value
        app_api_key_id = config.attributes.fields.get("app_api_key_id", None)
        if app_api_key_id is not None and app_api_key_id.string_value != "":
            self.app_api_key_id = app_api_key_id.string_value

        self.dependencies = dependencies
        
        # Then populate the complex fields
        self.__set_mode(config)
        self.__set_resources(config, dependencies)

        # This must be done after __set_resources
        # because __set_events uses self.resources
        self.__set_events(config, self.resources)
        
    def __set_events(self, config: ComponentConfig, resources: Mapping[str, Resource]):
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
        
        self.events = []
        for event_struct in events:
            if event_struct.struct_value is None:
                raise ValueError("The value for 'events' must be a list of dictionaries.")
            event = struct_to_dict(event_struct.struct_value)
            if not isinstance(event, Mapping):
                raise TypeError("Each event must be a dictionary.")
            self.events.append(Event(event, resources))

    def __set_mode(self, config: ComponentConfig):
        if "mode" not in config.attributes.fields:
            raise KeyError("The key 'mode' is missing from the configuration.")
        mode_val = config.attributes.fields.get("mode")
        if mode_val is None:
            raise ValueError("The value for 'mode' cannot be None.")
        mode_str = mode_val.string_value
        if mode_str not in [mode.value for mode in Modes]:
            raise ValueError(f"The value for 'mode' must be one of the defined modes: {','.join(Modes.__members__.values())}")
        self.mode = Modes(mode_str)
    
    def __set_resources(self, config: ComponentConfig, deps: Mapping[ResourceName, ResourceBase]):
        if "resources" not in config.attributes.fields:
            raise KeyError("The key 'resources' is missing from the configuration.")
        resources_val = config.attributes.fields.get("resources", None)
        if resources_val is None:
            raise ValueError("The value for 'resources' cannot be None.")
        
        resources = struct_to_dict(resources_val.struct_value)
        if not isinstance(resources, Mapping):
            raise TypeError("The value for 'resources' must be a dictionary.")
        
        self.resources = {}
        for resource_id, resource in resources.items():
            if not isinstance(resource_id, str):
                raise TypeError("The keys of 'resources' must be strings.")
            if not isinstance(resource, Mapping):
                raise TypeError("The values of 'resources' must be dictionaries.")
            if "type" not in resource or "subtype" not in resource:
                raise KeyError("Each resource must have 'type' and 'subtype' keys.")
            if not isinstance(resource["type"], str) or not isinstance(resource["subtype"], str):
                raise TypeError("'type' and 'subtype' values must be strings.")
            depName = getDependencyName(resource["type"], resource["subtype"], resource_id)
            if depName not in deps:
                raise ValueError(f"Dependency '{depName}' not found in dependencies.")
            if deps[depName] is None:
                raise ValueError(f"Dependency '{depName}' cannot be None.")
            
            self.resources[resource_id] = Resource(
                type=ResourceType(resource["type"]),
                subtype=ResourceSubType(resource["subtype"]),
                resource=deps[depName]
            )

    @property
    def mode(self) -> Modes:
        if self.__mode_override is None:
            return self.mode
        if not isinstance(self.__mode_override, ModeOverride):
            raise TypeError("The ModeOverride must be an instance of ModeOverride.")
        if self.__mode_override.until > datetime.now().timestamp():
            return self.__mode_override.mode
        self.__mode_override = None # If the override has expired, remove it so we don't check it every time
        return self.__mode
    
    @mode.setter
    def mode(self, mode: Modes):
        if not isinstance(mode, Modes):
            raise TypeError("The mode must be an instance of Modes.")
        self.__mode = mode

def getDependencyName(type: str, subtype: str, name: str) -> ResourceName:
    if type == ResourceType.component:
        if subtype == ResourceSubType.arm:
            return Arm.get_resource_name(name)
        elif subtype == ResourceSubType.base:
            return Base.get_resource_name(name)
        elif subtype == ResourceSubType.board:
            return Board.get_resource_name(name)
        elif subtype == ResourceSubType.camera:
            return Camera.get_resource_name(name)
        elif subtype == ResourceSubType.encoder:
            return Encoder.get_resource_name(name)
        elif subtype == ResourceSubType.gantry:
            return Gantry.get_resource_name(name)
        elif subtype == ResourceSubType.generic:
            return GenericComponent.get_resource_name(name)
        elif subtype == ResourceSubType.gripper:
            return Gripper.get_resource_name(name)
        elif subtype == ResourceSubType.input_controller:
            return Controller.get_resource_name(name)
        elif subtype == ResourceSubType.motor:
            return Motor.get_resource_name(name)
        elif subtype == ResourceSubType.movement_sensor:
            return MovementSensor.get_resource_name(name)
        elif subtype == ResourceSubType.power_sensor:
            return PowerSensor.get_resource_name(name)
        elif subtype == ResourceSubType.sensor:
            return Sensor.get_resource_name(name)
        elif subtype == ResourceSubType.servo:
            return Servo.get_resource_name(name)
        else:
            raise ValueError(f"Unknown component subtype: {subtype}, name: {name}")
    elif type == ResourceType.service:
        if subtype == ResourceSubType.slam:
            return SLAM.get_resource_name(name)
        # elif subtype == ResourceSubType.mlmodel:
        #     return MLModel.get_resource_name(name)
        elif subtype == ResourceSubType.motion:
            return Motion.get_resource_name(name)
        elif subtype == ResourceSubType.discovery:
            return Discovery.get_resource_name(name)
        elif subtype == ResourceSubType.navigation:
            return Navigation.get_resource_name(name)
        elif subtype == ResourceSubType.vision:
            return VisionClient.get_resource_name(name)
        else:
            raise ValueError(f"Unknown or unsupported service subtype: {subtype}, name: {name}")
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
