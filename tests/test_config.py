import pytest
import json
from google.protobuf.json_format import ParseDict
from viam.proto.app.robot import ComponentConfig

from src.config import Config, Modes, ResourceType, ResourceSubType, Resource
from src.event_manager import eventManager

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
    dependencies = {}

    # Parse the config
    config = Config(test_config, dependencies)

    assert config is not None
    assert isinstance(config, Config)
    assert config.Mode is not None
    assert config.get_effective_mode() == Modes.active
    assert len(config.Resources) == 7
    assert config.Resources["kasa_plug_1"].Type == ResourceType.component
    assert config.Resources["kasa_plug_1"].SubType == ResourceSubType.generic
    assert config.Resources["kasa_plug_2"].Type == ResourceType.component
    assert config.Resources["kasa_plug_2"].SubType == ResourceSubType.generic
    assert config.Resources["cam1"].Type == ResourceType.component
    assert config.Resources["cam1"].SubType == ResourceSubType.camera
    assert config.Resources["vcam1"].Type == ResourceType.component
    assert config.Resources["vcam1"].SubType == ResourceSubType.camera
    assert config.Resources["tracker1"].Type == ResourceType.service
    assert config.Resources["tracker1"].SubType == ResourceSubType.vision
    
    assert len(config.Events) == 3
    assert config.Events[0].name == "more than 3 results"
    assert config.Events[0].state == "paused"


