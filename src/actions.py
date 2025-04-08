import re
from typing import Mapping, Callable
from logging import Logger

import time

from viam.utils import ValueTypes

from .common import Resource, get_resource_from_resource_map_by_name
from .resourceUtils import prep_payload

# This implementation is currently wrong, because it doesn't reset after the action is taken.
# We need to produce an action based on a config, action it, then dispose of it or reset it.
class Action():
    __logger: Logger
    resource: Resource
    method: Callable
    method_name: str
    payload: str
    when_secs: int = 0
    response_match: str = ""
    taken: bool = False
    last_taken: float = 0.0
    
    def __init__(self, logger:Logger, conf: Mapping[str, ValueTypes], resources: Mapping[str, Resource]):
        if logger is None:
            raise ValueError("The logger cannot be None.")
        if not isinstance(logger, Logger):
            raise TypeError("The logger must be an instance of Logger.")
        self.__logger = logger
        
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
        method_name = conf["method"]

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

        if not hasattr(self.resource.resource, method_name):
            raise AttributeError(f"The method '{method_name}' does not exist on the resource {self.resource.resource.name}.")
        
        method = getattr(self.resource.resource, method_name)
        if not method:
            raise ValueError(f"The method '{method_name}' on the resource {self.resource.resource.name} is None.")
        if not callable(method):
            raise ValueError(f"The method '{method_name}' is not callable on the resource {self.resource.resource.name}.")
        
        self.method = method
        self.method_name = method_name
    
    def should_action(self, last_triggered:float, sms_message:str|None=None) -> bool:
        if self.taken:
            return False
        if (sms_message is not None and sms_message != "") and self.response_match != "":
            if re.search(self.response_match, sms_message):
                self.__logger.debug(f"matched {self.response_match}")
                return True
        if self.when_secs != -1:
            if (last_triggered - self.last_taken) >= self.when_secs:
                return True
        return False
    
    async def do_action(self, event_name:str, trigger_label:str, trigger_source:str) -> None:
        try:
            payload = prep_payload(self.payload, event_name, trigger_label, trigger_source)
            if payload is not None:
                await self.method(payload)
            else:
                await self.method()
        except Exception as e:
            self.__logger.error(f"Error calling method {self.method_name} on resource {self.resource.resource.name}: {e}")
            raise e
        finally:
            self.taken = True # I think we want to set this to true even if there is an error, so that we don't keep trying to call the method
            self.last_taken = time.time()
