import json
from google.protobuf.json_format import ParseDict
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.types import resource_name_from_string
from viam.components.generic.client import GenericClient as GenericComponent
from viam.components.camera.client import CameraClient as Camera
from viam.components.sensor.client import SensorClient as Sensor
from viam.services.generic.client import GenericClient as GenericService
from viam.services.vision import VisionClient as Vision
from typing import Mapping

from unittest.mock import MagicMock

from src.config import Config, Modes, ResourceType, ResourceSubType
from src.event_manager import eventManager
from src.rules import RuleLogicType, RuleType, RuleCall, Operator

def create_test_component_config() -> ComponentConfig:
    # Load the JSON string into a Python dictionary
    with open('tests/sample_config.json', 'r') as file:
        json_data = file.read()
    data = json.loads(json_data)
    
    # Create an empty ComponentConfig object
    config = ComponentConfig()
    
    # Parse the dictionary into the ComponentConfig object
    ParseDict(data, config.attributes)
    
    return config

def mock_generic_component(name: str) -> GenericComponent:
    """Mock a GenericComponent for testing."""
    component = MagicMock(spec=GenericComponent)
    component.name = name
    component.type = ResourceType.component
    component.sub_type = ResourceSubType.generic
    component.do_command = MagicMock(return_value = {})
    return component
def mock_camera(name: str) -> Camera:
    """Mock a Camera for testing."""
    camera = MagicMock(spec=Camera)
    camera.name = name
    camera.type = ResourceType.component
    camera.sub_type = ResourceSubType.camera
    camera.do_command = MagicMock(return_value = {})
    return camera
def mock_sensor(name: str) -> Sensor:
    """Mock a Sensor for testing."""
    sensor = MagicMock(spec=Sensor)
    sensor.name = name
    sensor.type = ResourceType.component
    sensor.sub_type = ResourceSubType.sensor
    sensor.do_command = MagicMock(return_value = {})
    return sensor
def mock_vision(name: str) -> Vision:
    """Mock a Vision for testing."""
    vision = MagicMock(spec=Vision)
    vision.name = name
    vision.type = ResourceType.service
    vision.sub_type = ResourceSubType.vision
    vision.do_command = MagicMock(return_value = {})
    return vision
def mock_generic_service(name: str) -> GenericService:
    """Mock a GenericService for testing."""
    service = MagicMock(spec=GenericService)
    service.name = name
    service.type = ResourceType.service
    service.sub_type = ResourceSubType.generic
    service.do_command = MagicMock(return_value = {})
    return service

def test_config_parsing():
    # Create a test ComponentConfig
    test_config = create_test_component_config()
    
    # Create a mock dependencies mapping
    dependencies:Mapping[ResourceName, ResourceBase] = {
        resource_name_from_string("rdk:component:generic/kasa_plug_1"): mock_generic_component(name="kasa_plug_1"), #type:ignore
        resource_name_from_string("rdk:component:generic/kasa_plug_2"): mock_generic_component(name="kasa_plug_2"), #type:ignore
        resource_name_from_string("rdk:component:camera/cam1"): mock_camera(name="cam1"), #type:ignore
        resource_name_from_string("rdk:component:camera/vcam1"): mock_camera(name="vcam1"), #type:ignore
        resource_name_from_string("rdk:service:vision/tracker1"): mock_vision(name="tracker1"), #type:ignore
        resource_name_from_string("rdk:service:vision/person_detector"): mock_vision(name="person_detector"), #type:ignore
        resource_name_from_string("rdk:component:sensor/stuff_sensor"): mock_sensor(name="stuff_sensor"), #type:ignore
        resource_name_from_string("rdk:service:generic/sms"): mock_generic_service(name="sms"), #type:ignore
        resource_name_from_string("rdk:service:generic/email"): mock_generic_service(name="email"), #type:ignore
        resource_name_from_string("rdk:component:generic/video_capture"): mock_generic_component(name="video_capture"), #type:ignore
    }

    # Parse the config
    config = Config(test_config, dependencies)

    assert config is not None
    assert isinstance(config, Config)
    assert config.mode is not None
    assert config.mode == Modes.active
    assert len(config.resources) == 9
    assert config.resources["kasa_plug_1"].type == ResourceType.component
    assert config.resources["kasa_plug_1"].sub_type == ResourceSubType.generic
    assert config.resources["kasa_plug_2"].type == ResourceType.component
    assert config.resources["kasa_plug_2"].sub_type == ResourceSubType.generic
    assert config.resources["cam1"].type == ResourceType.component
    assert config.resources["cam1"].sub_type == ResourceSubType.camera
    assert config.resources["vcam1"].type == ResourceType.component
    assert config.resources["vcam1"].sub_type == ResourceSubType.camera
    assert config.resources["tracker1"].type == ResourceType.service
    assert config.resources["tracker1"].sub_type == ResourceSubType.vision
    assert config.resources["sms_module"].type == ResourceType.component # I'm not sure if this is correct
    assert config.resources["sms_module"].sub_type == ResourceSubType.generic
    assert config.resources["email_module"].type == ResourceType.component # I'm not sure if this is correct
    assert config.resources["email_module"].sub_type == ResourceSubType.generic
    
    assert len(config.events) == 3
    assert config.events[0].name == "more than 3 results"
    assert set(config.events[0].modes) == set([Modes.inactive, Modes.active])
    assert config.events[0].pause_alerting_on_event_secs == 300
    assert config.events[0].detection_hz == 1
    assert config.events[0].trigger_sequence_count == 2
    assert config.events[0].sequence_count_current == 0
    assert config.events[0].rule_logic_type == RuleLogicType.AND
    assert len(config.events[0].rules) == 1
    assert config.events[0].rules[0].type == RuleType.call
    assert isinstance(config.events[0].rules[0], RuleCall)
    assert isinstance(config.events[0].rules[0].resource, ResourceBase)
    assert config.events[0].rules[0].resource.name == "stuff_sensor"
    assert config.events[0].rules[0].method == "get_readings"
    assert config.events[0].rules[0].result_path == "big.good"
    assert config.events[0].rules[0].result_function == "len"
    assert config.events[0].rules[0].result_operator == Operator.gt
    assert config.events[0].rules[0].result_value == 3
    assert config.events[0].rules[0].inverse_pause_secs == 900
    assert config.events[1].name == "a person camera 1"
    assert config.events[2].name == "a new person camera 2"

