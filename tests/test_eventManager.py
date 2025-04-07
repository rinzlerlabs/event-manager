import pytest
import json
from google.protobuf.json_format import ParseDict
from viam.proto.app.robot import ComponentConfig

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
    dependencies = {}

    # Parse the config
    mgr = eventManager.new(test_config, dependencies)

    assert mgr is not None
    assert isinstance(mgr, eventManager)

    while mgr.stop_events:
        stop_event = mgr.stop_events.pop()
        stop_event.set()

