import json
from typing import Mapping
from unittest.mock import MagicMock, AsyncMock

from viam.components.camera.client import CameraClient as Camera
from viam.components.generic.client import GenericClient as GenericComponent
from viam.components.sensor.client import SensorClient as Sensor
from viam.resource.base import ResourceBase
from viam.services.generic.client import GenericClient as GenericService
from viam.services.vision import VisionClient as Vision
from viam.utils import ValueTypes

from src.common import Resource, ResourceSubType, ResourceType


def read_config(file_path: str) -> dict[str, ValueTypes]:
    with open(file_path, 'r') as file:
        return json.load(file)

def mock_resource(resource_name: str, resource_type:ResourceType=ResourceType.component, resource_sub_type:ResourceSubType=ResourceSubType.generic, exception:Exception|None=None) -> Resource:
    # This function should return a mapping of resource names to resource objects.
    resource:ResourceBase|None = None
    match resource_type:
        case ResourceType.component:
            match resource_sub_type:
                case ResourceSubType.generic:
                    resource = MagicMock(spec=GenericComponent)
                case ResourceSubType.camera:
                    resource = MagicMock(spec=Camera)
                case ResourceSubType.sensor:
                    resource = MagicMock(spec=Sensor)
                case _:
                    raise ValueError(f"Unknown component subtype: {resource_sub_type}")
        case ResourceType.service:
            match resource_sub_type:
                case ResourceSubType.generic:
                    resource = MagicMock(spec=GenericService)
                case ResourceSubType.vision:
                    resource = MagicMock(spec=Vision)
                case _:
                    raise ValueError(f"Unknown service subtype: {resource_sub_type}")
        case _:
            raise ValueError(f"Unknown resource type: {resource_type}")
    resource.name = resource_name
    resource.type = resource_type
    resource.sub_type = resource_sub_type
    resource.do_command = AsyncMock(return_value = {}, side_effect=exception)
    resource.get_readings = AsyncMock(return_value = {}, side_effect=exception)
    
    return Resource(resource_type, resource_sub_type, resource)
