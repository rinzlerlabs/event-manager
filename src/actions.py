import re
import time

from .actionClass import Action
from .events import Event
from .logger import LOGGER
from .resourceUtils import call_method


def flip_action_status(event:Event, direction:bool):
    action:Action
    for action in event.actions:
        action.taken = direction

async def eval_action(event:Event, action:Action, sms_message:str|None):
    if action.taken:
        return False
    if (sms_message is not None and sms_message != "") and (action.response_match != ""):
        if re.search(action.response_match, sms_message):
            LOGGER.debug(f"matched {action.response_match}")
            return True
    if action.when_secs != -1:
        if (time.time() - event.last_triggered) >= action.when_secs:
            return True
    return False

async def do_action(event:Event, action:Action):
    await call_method(action.resource.resource, action.method, action.payload, event)

    action.taken = True
    action.last_taken = time.time()
