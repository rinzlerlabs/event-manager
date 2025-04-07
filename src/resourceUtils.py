import json
from typing import Any, Callable

from viam.resource.base import ResourceBase

async def call_method(method: Callable, payload:str, event_name:str|None=None, trigger_label:str|None=None, trigger_source:str|None=None) -> Any:
    """
    Calls a method with the given payload.
    Args:
        method (Callable): The method to call.
        payload (str): The payload to send to the method.
        event_name (str): The name of the event that triggered the action.
        trigger_label (str): The label of the trigger.
        trigger_source (str): The source of the trigger.
    Returns:
        The result of the method call.
    Raises:
        ValueError: If the method is not found or is not callable.
    """
    if not method:
        raise ValueError(f"Method {method} not found")
    if not callable(method):
        raise ValueError(f"Method {method} is not callable")

    if payload:
        # we don't want to alter action.payload directly as it will be used as a template repeatedly
        payload_copy = payload

        # At some point we might want other things to be template variables, for now just label and event name
        if trigger_label is not None:
            payload_copy = payload_copy.replace('<<triggered_label>>', trigger_label)
        if trigger_source is not None:
            payload_copy = payload_copy.replace('<<triggered_camera>>', trigger_source)
        if event_name is not None:
            payload_copy = payload_copy.replace('<<event_name>>', event_name)
        payload_copy = payload_copy.replace("'", "\"")

        return await method(json.loads(payload_copy))
    else:
        return await method()
