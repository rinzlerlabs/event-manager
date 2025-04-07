import logging
from unittest.mock import MagicMock, AsyncMock
import pytest
from helpers import mock_resource, read_config
from typing import Callable
from src.actions import Action
import time


def test_action_config_parsing():
    logger = logging.getLogger(__name__)
    config = read_config('tests/actions/sample_config.json')
    resources = {str(config["resource"]):mock_resource(str(config["resource"]))}
    action = Action(logger, config, resources)
    assert action is not None
    assert isinstance(action, Action)
    assert action.resource == resources[str(config["resource"])]
    assert isinstance(action.method, Callable)
    assert action.payload == config["payload"]
    assert action.when_secs == config["when_secs"]
    assert action.response_match == config["response_match"]
    assert action.taken == False
    assert action.last_taken == 0.0

def test_action_config_parsing_missing_resource():
    logger = logging.getLogger(__name__)
    config = read_config('tests/actions/sample_config.json')

    resources = mock_resource("test")
    resources = {"test":mock_resource("test")}
    with pytest.raises(ValueError, match=f'Dependency with name {config["resource"]} not found in dependencies.'):
        Action(logger, config, resources)

    config["resource"] = 12
    with pytest.raises(TypeError, match="The value for 'resource' must be a string."):
        Action(logger, config, resources)

    config["resource"] = None
    with pytest.raises(TypeError, match="The value for 'resource' must be a string."):
        Action(logger, config, resources)

    del config["resource"]
    with pytest.raises(KeyError, match="The key 'resource' is missing from the action configuration."):
        Action(logger, config, resources)

def test_action_config_parsing_missing_method():
    logger = logging.getLogger(__name__)
    config = read_config('tests/actions/sample_config.json')
    resources = {str(config["resource"]):mock_resource(str(config["resource"]))}
    del config["method"]
    with pytest.raises(KeyError, match="The key 'method' is missing from the action configuration."):
        Action(logger, config, resources)

    config["method"] = 12
    with pytest.raises(TypeError, match="The value for 'method' must be a string."):
        Action(logger, config, resources)

    config["method"] = None
    with pytest.raises(TypeError, match="The value for 'method' must be a string."):
        Action(logger, config, resources)

    config["method"] = "non_existent_method"
    with pytest.raises(AttributeError, match="The method 'non_existent_method' does not exist on the resource"):
        Action(logger, config, resources)

def test_action_config_parsing_missing_payload():
    logger = logging.getLogger(__name__)
    config = read_config('tests/actions/sample_config.json')
    resources = {str(config["resource"]):mock_resource(str(config["resource"]))}
    config["payload"] = 12
    with pytest.raises(TypeError, match="The value for 'payload' must be a string."):
        Action(logger, config, resources)

    config["payload"] = None
    with pytest.raises(TypeError, match="The value for 'payload' must be a string."):
        Action(logger, config, resources)

    del config["payload"]
    with pytest.raises(KeyError, match="The key 'payload' is missing from the action configuration."):
        Action(logger, config, resources)

def test_action_config_parsing_missing_when_secs():
    logger = logging.getLogger(__name__)
    config = read_config('tests/actions/sample_config.json')
    resources = {str(config["resource"]):mock_resource(str(config["resource"]))}
    config["when_secs"] = 12
    action = Action(logger, config, resources)
    assert action.when_secs == 12

    config["when_secs"] = -1
    action = Action(logger, config, resources)
    assert action.when_secs == -1

    config["when_secs"] = -2
    with pytest.raises(ValueError, match="The value for 'when_secs' cannot be negative."):
        Action(logger, config, resources)

    config["when_secs"] = "12"
    action = Action(logger, config, resources)
    assert action.when_secs == 12

    config["when_secs"] = None
    with pytest.raises(TypeError, match="The value for 'when_secs' must be an integer."):
        Action(logger, config, resources)

    del config["when_secs"]
    action = Action(logger, config, resources)
    assert action.when_secs == 0

def test_action_config_parsing_missing_response_match():
    logger = logging.getLogger(__name__)
    config = read_config('tests/actions/sample_config.json')
    resources = {str(config["resource"]):mock_resource(str(config["resource"]))}
    config["response_match"] = 12
    with pytest.raises(TypeError, match="The value for 'response_match' must be a string."):
        Action(logger, config, resources)

    config["response_match"] = None
    with pytest.raises(TypeError, match="The value for 'response_match' must be a string."):
        Action(logger, config, resources)

    del config["response_match"]
    action = Action(logger, config, resources)
    assert action.response_match == ""

def test_action_should_action():
    logger = logging.getLogger(__name__)
    config = read_config('tests/actions/sample_config.json')
    resources = {str(config["resource"]):mock_resource(str(config["resource"]))}
    action = Action(logger, config, resources)

    # test when action has already been taken
    action.taken = True
    assert action.should_action(0) == False
    action.taken = False

    action.response_match = "test"
    assert action.should_action(0, "hello, this is a test") == True

    action.when_secs = 0
    action.taken = False
    assert action.should_action(0) == True

    last_triggered = time.time()
    action.last_taken = time.time() - 9
    action.when_secs = 10
    assert action.should_action(last_triggered) == False

    action.last_taken = time.time() - 11
    action.when_secs = 10
    assert action.should_action(last_triggered) == True

    action.when_secs = -1
    assert action.should_action(0) == False
    
@pytest.mark.asyncio
async def test_action_do_action():
    logger = logging.getLogger(__name__)
    config = read_config('tests/actions/sample_config.json')
    resource_name = str(config["resource"])
    resources = {resource_name:mock_resource(resource_name, exception=Exception("Test exception"))}
    action = Action(logger, config, resources)

    assert action.taken == False
    assert action.last_taken == 0.0
    with pytest.raises(Exception, match="Test exception"):
        await action.do_action("test", "person", "cam1")
    assert action.taken == True
    assert action.last_taken > 0
    assert action.last_taken <= time.time()

    resources = {resource_name:mock_resource(resource_name)}
    action = Action(logger, config, resources)
    
    assert action.taken == False
    assert action.last_taken == 0.0
    await action.do_action("test", "person", "cam1")
    assert action.taken == True
    assert action.last_taken > 0
    assert action.last_taken <= time.time()
