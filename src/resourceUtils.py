import json
from typing import Any, Callable

from viam.resource.base import ResourceBase

def prep_payload(payload: str, event_name: str|None=None, trigger_label: str|None=None, trigger_source: str|None=None) -> Any|None:
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
        return json.loads(payload_copy)
    return None
