import json
from typing import Callable, Mapping

import pytest
from google.protobuf.json_format import ParseDict
from helpers import mock_resource
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.types import resource_name_from_string
from src.common import ResourceSubType, ResourceType
from src.eventManager import eventManager


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
        resource_name_from_string("rdk:component:generic/kasa_plug_1"): mock_resource("kasa_plug_1", ResourceType.component, ResourceSubType.generic).resource, #type:ignore
        resource_name_from_string("rdk:component:generic/kasa_plug_2"): mock_resource("kasa_plug_2", ResourceType.component, ResourceSubType.generic).resource, #type:ignore
        resource_name_from_string("rdk:component:camera/cam1"): mock_resource("cam1", ResourceType.component, ResourceSubType.camera).resource, #type:ignore
        resource_name_from_string("rdk:component:camera/vcam1"): mock_resource("vcam1", ResourceType.component, ResourceSubType.camera).resource, #type:ignore
        resource_name_from_string("rdk:service:vision/tracker1"): mock_resource("tracker1", ResourceType.service, ResourceSubType.vision).resource, #type:ignore
        resource_name_from_string("rdk:service:vision/person_detector"): mock_resource("person_detector", ResourceType.service, ResourceSubType.vision).resource, #type:ignore
        resource_name_from_string("rdk:component:sensor/stuff_sensor"): mock_resource("stuff_sensor", ResourceType.component, ResourceSubType.sensor).resource, #type:ignore
        resource_name_from_string("rdk:service:generic/sms"): mock_resource("sms", ResourceType.service, ResourceSubType.generic).resource, #type:ignore
        resource_name_from_string("rdk:service:generic/email"): mock_resource("email", ResourceType.service, ResourceSubType.generic).resource, #type:ignore
        resource_name_from_string("rdk:component:generic/video_capture"): mock_resource("video_capture", ResourceType.component, ResourceSubType.generic).resource, #type:ignore
    }

    # Parse the config
    mgr = eventManager.new(test_config, dependencies)

    assert mgr is not None
    assert isinstance(mgr, eventManager)

    while mgr.stop_events:
        stop_event = mgr.stop_events.pop()
        stop_event.set()

