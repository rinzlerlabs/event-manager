import asyncio
import json
import time
from typing import Callable, Dict, Mapping

import pytest
from google.protobuf.json_format import ParseDict
from helpers import mock_resource
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.types import resource_name_from_string
from src.common import ResourceSubType, ResourceType
from src.eventManager import eventManager
from src.event import EventState
from logging import getLogger
from viam.utils import ValueTypes
from unittest.mock import AsyncMock, patch


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

    mgr.stop_running_tasks()

# TODO: This test is not complete and needs to be improved
@pytest.mark.asyncio
async def test_get_readings():
    # Create a test ComponentConfig
    test_config = create_test_component_config()

    # Create a mock dependencies mapping
    dependencies:Mapping[ResourceName, ResourceBase] = {
        resource_name_from_string("rdk:component:generic/kasa_plug_1"): mock_resource("kasa_plug_1", ResourceType.component, ResourceSubType.generic).resource, #type:ignore
        resource_name_from_string("rdk:component:generic/kasa_plug_2"): mock_resource("kasa_plug_2", ResourceType.component, ResourceSubType.generic).resource, #type:ignore
        resource_name_from_string("rdk:component:camera/cam1"): mock_resource("cam1", ResourceType.component, ResourceSubType.camera).resource, #type:ignore
        resource_name_from_string("rdk:component:camera/vcam1"): mock_resource("vcam_1", ResourceType.component, ResourceSubType.camera).resource, #type:ignore
        resource_name_from_string("rdk:service:vision/tracker1"): mock_resource("tracker1", ResourceType.service, ResourceSubType.vision).resource, #type:ignore
        resource_name_from_string("rdk:service:vision/person_detector"): mock_resource("person_detector", ResourceType.service, ResourceSubType.vision).resource, #type:ignore
        resource_name_from_string("rdk:component:sensor/stuff_sensor"): mock_resource("stuff_sensor", ResourceType.component, ResourceSubType.sensor).resource, #type:ignore
        resource_name_from_string("rdk:service:generic/sms"): mock_resource("sms_module", ResourceType.service, ResourceSubType.generic).resource, #type:ignore
        resource_name_from_string("rdk:service:generic/email"): mock_resource("email_module", ResourceType.service, ResourceSubType.generic).resource, #type:ignore
        resource_name_from_string("rdk:component:generic/video_capture"): mock_resource("video_capture", ResourceType.component, ResourceSubType.generic).resource, #type:ignore
    }

    test_config.attributes["app_api_key"] = ""
    test_config.attributes["app_api_key_id"] = ""
    # We need to mock out the viam client so we can test the event manager without needing a real connection
    # Create a new event manager
    mgr = eventManager("eventManager")

    assert mgr is not None
    assert isinstance(mgr, eventManager)
    mgr.reconfigure_internal(test_config, dependencies)

    # Now we need to setup the event data to simulate the readings
    trigger_time = 1744133296.8066537

    event = mgr.config.events[0]
    event.state = EventState.triggered
    event.last_triggered = trigger_time
    event.triggered_label = "bob"
    event.triggered_camera = "cam1"
    event.triggered_rules = [{"triggered": True, "resource": "cam1", "image": "<image_data>", "value": "bob"}]
    event.pause_reason = "isaidso"
    readings = await mgr.get_readings(extra={"include_dot": True})
    assert readings is not None
    state = readings["state"]
    assert state is not None
    assert isinstance(state, Mapping)
    event_state = state[event.name]
    assert event_state is not None
    assert isinstance(event_state, Mapping)
    assert event_state["state"] == "triggered"
    assert event_state["last_triggered"] == '2025-04-08T17:28:16+00:00Z'
    assert event_state["triggered_label"] == "bob"
    assert event_state["triggered_camera"] == "cam1"
    assert event_state["triggered_rules"] == [{"triggered": True, "resource": "cam1", "image": "<image_data>", "value": "bob"}]
    assert event_state["pause_reason"] == "isaidso"
    mgr.logger.info(readings)
    
@pytest.mark.asyncio
async def test_viam_connect_success():
    mock_client = AsyncMock()
    mock_create_from_dial_options = AsyncMock(return_value=mock_client)
    mock_dial_options = AsyncMock()
    mock_dial_options_with_api_key = AsyncMock(return_value=mock_dial_options)

    with patch("src.eventManager.DialOptions.with_api_key", mock_dial_options_with_api_key):
        with patch("src.eventManager.ViamClient.create_from_dial_options", mock_create_from_dial_options):
            # Create an instance of eventManager
            manager = eventManager("test_manager")
            manager.config = AsyncMock()
            manager.config.app_api_key = "test_api_key"
            manager.config.app_api_key_id = "test_api_key_id"

            # Call the viam_connect method
            client = await manager.viam_connect()

            # Assertions
            mock_dial_options_with_api_key.assert_called_once_with(api_key="test_api_key", api_key_id="test_api_key_id")
            mock_create_from_dial_options.assert_called_once()
            assert client == mock_client

@pytest.mark.asyncio
async def test_viam_connect_missing_api_key():
    manager = eventManager("test_manager")
    manager.config = AsyncMock()
    manager.config.app_api_key = None
    manager.config.app_api_key_id = "test_api_key_id"

    with pytest.raises(ValueError, match="App API Key and App API Key ID are required for cloud connection."):
        await manager.viam_connect()

@pytest.mark.asyncio
async def test_viam_connect_missing_api_key_id():
    manager = eventManager("test_manager")
    manager.config = AsyncMock()
    manager.config.app_api_key = "test_api_key"
    manager.config.app_api_key_id = None

    with pytest.raises(ValueError, match="App API Key and App API Key ID are required for cloud connection."):
        await manager.viam_connect()
