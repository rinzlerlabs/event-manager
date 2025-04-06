from enum import Enum
from typing import Mapping

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
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.services.discovery import Discovery
from viam.services.generic import Generic as GenericService
# from viam.services.mlmodel import MLModel # Importing this takes a dependency on numpy, not doing that right now.
from viam.services.motion import Motion
from viam.services.navigation import Navigation
from viam.services.slam import SLAM
from viam.services.vision import VisionClient


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
    type: ResourceType
    sub_type: ResourceSubType
    resource: ResourceBase

    def __init__(self, type: ResourceType, subtype: ResourceSubType, resource: ResourceBase):
        if not isinstance(type, ResourceType):
            raise TypeError("The type must be an instance of ResourceType.")
        if not isinstance(subtype, ResourceSubType):
            raise TypeError("The subtype must be an instance of ResourceSubType.")
        if not isinstance(resource, ResourceBase):
            raise TypeError("The resource must be an instance of ResourceBase.")
        if not resource:
            raise ValueError("The resource cannot be None.")
        self.type = type
        self.sub_type = subtype
        self.resource = resource

    def copy(self):
        return Resource(
            type=self.type,
            subtype=self.sub_type,
            resource=self.resource
        )

class Modes(str,Enum):
    active = "active"
    inactive = "inactive"
    none = "none"

def get_dependency_resource_name(type: str, subtype: str, name: str) -> ResourceName:
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
        elif subtype == ResourceSubType.generic:
            return GenericService.get_resource_name(name)
        else:
            raise ValueError(f"Unknown or unsupported service subtype: {subtype}, name: {name}")
    else:
        raise ValueError(f"Unknown resource type: {type}")

def get_resource_base_from_resource_map_by_name(name:str, dependencies:Mapping[ResourceName, ResourceBase]) -> ResourceBase:
    """Get the dependency from the name
    Args:
        name (str): The name of the dependency
        dependencies (Mapping[ResourceName, ResourceBase]): The dependencies
    Returns:
        ResourceBase: The dependency
    Raises:
        TypeError: If the name is not a string or if the dependencies are not a mapping
        ValueError: If the dependency is not found
    """
    if not isinstance(name, str):
        raise TypeError("The name must be a string.")
    if not isinstance(dependencies, Mapping):
        raise TypeError("The dependencies must be a mapping.")
    if not dependencies:
        raise ValueError("The dependencies cannot be empty.")
    for depName, dep in dependencies.items():
        if depName.name == name:
            return dep
    raise ValueError(f"Dependency with name {name} not found in dependencies.")

def get_resource_from_resource_map_by_name(name:str, dependencies:Mapping[str, Resource]) -> Resource:
    """Get the dependency from the name
    Args:
        name (str): The name of the dependency
        dependencies (Mapping[str, Resource]): The dependencies
    Returns:
        ResourceBase: The dependency
    Raises:
        TypeError: If the name is not a string or if the dependencies are not a mapping
        ValueError: If the dependency is not found
    """
    if not isinstance(name, str):
        raise TypeError("The name must be a string.")
    if not isinstance(dependencies, Mapping):
        raise TypeError("The dependencies must be a mapping.")
    if not dependencies:
        raise ValueError("The dependencies cannot be empty.")
    for depName, dep in dependencies.items():
        if dep.resource.name == name:
            return dep
    raise ValueError(f"Dependency with name {name} not found in dependencies.")
