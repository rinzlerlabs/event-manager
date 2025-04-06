import json
from typing import Any

from viam.resource.base import ResourceBase
from viam.components.generic import Generic as GenericComponent
from viam.services.generic import Generic as GenericService
from viam.services.vision import VisionClient
from viam.components.sensor import Sensor

# TODO: Need to resolve the circular import issue with events, until then "event" must be untyped
async def call_method(resource:ResourceBase, method:str, payload:Any, event:Any) -> Any:
    """
    Calls a method on a resource with the given payload.
    Args:
        resource (ResourceBase): The resource to call the method on.
        method (str): The name of the method to call.
        payload (str): The payload to send to the method.
        event (Event): The event that triggered the action.
    Returns:
        The result of the method call.
    Raises:
        ValueError: If the method is not found or is not callable.
    """
    method = getattr(resource, method)
    if not method:
        raise ValueError(f"Method {method} not found on resource {resource.name}")
    if not callable(method):
        raise ValueError(f"Method {method} is not callable on resource {resource.name}")

    if payload:
        # we don't want to alter action.payload directly as it will be used as a template repeatedly
        payload_copy = payload

        if (event):
            # At some point we might want other things to be template variables, for now just label and event name
            payload_copy = payload_copy.replace('<<triggered_label>>', event.triggered_label)
            payload_copy = payload_copy.replace('<<triggered_camera>>', event.triggered_camera)
            payload_copy = payload_copy.replace('<<event_name>>', event.name)
        
            return await method(json.loads(payload_copy.replace("'", "\"")))
    else:
        return await method()
