from typing import Mapping, cast
from unittest.mock import AsyncMock, MagicMock
from PIL import Image

import re

import pytest
from src.common import Resource, ResourceSubType, ResourceType
from viam.utils import ValueTypes
from viam.services.vision import Vision, CaptureAllResult, Detection, Classification
from viam.media.video import ViamImage, CameraMimeType
from viam.media.utils.pil import pil_to_viam_image

from src.rules import RuleDetector, RuleClassifier, RuleTracker, RuleCall, RuleTime, Operator
from logging import getLogger

from tests.helpers import mock_resource

def test_rule_detector_parse_config():
    logger = getLogger(__name__)
    config:Mapping[str, ValueTypes] = {}
    resources:Mapping[str, Resource] = {}

    with pytest.raises(KeyError, match="The key 'camera' is missing from the rule configuration."):
        RuleDetector(logger, config, resources)

    config["camera"] = 12
    with pytest.raises(TypeError, match="The value for 'camera' must be a string."):
        RuleDetector(logger, config, resources)

    config["camera"] = "camera1"
    with pytest.raises(ValueError, match="Camera 'camera1' not found in dependencies."):
        RuleDetector(logger, config, resources)

    config["camera"] = "camera1"
    resources = {"camera1": mock_resource("camera1", ResourceType.component, ResourceSubType.generic)}
    with pytest.raises(TypeError, match="The camera resource must be of type Camera."):
        RuleDetector(logger, config, resources)

    resources = {"camera1": mock_resource("camera1", ResourceType.component, ResourceSubType.camera)}
    with pytest.raises(KeyError, match="The key 'detector' is missing from the rule configuration."):
        RuleDetector(logger, config, resources)

    config["detector"] = 12
    with pytest.raises(TypeError, match="The value for 'detector' must be a string."):
        RuleDetector(logger, config, resources)
    config["detector"] = "detector1"
    with pytest.raises(ValueError, match="Detector 'detector1' not found in dependencies."):
        RuleDetector(logger, config, resources)
    
    resources["detector1"] = mock_resource("detector1", ResourceType.component, ResourceSubType.generic)
    with pytest.raises(TypeError, match="The detector resource must be of type Vision."):
        RuleDetector(logger, config, resources)
    
    resources["detector1"] = mock_resource("detector1", ResourceType.service, ResourceSubType.vision)
    with pytest.raises(KeyError, match="The key 'class_regex' is missing from the rule configuration."):
        RuleDetector(logger, config, resources)

    config["class_regex"] = 12
    with pytest.raises(TypeError, match="The value for 'class_regex' must be a string."):
        RuleDetector(logger, config, resources)
    
    config["class_regex"] = ".*"
    with pytest.raises(KeyError, match="The key 'confidence_pct' is missing from the rule configuration."):
        RuleDetector(logger, config, resources)

    config["confidence_pct"] = ""
    with pytest.raises(TypeError, match="The value for 'confidence_pct' must be a number."):
        RuleDetector(logger, config, resources)
    
    config["confidence_pct"] = 1.2
    with pytest.raises(ValueError, match="The value for 'confidence_pct' must be between 0 and 1."):
        RuleDetector(logger, config, resources)
    
    config["confidence_pct"] = -1
    with pytest.raises(ValueError, match="The value for 'confidence_pct' must be between 0 and 1."):
        RuleDetector(logger, config, resources)
    
    config["confidence_pct"] = 0.5
    assert RuleDetector(logger, config, resources).inverse_pause_secs == 0

    config["inverse_pause_secs"] = ""
    with pytest.raises(TypeError, match="The value for 'inverse_pause_secs' must be a number."):
        RuleDetector(logger, config, resources)
    
    config["inverse_pause_secs"] = -1
    with pytest.raises(ValueError, match="The value for 'inverse_pause_secs' must be a positive number."):
        RuleDetector(logger, config, resources)
    
    config["inverse_pause_secs"] = 1
    assert RuleDetector(logger, config, resources).inverse_pause_secs == 1

@pytest.mark.asyncio
async def test_rule_detector_eval():
    logger = getLogger(__name__)
    config:Mapping[str, ValueTypes] = {}
    resources:Mapping[str, Resource] = {
        "camera1": mock_resource("camera1", ResourceType.component, ResourceSubType.camera),
        "detector1": mock_resource("detector1", ResourceType.service, ResourceSubType.vision)
    }

    config["camera"] = "camera1"
    config["detector"] = "detector1"
    config["class_regex"] = "bob"
    config["confidence_pct"] = 0.5
    config["inverse_pause_secs"] = 1

    rule_detector = RuleDetector(logger, config, resources)
    
    detector = cast(Vision, resources["detector1"].resource)
    
    detector.capture_all_from_camera = AsyncMock(return_value=None)
    res = await rule_detector.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "capture_all_from_camera returned None from detector 'detector1'"
    
    capture_all_result = CaptureAllResult()
    capture_all_result.image = None
    detector.capture_all_from_camera = AsyncMock(return_value=capture_all_result)
    res = await rule_detector.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "no detections returned from detector 'detector1'"

    capture_all_result.detections = []
    res = await rule_detector.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "no image returned with detections from detector 'detector1'"

    image = Image.new("RGB", (100, 100), color=(0,0,0))
    capture_all_result.image = pil_to_viam_image(image, CameraMimeType.JPEG)
    res = await rule_detector.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False

    capture_all_result.detections = [
        Detection(confidence=0.4, class_name="bob")
    ]
    res = await rule_detector.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False

    capture_all_result.detections = [
        Detection(confidence=0.5, class_name="alice")
    ]
    res = await rule_detector.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False

    capture_all_result.detections = [
        Detection(confidence=0.5, class_name="bob")
    ]
    res = await rule_detector.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is True
    assert "image" in res
    assert "resource" in res
    assert res["resource"] == "camera1"

def test_rule_classifier_parse_config():
    logger = getLogger(__name__)
    config:Mapping[str, ValueTypes] = {}
    resources:Mapping[str, Resource] = {}

    with pytest.raises(KeyError, match="The key 'camera' is missing from the rule configuration."):
        RuleClassifier(logger, config, resources)

    config["camera"] = 12
    with pytest.raises(TypeError, match="The value for 'camera' must be a string."):
        RuleClassifier(logger, config, resources)

    config["camera"] = "camera1"
    with pytest.raises(ValueError, match="Camera 'camera1' not found in dependencies."):
        RuleClassifier(logger, config, resources)

    config["camera"] = "camera1"
    resources = {"camera1": mock_resource("camera1", ResourceType.component, ResourceSubType.generic)}
    with pytest.raises(TypeError, match="The camera resource must be of type Camera."):
        RuleClassifier(logger, config, resources)

    resources = {"camera1": mock_resource("camera1", ResourceType.component, ResourceSubType.camera)}
    with pytest.raises(KeyError, match="The key 'classifier' is missing from the rule configuration."):
        RuleClassifier(logger, config, resources)

    config["classifier"] = 12
    with pytest.raises(TypeError, match="The value for 'classifier' must be a string."):
        RuleClassifier(logger, config, resources)
    config["classifier"] = "classifier1"
    with pytest.raises(ValueError, match="Classifier 'classifier1' not found in dependencies."):
        RuleClassifier(logger, config, resources)
    
    resources["classifier1"] = mock_resource("classifier1", ResourceType.component, ResourceSubType.generic)
    with pytest.raises(TypeError, match="The classifier resource must be of type Vision."):
        RuleClassifier(logger, config, resources)
    
    resources["classifier1"] = mock_resource("classifier1", ResourceType.service, ResourceSubType.vision)
    with pytest.raises(KeyError, match="The key 'class_regex' is missing from the rule configuration."):
        RuleClassifier(logger, config, resources)

    config["class_regex"] = 12
    with pytest.raises(TypeError, match="The value for 'class_regex' must be a string."):
        RuleClassifier(logger, config, resources)
    
    config["class_regex"] = ".*"
    with pytest.raises(KeyError, match="The key 'confidence_pct' is missing from the rule configuration."):
        RuleClassifier(logger, config, resources)

    config["confidence_pct"] = ""
    with pytest.raises(TypeError, match="The value for 'confidence_pct' must be a number."):
        RuleClassifier(logger, config, resources)
    
    config["confidence_pct"] = 1.2
    with pytest.raises(ValueError, match="The value for 'confidence_pct' must be between 0 and 1."):
        RuleClassifier(logger, config, resources)
    
    config["confidence_pct"] = -1
    with pytest.raises(ValueError, match="The value for 'confidence_pct' must be between 0 and 1."):
        RuleClassifier(logger, config, resources)
    
    config["confidence_pct"] = 0.5
    assert RuleClassifier(logger, config, resources).inverse_pause_secs == 0

    config["inverse_pause_secs"] = ""
    with pytest.raises(TypeError, match="The value for 'inverse_pause_secs' must be a number."):
        RuleClassifier(logger, config, resources)
    
    config["inverse_pause_secs"] = -1
    with pytest.raises(ValueError, match="The value for 'inverse_pause_secs' must be a positive number."):
        RuleClassifier(logger, config, resources)
    
    config["inverse_pause_secs"] = 1
    assert RuleClassifier(logger, config, resources).inverse_pause_secs == 1

@pytest.mark.asyncio
async def test_rule_classifier_eval():
    logger = getLogger(__name__)
    config:Mapping[str, ValueTypes] = {}
    resources:Mapping[str, Resource] = {
        "camera1": mock_resource("camera1", ResourceType.component, ResourceSubType.camera),
        "classifier1": mock_resource("classifier1", ResourceType.service, ResourceSubType.vision)
    }

    config["camera"] = "camera1"
    config["classifier"] = "classifier1"
    config["class_regex"] = "bob"
    config["confidence_pct"] = 0.5
    config["inverse_pause_secs"] = 1

    rule_classifier = RuleClassifier(logger, config, resources)
    
    classifier = cast(Vision, resources["classifier1"].resource)
    
    classifier.capture_all_from_camera = AsyncMock(return_value=None)
    res = await rule_classifier.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "capture_all_from_camera returned None from classifier 'classifier1'"
    
    capture_all_result = CaptureAllResult()
    capture_all_result.image = None
    classifier.capture_all_from_camera = AsyncMock(return_value=capture_all_result)
    res = await rule_classifier.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "no classifications returned from classifier 'classifier1'"

    capture_all_result.classifications = []
    res = await rule_classifier.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "no image returned with classifications from classifier 'classifier1'"

    image = Image.new("RGB", (100, 100), color=(0,0,0))
    capture_all_result.image = pil_to_viam_image(image, CameraMimeType.JPEG)
    res = await rule_classifier.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False

    capture_all_result.classifications = [
        Classification(confidence=0.4, class_name="bob")
    ]
    res = await rule_classifier.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False

    capture_all_result.classifications = [
        Classification(confidence=0.5, class_name="alice")
    ]
    res = await rule_classifier.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False

    capture_all_result.classifications = [
        Classification(confidence=0.5, class_name="bob")
    ]
    res = await rule_classifier.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is True
    assert "image" in res
    assert "resource" in res
    assert res["resource"] == "camera1"

def test_rule_tracker_parse_config():
    logger = getLogger(__name__)
    config:Mapping[str, ValueTypes] = {}
    resources:Mapping[str, Resource] = {}

    with pytest.raises(KeyError, match="The key 'camera' is missing from the rule configuration."):
        RuleTracker(logger, config, resources)

    config["camera"] = 12
    with pytest.raises(TypeError, match="The value for 'camera' must be a string."):
        RuleTracker(logger, config, resources)

    config["camera"] = "camera1"
    with pytest.raises(ValueError, match="Camera 'camera1' not found in dependencies."):
        RuleTracker(logger, config, resources)

    config["camera"] = "camera1"
    resources = {"camera1": mock_resource("camera1", ResourceType.component, ResourceSubType.generic)}
    with pytest.raises(TypeError, match="The camera resource must be of type Camera."):
        RuleTracker(logger, config, resources)

    resources = {"camera1": mock_resource("camera1", ResourceType.component, ResourceSubType.camera)}
    with pytest.raises(KeyError, match="The key 'tracker' is missing from the rule configuration."):
        RuleTracker(logger, config, resources)

    config["tracker"] = 12
    with pytest.raises(TypeError, match="The value for 'tracker' must be a string."):
        RuleTracker(logger, config, resources)
    config["tracker"] = "tracker1"
    with pytest.raises(ValueError, match="Tracker 'tracker1' not found in dependencies."):
        RuleTracker(logger, config, resources)
    
    resources["tracker1"] = mock_resource("tracker1", ResourceType.component, ResourceSubType.generic)
    with pytest.raises(TypeError, match="The tracker resource must be of type Vision."):
        RuleTracker(logger, config, resources)
    
    resources["tracker1"] = mock_resource("tracker1", ResourceType.service, ResourceSubType.vision)
    with pytest.raises(KeyError, match="The key 'confidence_pct' is missing from the rule configuration."):
        RuleTracker(logger, config, resources)

    config["confidence_pct"] = ""
    with pytest.raises(TypeError, match="The value for 'confidence_pct' must be a number."):
        RuleTracker(logger, config, resources)
    
    config["confidence_pct"] = 1.2
    with pytest.raises(ValueError, match="The value for 'confidence_pct' must be between 0 and 1."):
        RuleTracker(logger, config, resources)
    
    config["confidence_pct"] = -1
    with pytest.raises(ValueError, match="The value for 'confidence_pct' must be between 0 and 1."):
        RuleTracker(logger, config, resources)
    
    config["confidence_pct"] = 0.5
    assert RuleTracker(logger, config, resources).inverse_pause_secs == 0

    config["inverse_pause_secs"] = ""
    with pytest.raises(TypeError, match="The value for 'inverse_pause_secs' must be a number."):
        RuleTracker(logger, config, resources)
    
    config["inverse_pause_secs"] = -1
    with pytest.raises(ValueError, match="The value for 'inverse_pause_secs' must be a positive number."):
        RuleTracker(logger, config, resources)
    
    config["inverse_pause_secs"] = 1
    assert RuleTracker(logger, config, resources).inverse_pause_secs == 1

@pytest.mark.asyncio
async def test_rule_tracker_eval():
    logger = getLogger(__name__)
    config:Mapping[str, ValueTypes] = {}
    resources:Mapping[str, Resource] = {
        "camera1": mock_resource("camera1", ResourceType.component, ResourceSubType.camera),
        "tracker1": mock_resource("tracker1", ResourceType.service, ResourceSubType.vision)
    }

    config["camera"] = "camera1"
    config["tracker"] = "tracker1"
    config["class_regex"] = "bob"
    config["confidence_pct"] = 0.5
    config["inverse_pause_secs"] = 1

    rule_tracker = RuleTracker(logger, config, resources)
    
    tracker = cast(Vision, resources["tracker1"].resource)
    
    tracker.capture_all_from_camera = AsyncMock(return_value=None)
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "capture_all_from_camera returned None from tracker 'tracker1'"
    
    capture_all_result = CaptureAllResult()
    capture_all_result.image = None
    tracker.capture_all_from_camera = AsyncMock(return_value=capture_all_result)
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "no detections returned from tracker 'tracker1'"

    capture_all_result.detections = []
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "no image returned with detections from tracker 'tracker1'"

    image = Image.new("RGB", (100, 100), color=(0,0,0))
    capture_all_result.image = pil_to_viam_image(image, CameraMimeType.JPEG)
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False

    capture_all_result.detections = [
        Detection(confidence=0.4, class_name="bob")
    ]
    tracker.do_command = AsyncMock(return_value={})
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "no list_current returned from tracker 'tracker1'"

    tracker.do_command = AsyncMock(return_value={"list_current": []})
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "error" in res
    assert res["error"] == "list_current is unexpected type: '<class 'list'>' from tracker 'tracker1'"

    tracker.do_command = AsyncMock(return_value={"list_current": {}})
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert res["error"] == "list_current is empty from tracker 'tracker1'"

    tracker.do_command = AsyncMock(return_value={"list_current": {}})
    capture_all_result.detections = [
        Detection(confidence=0.5, class_name="alice")
    ]
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    # I think this is wrong, i think if the tracker finds somebody and 
    # they're not in `list_current` it should trigger
    assert res["triggered"] is False

    tracker.do_command = AsyncMock(return_value={"list_current": {
        "alice":{}
    }})
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is True
    assert "image" in res
    assert res["resource"] == "camera1"
    assert res["value"] == "alice"

    tracker.do_command = AsyncMock(return_value={"list_current": {
        "alice":{"face_id_label": "alice"}
    }})
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "image" not in res

    tracker.do_command = AsyncMock(return_value={"list_current": {
        "alice":{"manual_label": "alice"}
    }})
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "image" not in res

    tracker.do_command = AsyncMock(return_value={"list_current": {
        "alice":{"re_id_label": "alice"}
    }})
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "image" not in res

    capture_all_result.detections = [
        Detection(confidence=0.5, class_name="person123 (label: alice)")
    ]
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    # I think this is wrong, i think if the tracker finds somebody and 
    # they're not in `list_current` it should trigger
    assert res["triggered"] is False

    capture_all_result.detections = [
        Detection(confidence=0.5, class_name="bob")
    ]
    res = await rule_tracker.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "image" not in res

def test_rule_call_parse_config():
    logger = getLogger(__name__)
    config:Mapping[str, ValueTypes] = {}
    resources:Mapping[str, Resource] = {}

    with pytest.raises(KeyError, match="The key 'resource' is missing from the rule configuration."):
        RuleCall(logger, config, resources)

    config["resource"] = 12
    with pytest.raises(TypeError, match="The value for 'resource' must be a string."):
        RuleCall(logger, config, resources)

    config["resource"] = "sensor1"
    with pytest.raises(ValueError, match="Resource 'sensor1' not found in dependencies."):
        RuleCall(logger, config, resources)

    config["resource"] = "sensor1"
    resources = {"sensor1": "any"} # type: ignore
    with pytest.raises(TypeError, match="The resource must be a Viam resource."):
        RuleCall(logger, config, resources)

    config["resource"] = "sensor1"
    resource = mock_resource("sensor1", ResourceType.component, ResourceSubType.sensor)
    resource.resource = "a"# type: ignore
    resources = {"sensor1": resource} 
    with pytest.raises(TypeError, match="The resource must be a Viam resource."):
        RuleCall(logger, config, resources)

    resources = {"sensor1": mock_resource("sensor1", ResourceType.component, ResourceSubType.sensor)}
    with pytest.raises(KeyError, match="The key 'method' is missing from the rule configuration."):
        RuleCall(logger, config, resources)

    config["method"] = 12
    with pytest.raises(TypeError, match="The value for 'method' must be a string."):
        RuleCall(logger, config, resources)
    
    config["method"] = "foo"
    with pytest.raises(ValueError, match="Method 'foo' not found on resource 'sensor1'."):
        RuleCall(logger, config, resources)

    config["method"] = "do_command"
    config["payload"] = 12
    with pytest.raises(TypeError, match="The value for 'payload' must be a string."):
        RuleCall(logger, config, resources)

    config["payload"] = "foo"
    with pytest.raises(KeyError, match="The key 'result_path' is missing from the rule configuration."):
        RuleCall(logger, config, resources)

    config["result_path"] = 12
    with pytest.raises(TypeError, match="The value for 'result_path' must be a string."):
        RuleCall(logger, config, resources)

    config["result_path"] = "alice.bob"
    with pytest.raises(KeyError, match="The key 'result_function' is missing from the rule configuration."):
        RuleCall(logger, config, resources)

    config["result_function"] = 12
    with pytest.raises(TypeError, match="The value for 'result_function' must be a string."):
        RuleCall(logger, config, resources)
    
    config["result_function"] = "bob"
    with pytest.raises(ValueError, match="The value for 'result_function' must be either 'len' or 'any'."):
        RuleCall(logger, config, resources)

    config["result_function"] = "len"
    with pytest.raises(KeyError, match="The key 'result_operator' is missing from the rule configuration."):
        RuleCall(logger, config, resources)

    config["result_operator"] = 12
    with pytest.raises(TypeError, match="The value for 'result_operator' must be a string."):
        RuleCall(logger, config, resources)

    config["result_operator"] = "bob"
    with pytest.raises(ValueError, match="Invalid operator: 'bob'."):
        RuleCall(logger, config, resources)

    config["result_operator"] = "lt"
    with pytest.raises(KeyError, match="The key 'result_value' is missing from the rule configuration."):
        RuleCall(logger, config, resources)

    config["result_value"] = "abc" # This feels too unbounded
    with pytest.raises(KeyError, match="The key 'inverse_pause_secs' is missing from the rule configuration."):
        RuleCall(logger, config, resources)

    config["inverse_pause_secs"] = "12"
    with pytest.raises(TypeError, match="The value for 'inverse_pause_secs' must be a number."):
        RuleCall(logger, config, resources)
    
    config["inverse_pause_secs"] = -1
    with pytest.raises(ValueError, match="The value for 'inverse_pause_secs' must be a positive number."):
        RuleCall(logger, config, resources)
    
    config["inverse_pause_secs"] = 1
    rule_call = RuleCall(logger, config, resources)
    assert rule_call.resource == resources["sensor1"]
    assert rule_call.method == resources["sensor1"].resource.do_command
    assert rule_call.payload == "foo"
    assert rule_call.result_path == "alice.bob"
    assert rule_call.result_function == "len"
    assert rule_call.result_operator == Operator.from_string("lt")
    assert rule_call.result_value == "abc"
    assert rule_call.inverse_pause_secs == 1
    
@pytest.mark.asyncio
async def test_rule_call_eval():
    logger = getLogger(__name__)
    config:Mapping[str, ValueTypes] = {}
    resources:Mapping[str, Resource] = {
        "sensor1": mock_resource("sensor1", ResourceType.component, ResourceSubType.sensor)
    }

    config["resource"] = "sensor1"
    config["method"] = "do_command"
    config["payload"] = '{"foo":1}'
    config["result_path"] = "alice.bob"
    config["result_function"] = "len"
    config["result_operator"] = "lt"
    config["result_value"] = 5
    config["inverse_pause_secs"] = 1

    mock_do_command = AsyncMock(return_value={"alice": {"bob": [1, 2, 3]}})
    logger.info("mock_do_command: %s", mock_do_command)
    resources["sensor1"].resource.do_command = mock_do_command

    rule_call = RuleCall(logger, config, resources)
    res = await rule_call.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is True
    assert "value" in res
    assert res["value"] == 3
    assert "resource" in res
    assert res["resource"] == "sensor1"
    assert mock_do_command.called is True
    assert mock_do_command.call_count == 1
    assert mock_do_command.call_args[0][0] == {"foo": 1}

    del config["payload"]

    mock_do_command = AsyncMock(return_value={"alice": {"bob": [1, 2, 3]}})
    logger.info("mock_do_command: %s", mock_do_command)
    resources["sensor1"].resource.do_command = mock_do_command

    rule_call = RuleCall(logger, config, resources)
    res = await rule_call.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is True
    assert "value" in res
    assert res["value"] == 3
    assert "resource" in res
    assert res["resource"] == "sensor1"
    assert mock_do_command.called is True
    assert mock_do_command.call_count == 1
    assert mock_do_command.call_args == []

    mock_do_command = AsyncMock(return_value=None)
    logger.info("mock_do_command: %s", mock_do_command)
    resources["sensor1"].resource.do_command = mock_do_command

    rule_call = RuleCall(logger, config, resources)
    res = await rule_call.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is False
    assert "value" not in res
    assert "resource" not in res
    assert mock_do_command.called is True
    assert mock_do_command.call_count == 1
    assert mock_do_command.call_args == []

    mock_do_command = AsyncMock(return_value={"alice": {"bob": [1, 2, 3]}})
    logger.info("mock_do_command: %s", mock_do_command)
    resources["sensor1"].resource.do_command = mock_do_command
    config["result_function"] = "any"

    rule_call = RuleCall(logger, config, resources)
    res = await rule_call.eval()
    assert res is not None
    assert isinstance(res, Mapping)
    assert "triggered" in res
    assert res["triggered"] is True
    assert "value" in res
    assert res["value"] == True
    assert "resource" in res
    assert res["resource"] == "sensor1"
    assert mock_do_command.called is True
    assert mock_do_command.call_count == 1
    assert mock_do_command.call_args == []

def test_rule_time_parse_config():
    