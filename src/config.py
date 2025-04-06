from enum import Enum
from typing import List, Mapping, cast
import re
from datetime import datetime, timezone, timedelta

from viam.utils import ValueTypes, struct_to_dict

from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase

from .events import Event
from .common import ResourceType, ResourceSubType, Resource, Modes, get_dependency_resource_name

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
    
    def __init__(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        if not isinstance(config, ComponentConfig):
            raise TypeError("The configuration must be a dictionary.")
        if not config:
            raise ValueError("The configuration cannot be empty.")
        
        # First populate the simple fields
        app_api_key = config.attributes.fields.get("app_api_key", None)
        if app_api_key is not None and app_api_key.string_value != "":
            self.app_api_key = app_api_key.string_value
        app_api_key_id = config.attributes.fields.get("app_api_key_id", None)
        if app_api_key_id is not None and app_api_key_id.string_value != "":
            self.app_api_key_id = app_api_key_id.string_value

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
    
    def __set_resources(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
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
            depName = get_dependency_resource_name(resource["type"], resource["subtype"], resource_id)
            if depName not in dependencies:
                raise ValueError(f"Dependency '{depName}' not found in dependencies.")
            if dependencies[depName] is None:
                raise ValueError(f"Dependency '{depName}' cannot be None.")
            
            self.resources[resource_id] = Resource(
                type=ResourceType(resource["type"]),
                subtype=ResourceSubType(resource["subtype"]),
                resource=dependencies[depName]
            )
        
        # Now add the SMS and Email modules
        sms_module = config.attributes.fields.get("sms_module", None)
        if sms_module is not None and sms_module.string_value != "":
            sms_module = sms_module.string_value
            sms_module_name = get_dependency_resource_name(ResourceType.service, ResourceSubType.generic, sms_module)
            if sms_module_name not in dependencies:
                raise ValueError(f"SMS module '{sms_module_name}' not found in dependencies.")
            self.resources["sms_module"] = Resource(ResourceType.component, ResourceSubType.generic, dependencies[sms_module_name])
        email_module = config.attributes.fields.get("email_module", None)
        if email_module is not None and email_module.string_value != "":
            email_module = email_module.string_value
            email_module_name = get_dependency_resource_name(ResourceType.service, ResourceSubType.generic, email_module)
            if email_module_name not in dependencies:
                raise ValueError(f"Email module '{email_module_name}' not found in dependencies.")
            self.resources["email_module"] = Resource(ResourceType.component, ResourceSubType.generic, dependencies[email_module_name])

    @property
    def mode(self) -> Modes:
        if self.__mode_override is None:
            return self.__mode
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
