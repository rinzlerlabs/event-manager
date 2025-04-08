import logging

import pytest
from helpers import mock_resource, read_config
from typing import Mapping
from viam.utils import ValueTypes
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from src.actions import Action
from src.common import MODE_INACTIVE, Resource, ResourceType, ResourceSubType
from viam.resource.types import resource_name_from_string

from src.event import Event, EventState, EventConfigParser
from helpers import mock_resource
from src.notifications import SmsNotifier
from src.rules import RuleLogicType, RuleTime

def test_event_config_parsing():
    logger = logging.getLogger(__name__)
    config = read_config('tests/events/sample_config.json')
    resources:Mapping[str, Resource] = {
        "kasa_plug_1": mock_resource("kasa_plug_1", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic),
        "kasa_plug_2": mock_resource("kasa_plug_2", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic),
        "cam1": mock_resource("cam1", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.camera),
        "vcam1": mock_resource("vcam1", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.camera),
        "tracker1": mock_resource("tracker1", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.vision),
        "person_detector": mock_resource("person_detector", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.vision),
        "stuff_sensor": mock_resource("stuff_sensor", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.sensor),
        "sms_module": mock_resource("sms", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.generic),
        "email_module": mock_resource("email", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.generic),
        "video_capture": mock_resource("video_capture", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic)
    }
    event = Event(logger, config, resources)
    assert event is not None
    assert isinstance(event, Event)
    assert event.name == config["name"]
    assert event.state == EventState.paused
    assert event.capture_video == config["capture_video"]
    assert event.video_capture_resource == resources[str(config["video_capture_resource"])].resource
    assert event.event_video_capture_padding_secs == config["event_video_capture_padding_secs"]

def test_event_config_parsing_logger():
    config = read_config('tests/events/sample_config.json')
    with pytest.raises(ValueError, match="The logger cannot be None."):
        Event(None, config, {}) # type: ignore

    with pytest.raises(TypeError, match="The logger must be an instance of Logger."):
        Event("not_a_logger", config, {}) # type: ignore

    del config["name"]
    logger = logging.getLogger(__name__)
    with pytest.raises(KeyError, match="The key 'name' is missing from the event configuration."):
        Event(logger, config, {})

def test_event_config_parsing_name():
    config = read_config('tests/events/sample_config.json')
    
    config["name"] = 12
    with pytest.raises(TypeError, match="The value for 'name' must be a string."):
        EventConfigParser.parse_name(config)

    config["name"] = None
    with pytest.raises(TypeError, match="The value for 'name' must be a string."):
        EventConfigParser.parse_name(config)

    del config["name"]
    with pytest.raises(KeyError, match="The key 'name' is missing from the event configuration."):
        EventConfigParser.parse_name(config)

def test_event_config_parsing_state():
    config = read_config('tests/events/sample_config.json')
    
    config["state"] = 12
    with pytest.raises(TypeError, match="The value for 'state' must be a string."):
        EventConfigParser.parse_state(config)

    config["state"] = None
    with pytest.raises(TypeError, match="The value for 'state' must be a string."):
        EventConfigParser.parse_state(config)

    del config["state"]
    assert EventConfigParser.parse_state(config) == EventState.paused

    config["state"] = "setup"
    assert EventConfigParser.parse_state(config) == EventState.setup

def test_event_config_parsing_capture_video():
    config = read_config('tests/events/sample_config.json')
    
    config["capture_video"] = 12
    with pytest.raises(TypeError, match="The value for 'capture_video' must be a boolean."):
        EventConfigParser.parse_capture_video(config)

    config["capture_video"] = None
    with pytest.raises(TypeError, match="The value for 'capture_video' must be a boolean."):
        EventConfigParser.parse_capture_video(config)

    del config["capture_video"]
    assert EventConfigParser.parse_capture_video(config) == False

def test_event_config_parsing_video_capture_resource():
    config = read_config('tests/events/sample_config.json')
    original_resource = str(config["video_capture_resource"])
    
    config["video_capture_resource"] = 12
    with pytest.raises(TypeError, match="The value for 'video_capture_resource' must be a string."):
        EventConfigParser.parse_video_capture_resource(config, {})

    config["video_capture_resource"] = None
    with pytest.raises(TypeError, match="The value for 'video_capture_resource' must be a string."):
        EventConfigParser.parse_video_capture_resource(config, {})

    config["video_capture_resource"] = "non_existent_resource"
    with pytest.raises(ValueError, match="Dependency 'non_existent_resource' not found in dependencies."):
        EventConfigParser.parse_video_capture_resource(config, {})

    config["video_capture_resource"] = original_resource
    dependencies:Mapping[str, Resource] = {
        original_resource:None # type: ignore
    }
    with pytest.raises(ValueError, match=f"Dependency '{original_resource}' cannot be None."):
        EventConfigParser.parse_video_capture_resource(config, dependencies)

    dependencies:Mapping[str, Resource] = {
        original_resource: mock_resource(original_resource, resource_type=ResourceType.service, resource_sub_type=ResourceSubType.vision),
    }
    with pytest.raises(ValueError, match=f"Dependency '{original_resource}' must be a camera or generic component."):
        EventConfigParser.parse_video_capture_resource(config, dependencies)

    dependencies:Mapping[str, Resource] = {
        original_resource: mock_resource(original_resource, resource_type=ResourceType.component, resource_sub_type=ResourceSubType.sensor),
    }
    with pytest.raises(ValueError, match=f"Dependency '{original_resource}' must be a camera or generic component."):
        EventConfigParser.parse_video_capture_resource(config, dependencies)

    dependencies:Mapping[str, Resource] = {
        original_resource: mock_resource(original_resource, resource_type=ResourceType.component, resource_sub_type=ResourceSubType.camera),
    }
    assert EventConfigParser.parse_video_capture_resource(config, dependencies) == dependencies[original_resource].resource

    dependencies:Mapping[str, Resource] = {
        original_resource: mock_resource(original_resource, resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic),
    }
    assert EventConfigParser.parse_video_capture_resource(config, dependencies) == dependencies[original_resource].resource

    del config["video_capture_resource"]
    assert EventConfigParser.parse_video_capture_resource(config, dependencies) == None

def test_event_config_parsing_event_video_capture_padding_secs():
    config = read_config('tests/events/sample_config.json')
    
    config["event_video_capture_padding_secs"] = "a"
    with pytest.raises(ValueError, match="The value for 'event_video_capture_padding_secs' must be an integer."):
        EventConfigParser.parse_event_video_capture_padding_secs(config)

    config["event_video_capture_padding_secs"] = None
    with pytest.raises(TypeError, match="The value for 'event_video_capture_padding_secs' must be an integer."):
        EventConfigParser.parse_event_video_capture_padding_secs(config)

    config["event_video_capture_padding_secs"] = 12.5
    assert EventConfigParser.parse_event_video_capture_padding_secs(config) == 12.5

    config["event_video_capture_padding_secs"] = "12"
    assert EventConfigParser.parse_event_video_capture_padding_secs(config) == 12

    config["event_video_capture_padding_secs"] = 12
    assert EventConfigParser.parse_event_video_capture_padding_secs(config) == 12

    del config["event_video_capture_padding_secs"]
    assert EventConfigParser.parse_event_video_capture_padding_secs(config) == 10

def test_event_config_parsing_pause_alerting_on_event_secs():
    config = read_config('tests/events/sample_config.json')
    
    config["pause_alerting_on_event_secs"] = "a"
    with pytest.raises(ValueError, match="The value for 'pause_alerting_on_event_secs' must be an integer."):
        EventConfigParser.parse_pause_alerting_on_event_secs(config)

    config["pause_alerting_on_event_secs"] = None
    with pytest.raises(TypeError, match="The value for 'pause_alerting_on_event_secs' must be an integer."):
        EventConfigParser.parse_pause_alerting_on_event_secs(config)

    config["pause_alerting_on_event_secs"] = 12.5
    assert EventConfigParser.parse_pause_alerting_on_event_secs(config) == 12.5

    config["pause_alerting_on_event_secs"] = "12"
    assert EventConfigParser.parse_pause_alerting_on_event_secs(config) == 12

    config["pause_alerting_on_event_secs"] = 12
    assert EventConfigParser.parse_pause_alerting_on_event_secs(config) == 12

    del config["pause_alerting_on_event_secs"]
    assert EventConfigParser.parse_pause_alerting_on_event_secs(config) == 300

def test_event_config_parsing_detection_hz():
    config = read_config('tests/events/sample_config.json')
    
    config["detection_hz"] = "a"
    with pytest.raises(ValueError, match="The value for 'detection_hz' must be an integer."):
        EventConfigParser.parse_detection_hz(config)

    config["detection_hz"] = None
    with pytest.raises(TypeError, match="The value for 'detection_hz' must be an integer."):
        EventConfigParser.parse_detection_hz(config)

    config["detection_hz"] = 12.5
    assert EventConfigParser.parse_detection_hz(config) == 12

    config["detection_hz"] = "12"
    assert EventConfigParser.parse_detection_hz(config) == 12

    config["detection_hz"] = 12
    assert EventConfigParser.parse_detection_hz(config) == 12

    del config["detection_hz"]
    assert EventConfigParser.parse_detection_hz(config) == 10

def test_event_config_parsing_modes():
    logger = logging.getLogger(__name__)
    config = read_config('tests/events/sample_config.json')
    del config["video_capture_resource"]
    
    config["modes"] = 12
    with pytest.raises(TypeError, match="The value for 'modes' must be a list."):
        EventConfigParser.parse_modes(config)

    config["modes"] = None
    with pytest.raises(TypeError, match="The value for 'modes' must be a list."):
        EventConfigParser.parse_modes(config)

    config["modes"] = ["mode1", 12]
    with pytest.raises(TypeError, match="Each mode in 'modes' must be a string."):
        EventConfigParser.parse_modes(config)

    config["modes"] = ["mode1", "mode2"]
    assert EventConfigParser.parse_modes(config) == ["mode1", "mode2"]

    del config["modes"]
    assert EventConfigParser.parse_modes(config) == [MODE_INACTIVE]

def test_event_config_parsing_rule_logic_type():
    logger = logging.getLogger(__name__)
    config = read_config('tests/events/sample_config.json')
    del config["video_capture_resource"]
    
    config["rule_logic_type"] = 12
    with pytest.raises(TypeError, match="The value for 'rule_logic_type' must be a string."):
        EventConfigParser.parse_rule_logic_type(config)

    config["rule_logic_type"] = None
    with pytest.raises(TypeError, match="The value for 'rule_logic_type' must be a string."):
        EventConfigParser.parse_rule_logic_type(config)

    config["rule_logic_type"] = "bob"
    with pytest.raises(ValueError, match="Invalid value for 'rule_logic_type': bob"):
        EventConfigParser.parse_rule_logic_type(config)

    del config["rule_logic_type"]
    assert EventConfigParser.parse_rule_logic_type(config) == RuleLogicType.AND

def test_event_config_parsing_rules():
    logger = logging.getLogger(__name__)
    config = read_config('tests/events/sample_config.json')
    original_rules = config["rules"]

    config["rules"] = 12
    with pytest.raises(TypeError, match="The value for 'rules' must be a list."):
        EventConfigParser.parse_rules(logger, config, {})

    config["rules"] = None
    with pytest.raises(TypeError, match="The value for 'rules' must be a list."):
        EventConfigParser.parse_rules(logger, config, {})

    config["rules"] = [{"type": "time", "start_hour": 1, "end_hour": 2}]
    rules = EventConfigParser.parse_rules(logger, config, {})
    assert rules is not None
    assert len(rules) == 1
    assert isinstance(rules[0], RuleTime)

    del config["rules"]
    with pytest.raises(KeyError, match="The key 'rules' is missing from the event configuration."):
        EventConfigParser.parse_rules(logger, config, {})

    config["rules"] = ["bob"]
    with pytest.raises(TypeError, match="Each rule in 'rules' must be a dictionary."):
        EventConfigParser.parse_rules(logger, config, {})

    config["rules"] = [{}]
    with pytest.raises(KeyError, match="The key 'type' is missing from the rule configuration."):
        EventConfigParser.parse_rules(logger, config, {})

    config["rules"] = [{"type": "bob", "start_hour": 1, "end_hour": 2}]
    with pytest.raises(ValueError, match="Invalid rule type: bob"):
        EventConfigParser.parse_rules(logger, config, {})

def test_event_config_parse_notifications():
    logger = logging.getLogger(__name__)
    config = read_config('tests/events/sample_config.json')

    config["notifications"] = 12
    with pytest.raises(TypeError, match="The value for 'notifications' must be a list."):
        EventConfigParser.parse_notifiers(logger, config, {})

    config["notifications"] = None
    with pytest.raises(TypeError, match="The value for 'notifications' must be a list."):
        EventConfigParser.parse_notifiers(logger, config, {})

    config["notifications"] = [{"type": "sms", "to": "212-555-1212", "preset": "test"}]
    dependencies:Mapping[str, Resource] = {
        "sms_module": mock_resource("sms", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.generic),
    }
    notifiers = EventConfigParser.parse_notifiers(logger, config, dependencies)
    assert notifiers is not None
    assert len(notifiers) == 1
    assert isinstance(notifiers[0], SmsNotifier)

    del config["notifications"]
    with pytest.raises(KeyError, match="The key 'notifications' is missing from the event configuration."):
        EventConfigParser.parse_notifiers(logger, config, {})

    config["notifications"] = ["bob"]
    with pytest.raises(TypeError, match="Each notification in 'notifications' must be a dictionary."):
        EventConfigParser.parse_notifiers(logger, config, {})
    
    config["notifications"] = [{}]
    with pytest.raises(KeyError, match="The key 'type' is missing from the notification configuration."):
        EventConfigParser.parse_notifiers(logger, config, {})

def test_event_config_parsing_actions():
    logger = logging.getLogger(__name__)
    config = read_config('tests/events/sample_config.json')

    config["actions"] = 12
    with pytest.raises(TypeError, match="The value for 'actions' must be a list."):
        EventConfigParser.parse_actions(logger, config, {})

    config["actions"] = None
    with pytest.raises(TypeError, match="The value for 'actions' must be a list."):
        EventConfigParser.parse_actions(logger, config, {})

    config["actions"] = [{"type": "action", "resource": "kasa_plug_1", "method": "do_command", "payload": "test"}]
    dependencies:Mapping[str, Resource] = {
        "kasa_plug_1": mock_resource("kasa_plug_1", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic),
    }
    actions = EventConfigParser.parse_actions(logger, config, dependencies)
    assert actions is not None
    assert len(actions) == 1
    assert isinstance(actions[0], Action)
    assert actions[0].resource.resource == dependencies["kasa_plug_1"].resource

    config["actions"] = ["bob"]
    with pytest.raises(TypeError, match="Each action in 'actions' must be a dictionary."):
        EventConfigParser.parse_actions(logger, config, {})

def test_event_config_parsing_trigger_sequence_count():
    logger = logging.getLogger(__name__)
    config = read_config('tests/events/sample_config.json')

    config["trigger_sequence_count"] = 12
    assert EventConfigParser.parse_trigger_sequence_count(config) == 12

    config["trigger_sequence_count"] = "12"
    assert EventConfigParser.parse_trigger_sequence_count(config) == 12

    config["trigger_sequence_count"] = 12.5 
    assert EventConfigParser.parse_trigger_sequence_count(config) == 12

    config["trigger_sequence_count"] = None
    with pytest.raises(TypeError, match="The value for 'trigger_sequence_count' must be an integer."):
        EventConfigParser.parse_trigger_sequence_count(config)

    del config["trigger_sequence_count"]
    assert EventConfigParser.parse_trigger_sequence_count(config) == 1

def test_event_config_parsing_invalid_resource():
    logger = logging.getLogger(__name__)
    config = read_config('tests/events/sample_config.json')
    resources:Mapping[str, Resource] = {
        "kasa_plug_1": mock_resource("kasa_plug_1", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic),
        "kasa_plug_2": mock_resource("kasa_plug_2", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic),
        "cam1": mock_resource("cam1", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.camera),
        "vcam1": mock_resource("vcam1", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.camera),
        "tracker1": mock_resource("tracker1", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.vision),
        "person_detector": mock_resource("person_detector", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.vision),
        "stuff_sensor": mock_resource("stuff_sensor", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.sensor),
        "sms_module": mock_resource("sms", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.generic),
        "email_module": mock_resource("email", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.generic),
        "video_capture": mock_resource("video_capture", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic)
    }
    config["video_capture_resource"] = "non_existent_resource"
    with pytest.raises(ValueError):
        Event(logger, config, resources)

def test_event_flip_action_status():
    logger = logging.getLogger(__name__)
    config = read_config('tests/events/sample_config.json')
    resources:Mapping[str, Resource] = {
        "kasa_plug_1": mock_resource("kasa_plug_1", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic),
        "kasa_plug_2": mock_resource("kasa_plug_2", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic),
        "cam1": mock_resource("cam1", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.camera),
        "vcam1": mock_resource("vcam1", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.camera),
        "tracker1": mock_resource("tracker1", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.vision),
        "person_detector": mock_resource("person_detector", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.vision),
        "stuff_sensor": mock_resource("stuff_sensor", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.sensor),
        "sms_module": mock_resource("sms", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.generic),
        "email_module": mock_resource("email", resource_type=ResourceType.service, resource_sub_type=ResourceSubType.generic),
        "video_capture": mock_resource("video_capture", resource_type=ResourceType.component, resource_sub_type=ResourceSubType.generic)
    }
    event = Event(logger, config, resources)
    assert event is not None
    assert isinstance(event, Event)
    assert event.actions is not None
    assert len(event.actions) == 3
    assert event.actions[0].taken == False
    assert event.actions[1].taken == False
    assert event.actions[2].taken == False
    event.flip_action_status(True)
    assert event.actions[0].taken == True
    assert event.actions[1].taken == True
    assert event.actions[2].taken == True
