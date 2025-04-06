import operator
import re
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, cast

from viam.components.camera.client import Camera
from viam.media.utils.pil import viam_to_pil_image
from viam.resource.base import ResourceBase
from viam.services.vision import Classification, Detection, VisionClient
from viam.services.vision.client import VisionClient
from viam.utils import ValueTypes

from src.common import Resource

from . import logic
from .logger import LOGGER
from .resource_utils import call_method


class Operator(Enum):
    eq = ("eq", operator.eq)
    ne = ("ne", operator.ne)
    lt = ("lt", operator.lt)
    lte = ("lte", operator.le)
    gt = ("gt", operator.gt)
    gte = ("gte", operator.ge)
    regex = ("regex", lambda a,b: re.match(b,a))
    in_ = ("in", lambda a,b: a in b)
    has_attr = ("hasattr", hasattr)

    def invoke(self, a: Any, b: Any) -> bool:
        return self.value[1](a, b)

    @classmethod
    def from_string(cls, name: str):
        name = name.lower()
        for op in cls:
            if op.name == name:
                return op
        raise ValueError(f"Invalid operator: {name}")

class RuleLogicType(str, Enum):
    AND = "AND"
    OR = "OR"
    NOR = "NOR"
    NAND = "NAND"
    XOR = "XOR"
    NOT = "NOT"
    XNOR = "XNOR"

class RuleType(str, Enum):
    detection = "detection"
    classification = "classification"
    time = "time"
    tracker = "tracker"
    call = "call"

class Rule():
    type: RuleType

    def __init__(self, rule_type: RuleType):
        self.type = rule_type

class TimeRange():
    start_hour: int
    end_hour: int

    def __init__(self, start_hour: int, end_hour: int):
        if start_hour < 0 or start_hour > 23:
            raise ValueError("start_hour must be between 0 and 23")
        if end_hour < 0 or end_hour > 23:
            raise ValueError("end_hour must be between 0 and 23")
        if start_hour >= end_hour:
            raise ValueError("start_hour must be less than end_hour")
        self.start_hour = start_hour
        self.end_hour = end_hour

class RuleDetector(Rule):
    camera: Camera
    camera_name: str
    detector: VisionClient
    class_regex: str
    confidence_pct: float
    inverse_pause_secs: int

    def __init__(self, conf: Mapping[str, ValueTypes], resources: Mapping[str, Resource]):
        super().__init__(RuleType.detection)
        
        # Check if the camera is in the configuration and if it's a string
        if "camera" not in conf:
            raise KeyError("The key 'camera' is missing from the rule configuration.")
        if not isinstance(conf["camera"], str):
            raise TypeError("The value for 'camera' must be a string.")
        self.camera_name = conf["camera"]
        
        # Check if the camera is in the dependencies and make sure it's a Camera
        if conf["camera"] not in resources:
            raise ValueError(f"Camera {conf['camera']} not found in dependencies.")
        if not isinstance(resources[conf["camera"]].resource, Camera):
            raise TypeError("The camera resource must be of type Camera.")
        self.camera = cast(Camera, resources[conf["camera"]].resource)
        
        # Check if detector is in the configuration and if it's a string
        # Check if the detector is in the dependencies and make sure it's a VisionClient
        if "detector" not in conf:
            raise KeyError("The key 'detector' is missing from the rule configuration.")
        if not isinstance(conf["detector"], str):
            raise TypeError("The value for 'detector' must be a string.")
        if conf["detector"] not in resources:
            raise ValueError(f"Detector {conf['detector']} not found in dependencies.")
        if not isinstance(resources[conf["detector"]].resource, VisionClient):
            raise TypeError("The detector resource must be of type Vision.")
        self.detector = cast(VisionClient, resources[conf["detector"]].resource)
        
        # Check if class_regex is in the configuration and if it's a string
        if "class_regex" not in conf:
            raise KeyError("The key 'class_regex' is missing from the rule configuration.")
        if not isinstance(conf["class_regex"], str):
            raise TypeError("The value for 'class_regex' must be a string.")
        self.class_regex = str(conf["class_regex"])
        
        # Check if confidence_pct is in the configuration, if it's a number, and if it's between 0 and 1
        if "confidence_pct" not in conf:
            raise KeyError("The key 'confidence_pct' is missing from the rule configuration.")
        if not isinstance(conf["confidence_pct"], (int, float)):
            raise TypeError("The value for 'confidence_pct' must be a number.")
        if conf["confidence_pct"] < 0 or conf["confidence_pct"] > 1:
            raise ValueError("The value for 'confidence_pct' must be between 0 and 1.")
        self.confidence_pct = float(conf["confidence_pct"])
        
        # Check if inverse_pause_secs is in the configuration, if it's a number, and if it's positive, otherwise set to 0
        if "inverse_pause_secs" in conf:
            if not isinstance(conf["inverse_pause_secs"], (int, float)):
                raise TypeError("The value for 'inverse_pause_secs' must be a number.")
            if conf["inverse_pause_secs"] < 0:
                raise ValueError("The value for 'inverse_pause_secs' must be a positive number.")
            self.inverse_pause_secs = int(conf["inverse_pause_secs"])
        else:
            self.inverse_pause_secs = 0

class RuleClassifier(Rule):
    camera: Camera
    camera_name: str
    classifier: VisionClient
    class_regex: str
    confidence_pct: float
    inverse_pause_secs: int

    def __init__(self, conf: Mapping[str, ValueTypes], resources: Mapping[str, Resource]):
        super().__init__(RuleType.classification)
        
        # Check if the camera is in the configuration and if it's a string
        if "camera" not in conf:
            raise KeyError("The key 'camera' is missing from the rule configuration.")
        if not isinstance(conf["camera"], str):
            raise TypeError("The value for 'camera' must be a string.")
        self.camera_name = conf["camera"]
        
        # Check if the camera is in the dependencies and make sure it's a Camera
        if conf["camera"] not in resources:
            raise ValueError(f"Camera {conf['camera']} not found in dependencies.")
        if not isinstance(resources[conf["camera"]].resource, Camera):
            raise TypeError("The camera resource must be of type Camera.")
        self.camera = cast(Camera, resources[conf["camera"]].resource)
        
        # Check if classifier is in the configuration and if it's a string
        # Check if the classifier is in the dependencies and make sure it's a VisionClient
        if "classifier" not in conf:
            raise KeyError("The key 'classifier' is missing from the rule configuration.")
        if not isinstance(conf["classifier"], str):
            raise TypeError("The value for 'classifier' must be a string.")
        if conf["classifier"] not in resources:
            raise ValueError(f"Classifier {conf['classifier']} not found in dependencies.")
        if not isinstance(resources[conf["classifier"]].resource, VisionClient):
            raise TypeError("The classifier resource must be of type Vision.")
        self.classifier = cast(VisionClient, resources[conf["classifier"]].resource)
        
        # Check if class_regex is in the configuration and if it's a string
        if "class_regex" not in conf:
            raise KeyError("The key 'class_regex' is missing from the rule configuration.")
        if not isinstance(conf["class_regex"], str):
            raise TypeError("The value for 'class_regex' must be a string.")
        self.class_regex = str(conf["class_regex"])
        
        # Check if confidence_pct is in the configuration, if it's a number, and if it's between 0 and 1
        if "confidence_pct" not in conf:
            raise KeyError("The key 'confidence_pct' is missing from the rule configuration.")
        if not isinstance(conf["confidence_pct"], (int, float)):
            raise TypeError("The value for 'confidence_pct' must be a number.")
        if conf["confidence_pct"] < 0 or conf["confidence_pct"] > 1:
            raise ValueError("The value for 'confidence_pct' must be between 0 and 1.")
        self.confidence_pct = float(conf["confidence_pct"])
        
        # Check if inverse_pause_secs is in the configuration, if it's a number, and if it's positive, otherwise set to 0
        if "inverse_pause_secs" in conf:
            if not isinstance(conf["inverse_pause_secs"], (int, float)):
                raise TypeError("The value for 'inverse_pause_secs' must be a number.")
            if conf["inverse_pause_secs"] < 0:
                raise ValueError("The value for 'inverse_pause_secs' must be a positive number.")
            self.inverse_pause_secs = int(conf["inverse_pause_secs"])
        else:
            self.inverse_pause_secs = 0

class RuleTracker(Rule):
    camera: Camera
    camera_name: str
    tracker: VisionClient
    inverse_pause_secs: int
    pause_on_known_secs: int

    def __init__(self, conf: Mapping[str, ValueTypes], resources: Mapping[str, Resource]):
        super().__init__(RuleType.tracker)
        
        # Check if the camera is in the configuration and if it's a string
        if "camera" not in conf:
            raise KeyError("The key 'camera' is missing from the rule configuration.")
        if not isinstance(conf["camera"], str):
            raise TypeError("The value for 'camera' must be a string.")
        self.camera_name = conf["camera"]
        
        # Check if the camera is in the dependencies and make sure it's a Camera
        if conf["camera"] not in resources:
            raise ValueError(f"Camera {conf['camera']} not found in dependencies.")
        if not isinstance(resources[conf["camera"]].resource, Camera):
            raise TypeError("The camera resource must be of type Camera.")
        self.camera = cast(Camera, resources[conf["camera"]].resource)
        
        # Check if tracker is in the configuration and if it's a string
        # Check if the classifier is in the dependencies and make sure it's a VisionClient
        if "tracker" not in conf:
            raise KeyError("The key 'tracker' is missing from the rule configuration.")
        if not isinstance(conf["tracker"], str):
            raise TypeError("The value for 'tracker' must be a string.")
        if conf["tracker"] not in resources:
            raise ValueError(f"Tracker {conf['tracker']} not found in dependencies.")
        if not isinstance(resources[conf["tracker"]].resource, VisionClient):
            raise TypeError(f"The tracker resource must be of type Vision. Got {type(resources[conf['tracker']].resource)}")
        self.tracker = cast(VisionClient, resources[conf["tracker"]].resource)
        
        # Check if confidence_pct is in the configuration, if it's a number, and if it's between 0 and 1
        if "confidence_pct" not in conf:
            raise KeyError("The key 'confidence_pct' is missing from the rule configuration.")
        if not isinstance(conf["confidence_pct"], (int, float)):
            raise TypeError("The value for 'confidence_pct' must be a number.")
        if conf["confidence_pct"] < 0 or conf["confidence_pct"] > 1:
            raise ValueError("The value for 'confidence_pct' must be between 0 and 1.")
        self.confidence_pct = float(conf["confidence_pct"])
        
        # Check if inverse_pause_secs is in the configuration, if it's a number, and if it's positive, otherwise set to 0
        if "inverse_pause_secs" in conf:
            if not isinstance(conf["inverse_pause_secs"], (int, float)):
                raise TypeError("The value for 'inverse_pause_secs' must be a number.")
            if conf["inverse_pause_secs"] < 0:
                raise ValueError("The value for 'inverse_pause_secs' must be a positive number.")
            self.inverse_pause_secs = int(conf["inverse_pause_secs"])
        else:
            self.inverse_pause_secs = 0
        
class RuleCall(Rule):
    resource: ResourceBase
    method: str
    payload:str = ""
    result_path: str = ""
    result_function: str = ""
    result_operator: Operator
    result_value: Any
    inverse_pause_secs: int

    def __init__(self, conf: Mapping[str, ValueTypes], resources: Mapping[str, Resource]):
        super().__init__(RuleType.call)
        # Check if the resource is in the configuration and if it's a string
        if "resource" not in conf:
            raise KeyError("The key 'resource' is missing from the rule configuration.")
        if not isinstance(conf["resource"], str):
            raise TypeError("The value for 'resource' must be a string.")
        # Check if the resource is in the dependencies and make sure it's a Resource
        if conf["resource"] not in resources:
            raise ValueError(f"Resource {conf['resource']} not found in dependencies.")
        if not isinstance(resources[conf["resource"]].resource, ResourceBase):
            raise TypeError("The resource must be of type ResourceBase.")
        self.resource = resources[conf["resource"]].resource

        # Check if the method is in the configuration and if it's a string
        if "method" not in conf:
            raise KeyError("The key 'method' is missing from the rule configuration.")
        if not isinstance(conf["method"], str):
            raise TypeError("The value for 'method' must be a string.")
        # Check if the resource has a method with the given name
        if not hasattr(self.resource, conf["method"]):
            raise ValueError(f"Method {conf['method']} not found in resource {conf['resource']}.")
        self.method = str(conf["method"])
        
        # Check if the payload is a string if it's in the configuration
        if "payload" in conf:
            if not isinstance(conf["payload"], str):
                raise TypeError("The value for 'payload' must be a string.")
            self.payload = str(conf["payload"])

        # Check if the result_path is in the configuration and if it's a string
        if "result_path" not in conf:
            raise KeyError("The key 'result_path' is missing from the rule configuration.")
        if not isinstance(conf["result_path"], str):
            raise TypeError("The value for 'result_path' must be a string.")
        self.result_path = str(conf["result_path"])
        
        # Check if the result_function is in the configuration and if it's a string
        if "result_function" not in conf:
            raise KeyError("The key 'result_function' is missing from the rule configuration.")
        if not isinstance(conf["result_function"], str):
            raise TypeError("The value for 'result_function' must be a string.")
        self.result_function = str(conf["result_function"])
        
        # Check if the result_operator is in the configuration and if it's a string
        if "result_operator" not in conf:
            raise KeyError("The key 'result_operator' is missing from the rule configuration.")
        if not isinstance(conf["result_operator"], str):
            raise TypeError("The value for 'result_operator' must be a string.")
        self.result_operator = Operator.from_string(conf["result_operator"])

        # Check if the result_value is in the configuration and if it's a string
        if "result_value" not in conf:
            raise KeyError("The key 'result_value' is missing from the rule configuration.")
        self.result_value = conf["result_value"]
        # Check if the inverse_pause_secs is in the configuration, if it's a number, and if it's positive
        if "inverse_pause_secs" not in conf:
            raise KeyError("The key 'inverse_pause_secs' is missing from the rule configuration.")
        if not isinstance(conf["inverse_pause_secs"], (int, float)):
            raise TypeError("The value for 'inverse_pause_secs' must be a number.")
        if conf["inverse_pause_secs"] < 0:
            raise ValueError("The value for 'inverse_pause_secs' must be a positive number.")
        self.inverse_pause_secs = int(conf["inverse_pause_secs"])

class RuleTime(Rule):
    ranges: list[TimeRange]
    def __init__(self, conf: Mapping[str, ValueTypes]):
        super().__init__(RuleType.time)
        if "ranges" in conf:
            if isinstance(conf["ranges"], list):
                self.ranges = []
                for r in conf["ranges"]:
                    if not isinstance(r, (dict,Mapping)):
                        raise TypeError("The value for 'ranges' must be a list of dictionaries.")
                    if "start_hour" not in r or "end_hour" not in r:
                        raise KeyError("The keys 'start_hour' and 'end_hour' are required in each range.")
                    # I'm not sure how I feel about including 'str' in here, but it seems like a possible common mistake...
                    if not isinstance(r["start_hour"], (int,float, str)) or not isinstance(r["end_hour"], (int, float, str)): 
                        raise TypeError("The values for 'start_hour' and 'end_hour' must be a number.")
                    self.ranges.append(TimeRange(int(r["start_hour"]), int(r["end_hour"])))
            elif isinstance(conf["ranges"], (dict, Mapping)):
                if "start_hour" not in conf["ranges"] or "end_hour" not in conf["ranges"]:
                    raise KeyError("The keys 'start_hour' and 'end_hour' are required in the range.")
                # I'm not sure how I feel about including 'str' in here, but it seems like a possible common mistake...
                if not isinstance(conf["ranges"]["start_hour"], (int, float, str)) or not isinstance(conf["ranges"]["end_hour"], (int, float, str)):
                    raise TypeError("The values for 'start_hour' and 'end_hour' must be a number.")
                self.ranges = [TimeRange(int(conf["ranges"]["start_hour"]), int(conf["ranges"]["end_hour"]))]
        elif "start_hour" in conf and "end_hour" in conf:
            # I'm not sure how I feel about including 'str' in here, but it seems like a possible common mistake...
            if not isinstance(conf["start_hour"], (int, float,str)) or not isinstance(conf["end_hour"], (int, float,str)):
                raise TypeError("The values for 'start_hour' and 'end_hour' must be a number.")
            self.ranges = [TimeRange(int(conf["start_hour"]), int(conf["end_hour"]))]
        else:
            raise KeyError("The configuration for a time rule must include 'ranges' or 'start_hour' and 'end_hour'.")

async def eval_rule(rule:RuleTime|RuleDetector|RuleClassifier|RuleTracker|RuleCall) -> dict[str, Any]:
    response:dict[str, Any] = { "triggered" : False }
    match rule.type:
        case RuleType.time:
            rule = cast(RuleTime, rule)
            curr_time = datetime.now()
            for r in rule.ranges:
                if (curr_time.hour >= r.start_hour) and (curr_time.hour < r.end_hour):
                    LOGGER.debug("Time triggered")
                    response["triggered"] = True   
        case RuleType.detection:
            rule = cast(RuleDetector, rule)
            all = await rule.detector.capture_all_from_camera(rule.camera_name, return_detections=True, return_image=True)
            if all is None or all.detections is None or all.image is None:
                LOGGER.error(f"Error: no image returned from {rule.camera_name}")
                return response
            d: Detection
            for d in all.detections:
                if (d.confidence >= rule.confidence_pct) and re.search(rule.class_regex, d.class_name):
                    LOGGER.debug("Detection triggered")
                    response["triggered"] = True
                    response["image"] = viam_to_pil_image(all.image)
                    response["value"] = d.class_name
                    response["resource"] = rule.camera_name
        case RuleType.classification:
            rule = cast(RuleClassifier, rule)
            all = await rule.classifier.capture_all_from_camera(rule.camera_name, return_classifications=True, return_image=True)

            if all is None or all.classifications is None or all.image is None:
                LOGGER.error(f"Error: no image returned from {rule.camera_name}")
                return response
            
            c: Classification
            for c in all.classifications:
                if (c.confidence >= rule.confidence_pct) and re.search(rule.class_regex, c.class_name):
                    LOGGER.debug("Classification triggered")
                    response["triggered"] = True
                    response["image"] = viam_to_pil_image(all.image)
                    response["value"] = c.class_name
                    response["resource"] = rule.camera
        case RuleType.tracker:
            rule = cast(RuleTracker, rule)
            # NOTE: we call capture_all_from_camera() in order to get an image and coordinates in case there is an actionable detection
            all = await rule.tracker.capture_all_from_camera(rule.camera_name, return_classifications=False, return_detections=True, return_image=True)

            if all is None or all.detections is None or all.image is None:
                LOGGER.error(f"Error: no image returned from {rule.camera}")
                return response
            
            approved_status = []

            current = await rule.tracker.do_command({"list_current": True})
            
            for d in all.detections:
                authorized = False

                # NOTE: the class name of a tracker detection that has been labeled now has a label appended to it,
                #  so it would never ever match a key in current[].  We will therefore strip this label.
                class_without_label = re.sub(r'\s+\(label:\s.*', '', d.class_name)
                LOGGER.debug(class_without_label + "-" + str(current["list_current"]))
                if "list_current" not in current:
                    LOGGER.error(f"Error: no list_current returned from {rule.tracker}")
                    return response
                if not isinstance(current["list_current"], Mapping):
                    LOGGER.error(f"Error: list_current is unexpected type: {type(current['list_current'])}")
                    return response

                if class_without_label in current["list_current"]:
                    k = current["list_current"][class_without_label]
                    if k["face_id_label"] or k["manual_label"] or k["re_id_label"]:
                        authorized = True
                        response["known_person_seen"] = True
                    approved_status.append(authorized)
                    if not authorized:
                        im = viam_to_pil_image(all.image)
                        response["image"] = im.crop((d.x_min, d.y_min, d.x_max, d.y_max))
                        response["value"] = class_without_label
                        response["resource"] = rule.camera
            LOGGER.debug(approved_status)
            if len(approved_status) > 0 and logic.NOR(approved_status):
                LOGGER.info("Tracker triggered")
                LOGGER.info(response)

                response["triggered"] = True
        case RuleType.call:
            rule = cast(RuleCall, rule)
            try:
                call_res = await call_method(rule.resource, rule.method, rule.payload, None)
                if rule.result_path:
                    call_res = get_value_by_dot_notation(call_res, rule.result_path)
                    if call_res == None:
                        LOGGER.error(f"data not found in path {rule.result_path}")
                        return response

                LOGGER.debug(call_res)
                if rule.result_function:
                    match rule.result_function:
                        case "len":
                            call_res = len(call_res)
                        case "any":
                            call_res = any(call_res)          

                response["triggered"] = rule.result_operator.invoke(call_res, rule.result_value)
                response["value"] = call_res
                response["resource"] = rule.resource
                LOGGER.debug(f"call rule eval to {response['triggered']} call_res {call_res} result_val {rule.result_value}")
            except Exception as e:
                LOGGER.error(f"Error in 'call' type rule, rule not properly evaluated: {e}")
    return response

def logical_trigger(logic_type, list):
    logic_function = getattr(logic, logic_type)
    return logic_function(list)

def get_value_by_dot_notation(data, path):
    """Access a nested dictionary value using dot notation."""

    keys = path.split('.')
    value = data

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None  # Key not found

    return value
