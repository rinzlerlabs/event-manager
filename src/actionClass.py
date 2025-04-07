from typing import Mapping

from viam.utils import ValueTypes

from .common import Resource, get_resource_from_resource_map_by_name

class Action():
    resource: Resource
    method: str
    payload: str
    when_secs: int
    response_match: str = ""
    taken: bool = False
    last_taken: float
    def __init__(self, conf: Mapping[str, ValueTypes], resources: Mapping[str, Resource]):
        if "resource" not in conf:
            raise KeyError("The key 'resource' is missing from the action configuration.")
        if not isinstance(conf["resource"], str):
            raise TypeError("The value for 'resource' must be a string.")
        self.resource = get_resource_from_resource_map_by_name(conf["resource"], resources)

        if "method" not in conf:
            raise KeyError("The key 'method' is missing from the action configuration.")
        if not isinstance(conf["method"], str):
            raise TypeError("The value for 'method' must be a string.")
        if not hasattr(self.resource.resource, conf["method"]):
            raise AttributeError(f"The method '{conf['method']}' does not exist on the resource {conf['resource']}.")
        self.method = conf["method"]

        if "payload" not in conf:
            raise KeyError("The key 'payload' is missing from the action configuration.")
        if not isinstance(conf["payload"], str):
            raise TypeError("The value for 'payload' must be a string.")
        self.payload = conf["payload"]

        if "when_secs" in conf:
            if not isinstance(conf["when_secs"], (int, float, str)):
                raise TypeError("The value for 'when_secs' must be an integer.")
            self.when_secs = int(conf["when_secs"])
            if self.when_secs < 0 and self.when_secs != -1: # I'm not a fan of -1 for a sentinal value, but it is used in the original code
                raise ValueError("The value for 'when_secs' cannot be negative.")
        
        if "response_match" in conf:
            if not isinstance(conf["response_match"], str):
                raise TypeError("The value for 'response_match' must be a string.")
            self.response_match = conf["response_match"]
