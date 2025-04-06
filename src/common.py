from enum import Enum

from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase

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
