import json
import logging
from typing import Mapping, Callable
from datetime import datetime, timedelta
from dateutil import parser as dateutil

from google.protobuf.json_format import ParseDict
import pytest
from helpers import mock_resource
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.types import resource_name_from_string
from src.common import MODE_ACTIVE, MODE_INACTIVE, Resource, ResourceSubType, ResourceType
from src.config import Config, ModeOverride
from src.rules import Operator, RuleCall, RuleLogicType, RuleType


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
    logger = logging.getLogger(__name__)
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
    with pytest.raises(ValueError, match="The logger cannot be None."):
        config = Config(None, test_config, dependencies) # type:ignore
    with pytest.raises(TypeError, match="The logger must be an instance of Logger."):
        config = Config("not a logger", test_config, dependencies) # type:ignore

    with pytest.raises(TypeError, match="The configuration must be a dictionary."):
        config = Config(logger, "not a config", dependencies) # type:ignore
    with pytest.raises(ValueError, match="The configuration cannot be empty."):
        config = Config(logger, None, dependencies) # type:ignore
    with pytest.raises(ValueError, match="The configuration cannot be empty."):
        config = Config(logger, {}, dependencies) # type:ignore

    config = Config(logger, test_config, dependencies)

    assert config is not None
    assert isinstance(config, Config)
    assert config.mode is not None
    assert config.mode == MODE_ACTIVE
    
    assert len(config.events) == 3
    assert config.events[0].name == "more than 3 results"
    assert set(config.events[0].modes) == set([MODE_ACTIVE])
    assert config.events[0].pause_alerting_on_event_secs == 300
    assert config.events[0].detection_hz == 1
    assert config.events[0].trigger_sequence_count == 2
    assert config.events[0].sequence_count_current == 0
    assert config.events[0].rule_logic_type == RuleLogicType.AND
    assert len(config.events[0].rules) == 1
    assert config.events[0].rules[0].type == RuleType.call
    assert isinstance(config.events[0].rules[0], RuleCall)
    assert isinstance(config.events[0].rules[0].resource, Resource)
    assert isinstance(config.events[0].rules[0].resource.resource, ResourceBase)
    assert config.events[0].rules[0].resource.resource.name == "stuff_sensor"
    assert isinstance(config.events[0].rules[0].method, Callable)
    assert config.events[0].rules[0].result_path == "big.good"
    assert config.events[0].rules[0].result_function == "len"
    assert config.events[0].rules[0].result_operator == Operator.gt
    assert config.events[0].rules[0].result_value == 3
    assert config.events[0].rules[0].inverse_pause_secs == 900
    assert config.events[1].name == "a person camera 1"
    assert config.events[2].name == "a new person camera 2"

def test_config_get_mode():
    logger = logging.getLogger(__name__)
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

    config = Config(logger, test_config, dependencies)

    assert config is not None
    assert isinstance(config, Config)
    assert config.mode is not None
    assert config.mode == MODE_ACTIVE
    config._Config__mode_override = "test" # type:ignore
    with pytest.raises(TypeError, match="The ModeOverride must be an instance of ModeOverride."):
        assert config.mode == MODE_ACTIVE

    config._Config__mode_override = ModeOverride(test_config)
    assert config.mode == MODE_ACTIVE # this should clear out the override as the timestamp in the json config file is in the past
    assert config._Config__mode_override is None

    mode_override_config = test_config.attributes.fields["mode_override"]
    mode_override_config.struct_value.fields["until"].string_value = (datetime.now().astimezone() + timedelta(seconds=1000)).isoformat()
    
    config._Config__mode_override = ModeOverride(test_config)
    assert config.mode == MODE_INACTIVE

    mode_override_config = test_config.attributes.fields["mode_override"]
    mode_override_config.struct_value.fields["until"].string_value = (datetime.now() + timedelta(seconds=1000)).isoformat()

    with pytest.raises(ValueError, match="The value for 'until' must be a timezone-aware datetime."):
        Config(logger, test_config, dependencies)


def test_config_set_mode():
    logger = logging.getLogger(__name__)
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

    config = Config(logger, test_config, dependencies)
    assert config is not None
    assert isinstance(config, Config)
    assert config.mode == MODE_ACTIVE

    with pytest.raises(TypeError, match="The mode must be an instance of string."):
        config.mode = {} # type:ignore

def test_config_no_sms_module_in_dependencies_but_in_config():
    logger = logging.getLogger(__name__)
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
        resource_name_from_string("rdk:component:generic/video_capture"): mock_resource("video_capture", ResourceType.component, ResourceSubType.generic).resource, #type:ignore
    }

    with pytest.raises(ValueError, match="SMS module 'sms' not found in dependencies."):
        Config(logger, test_config, dependencies)

def test_config_no_email_module_in_dependencies_but_in_config():
    logger = logging.getLogger(__name__)
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
        resource_name_from_string("rdk:service:generic/sms"): mock_resource("sms", ResourceType.service, ResourceSubType.generic).resource, #type:ignore
        resource_name_from_string("rdk:component:sensor/stuff_sensor"): mock_resource("stuff_sensor", ResourceType.component, ResourceSubType.sensor).resource, #type:ignore
        resource_name_from_string("rdk:component:generic/video_capture"): mock_resource("video_capture", ResourceType.component, ResourceSubType.generic).resource, #type:ignore
    }

    with pytest.raises(ValueError, match="Email module 'email' not found in dependencies."):
        Config(logger, test_config, dependencies)

