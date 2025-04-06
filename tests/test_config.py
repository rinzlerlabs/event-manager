import pytest
import json
from google.protobuf.json_format import ParseDict
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.types import resource_name_from_string
from viam.components.generic.client import GenericClient as Generic
from viam.components.camera.client import CameraClient as Camera
from viam.components.sensor.client import SensorClient as Sensor
from viam.services.vision import VisionClient as Vision
from typing import Mapping

from src.config import Config, Modes, ResourceType, ResourceSubType
from src.event_manager import eventManager
from src.rules import RuleLogicType, RuleType, RuleCall

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

def test_config_parsing():
    # Create a test ComponentConfig
    test_config = create_test_component_config()
    
    # Create a mock dependencies mapping
    dependencies:Mapping[ResourceName, ResourceBase] = {
        resource_name_from_string("rdk:component:generic/kasa_plug_1"): Generic(name="kasa_plug_1", channel=None), #type:ignore
        resource_name_from_string("rdk:component:generic/kasa_plug_2"): Generic(name="kasa_plug_2", channel=None), #type:ignore
        resource_name_from_string("rdk:component:camera/cam1"): Camera(name="cam1", channel=None), #type:ignore
        resource_name_from_string("rdk:component:camera/vcam1"): Camera(name="vcam1", channel=None), #type:ignore
        resource_name_from_string("rdk:service:vision/tracker1"): Vision(name="tracker1", channel=None), #type:ignore
        resource_name_from_string("rdk:service:vision/person_detector"): Vision(name="person_detector", channel=None), #type:ignore
        resource_name_from_string("rdk:component:sensor/stuff_sensor"): Sensor(name="stuff_sensor", channel=None), #type:ignore
    }

    # Parse the config
    config = Config(test_config, dependencies)

    assert config is not None
    assert isinstance(config, Config)
    assert config.mode is not None
    assert config.get_effective_mode() == Modes.active
    assert len(config.resources) == 7
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
    assert config.events[0].rules[0].resource == "stuff_sensor"
    assert config.events[0].rules[0].method == "get_readings"
    assert config.events[0].rules[0].result_path == "big.good"
    assert config.events[0].rules[0].result_function == "len"
    assert config.events[0].rules[0].result_operator == "gt"
    assert config.events[0].rules[0].result_value == 3
    assert config.events[0].rules[0].inverse_pause_secs == 900
    assert config.events[1].name == "a person camera 1"
    assert config.events[2].name == "a new person camera 2"

