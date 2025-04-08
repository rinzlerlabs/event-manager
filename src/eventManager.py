import asyncio
import re
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import (Any, ClassVar, Dict, Mapping, Optional, cast, Iterable)
from logging import Logger

import pydot
from typing_extensions import Self
from viam.app.viam_client import ViamClient
from viam.components.sensor import Sensor
from viam.errors import NoCaptureToStoreError
from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.types import Model, ModelFamily
from viam.rpc.dial import DialOptions
from viam.utils import (SensorReading, ValueTypes, from_dm_from_extra,
                        struct_to_dict)

from . import actions, event as events, notifications, rules, triggered
from .config import Config

class eventManager(Sensor, Reconfigurable):
    MODEL: ClassVar[Model] = Model(ModelFamily("viam", "event-manager"), "eventing")

    config: Config
    name: str
    dm_sent_status = {}
    event_stop_signals:list[asyncio.Event] = []
    event_loop_tasks:list[asyncio.Task] = []
    logger: Logger

    # Constructor
    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        my_class = cls(config.name)
        my_class.reconfigure(config, dependencies)
        return my_class

    # Validates JSON Configuration
    @classmethod
    def validate(cls, config: ComponentConfig):
        # TODO: Add validation for the config as a whole
        deps = []

        attributes = struct_to_dict(config.attributes)

        resources = attributes.get("resources")
        if resources is not None:
            if not isinstance(resources, (dict, Mapping)):
                raise TypeError("expected resources to be a dictionary")
            for r in resources.keys():
                deps.append(r)
        sms_module = config.attributes.fields["sms_module"].string_value or ""
        if sms_module != "":
            deps.append(sms_module)
        email_module = config.attributes.fields["email_module"].string_value or ""
        if email_module != "":
            deps.append(email_module)
        return deps

    # Handles attribute reconfiguration
    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        self.reconfigure_internal(config, dependencies)
        asyncio.ensure_future(self.start_event_manager()) 
        return
    
    def reconfigure_internal(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        self.name = config.name

        if self.logger is None:
            raise ValueError("Logger is not set. The logger is injected by viam-python-sdk, if it's missing, this is probably a bug in the SDK.")
        
        self.stop_running_tasks()

        # reset event states
        self.config = Config(self.logger, config, dependencies)

    def stop_running_tasks(self) -> None:
        if self.event_stop_signals is not None and isinstance(self.event_stop_signals, Iterable) and len(self.event_stop_signals) > 0:
            while self.event_stop_signals:
                stop_event = self.event_stop_signals.pop()
                stop_event.set()

    async def viam_connect(self) -> ViamClient:
        if self.config.app_api_key == '' or self.config.app_api_key is None \
            or self.config.app_api_key_id == '' or self.config.app_api_key_id is None:
            raise ValueError("App API Key and App API Key ID are required for cloud connection.")
        dial_options = DialOptions.with_api_key(
            api_key=self.config.app_api_key,
            api_key_id=self.config.app_api_key_id
        )
        return await ViamClient.create_from_dial_options(dial_options)

    async def start_event_manager(self):
        self.logger.info("Starting event manager")

        if (self.config.app_api_key is not None and self.config.app_api_key != '' \
            and self.config.app_api_key_id is not None and self.config.app_api_key_id != ''):
            self.app_client = await self.viam_connect()

        event: events.Event
        for event in self.config.events:
            stop_event = asyncio.Event()
            self.event_stop_signals.append(stop_event)
            task = asyncio.create_task(self.event_check_loop(event, stop_event))
            self.event_loop_tasks.append(task)

    async def event_check_loop(self, event: events.Event, stop_event):
        """
        This function runs in a loop and checks for events that are triggered.
        """
        self.logger.info("Starting event check loop for " + event.name)
        while not stop_event.is_set():
            await self.check_event(event)

        self.logger.info("Ending event check loop for " + event.name)

    async def check_event(self, event:events.Event):
        """
        This function checks if the event has been triggered.
        """
        try:
            if ((self.config.mode in event.modes) and ((event.is_triggered == False) or ((event.is_triggered == True) and ((time.time() - event.last_triggered) >= event.pause_alerting_on_event_secs)))):
                start_time = datetime.now()
                event.state = events.EventState.monitoring

                # reset event and actions before evaluating
                event.is_triggered = False
                event.actions_paused = False
                event.pause_reason = ""

                event.triggered_camera = ""
                event.triggered_label = ""
                event.triggered_rules = []

                event.flip_action_status(False)

                rule_results:list[dict[str, Any]] = []
                for rule in event.rules:
                    self.logger.debug(rule)
                    result = await rule.eval()
                    if result["triggered"] == True:
                        event.sequence_count_current = event.sequence_count_current + 1
                    else:
                        event.sequence_count_current = 0

                    if event.sequence_count_current < event.trigger_sequence_count:
                        # don't consider triggered as we've not met the threshold
                        result["triggered"] = False
                    else:
                        # reset sequence count if we are at the sequence count threshold
                        event.sequence_count_current = 0

                    # rule settings can determine if the event loop should be paused on
                    # non-triggered events
                    if isinstance(rule, rules.RuleDetector) or \
                        isinstance(rule, rules.RuleClassifier) or \
                            isinstance(rule, rules.RuleTracker) or \
                                isinstance(rule, rules.RuleCall):
                        if rule.inverse_pause_secs > 0 and not result["triggered"]:
                            event.paused_until = time.time() + rule.inverse_pause_secs
                            event.state = events.EventState.paused
                            event.pause_reason = f"{rule.type} rule inverse pause for {rule.inverse_pause_secs} secs"
                            break
                    if isinstance(rule, rules.RuleTracker):
                        if rule.pause_on_known_secs > 0 and "known_person_seen" in result and result["known_person_seen"]:
                            event.paused_until = time.time() + rule.pause_on_known_secs
                            event.state = events.EventState.paused
                            event.pause_reason = "known person"
                            break

                    rule_results.append(result)

                if (event.state != events.EventState.paused) and (rules.logical_trigger(event.rule_logic_type, [res['triggered'] for res in rule_results]) == True):
                    event.is_triggered = True
                    event.last_triggered = time.time()
                    event.state = events.EventState.triggered

                    rule_index = 0
                    triggered_image = None

                    # not all rules consider or capture images and labels, check if we have them
                    for rule in event.rules:
                        if "triggered" in rule_results[rule_index] and rule_results[rule_index]['triggered'] == True:
                            if hasattr(rule, 'camera'):
                                if "value" in rule_results[rule_index]:
                                    event.triggered_label = rule_results[rule_index]["value"]
                                if "resource" in rule_results[rule_index]:
                                    event.triggered_camera = rule_results[rule_index]["resource"]
                                if "image" in rule_results[rule_index]:
                                    triggered_image = rule_results[rule_index]["image"]
                                    # remove once copied because we will use rule_results for state reporting
                                    del rule_results[rule_index]["image"]
                                if event.capture_video:
                                    asyncio.ensure_future(
                                        triggered.request_capture(event))
                        rule_index = rule_index + 1

                    event.triggered_rules = rule_results

                    for n in event.notifiers:
                        await n.notify(event.name, event.triggered_label, event.triggered_camera, triggered_image)

                # try to respect detection_hz as desired speed of detections
                elapsed = (datetime.now() - start_time).total_seconds()
                to_wait = (1 / event.detection_hz) - elapsed
                if to_wait > 0:
                    await asyncio.sleep(to_wait)
            elif (event.is_triggered == True) and (event.actions_paused == False):
                self.logger.debug("checking for ACTIONS")
                event.state = events.EventState.actioning

                # see if any actions need to be performed
                sms_message = ""
                # only poll for SMS if there are actions configured for this event
                # TODO: only poll if actions are checking for SMS responses
                #   # I think this is moot with the code below filtering for sms notifiers before doing anything
                if len(event.actions):
                    sms_notifiers = [n for n in event.notifiers if isinstance(n, notifications.SmsNotifier)]
                    for n in sms_notifiers:
                        sms_message = await n.check_sms_response(event.last_triggered) # This is a last one wins case, if there are multiple sms notifiers, we are going to have issues
                for action in event.actions:
                    await self.event_action(event, action, sms_message)
                await asyncio.sleep(1)
            else:
                # sleep if we know we are not currently checking for this event
                await asyncio.sleep(.5)
        except Exception as e:
            self.logger.error(f'Error in event check loop: {e}')
            self.logger.error(traceback.format_exc())
            await asyncio.sleep(1)
    
    async def event_action(self, event:events.Event, action:actions.Action, message:str|None):
        should_action = action.should_action(event.last_triggered, message)
        if should_action:
            if message is not None and message != "":
                # once we get a valid message, no other actions should be taken
                event.actions_paused = True
                event.state = events.EventState.paused
                event.pause_reason = "sms"
            await action.do_action(event.name, event.triggered_label, event.triggered_camera)

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, ValueTypes]:
        result:Dict[str, ValueTypes] = {}
        for name, args in command.items():
            if args is None or not isinstance(args, (dict, Mapping)):
                raise ValueError("args must be a dictionary")
            if name == "get_triggered":
                if not isinstance(args, dict):
                    raise ValueError("args must be a dictionary")
                
                # As far as I can tell, the org_id is needed for the cloud query
                org_id = args.get("organization_id", None)
                if org_id is None:
                    raise ValueError("organization_id is required")
                
                if self.app_client is None:
                    result["triggered"] = { "error": "app_api_key and app_api_key_id as well as data capture on GetReadings() for this module must be configured" }
                else:
                    result["triggered"] = await triggered.get_triggered_cloud(self.logger, self.app_client, self.name, org_id, num=args.get("number", 5), event_name=args.get("event", None))
            elif name == "delete_triggered_video":
                if not isinstance(args, dict):
                    raise ValueError("args must be a dictionary")
                id = args.get("id", None)
                if id is None:
                    raise ValueError("id is required")
                if not isinstance(id, str):
                    raise ValueError("id must be a string")

                location_id = args.get("location_id", None)
                if location_id is None:
                    raise ValueError("location_id is required")
                if not isinstance(location_id, str):
                    raise ValueError("location_id must be a string")

                organization_id = args.get("organization_id", None)
                if organization_id is None:
                    raise ValueError("organization_id is required")
                if not isinstance(organization_id, str):
                    raise ValueError("organization_id must be a string")
                
                if self.app_client is None:
                    result["total"] = { "error": "app_api_key and app_api_key_id as well as data capture on GetReadings() for this module must be configured" }
                else:
                    result["total"] = await triggered.delete_from_cloud(self.app_client, id, location_id, organization_id)
            elif name == "trigger_event":
                for e in self.config.events:
                    if e.name == args.get("event", ""):
                        e.is_triggered = True
                        e.last_triggered = time.time()
                        e.state = events.EventState.triggered
                        result = {"triggered": True}
            elif name == "pause_triggered":
                for e in self.config.events:
                    if (e.name == args.get("event", "")) and e.is_triggered == True:
                        e.state = events.EventState.paused
                        e.pause_reason = "manual"
                        e.actions_paused = True
                        result = {"paused": True}
            elif name == "respond_triggered":
                for e in self.config.events:
                    if (e.name == args.get("event", "")) and e.is_triggered == True:
                        for action in e.actions:
                            await self.event_action(e, action, args.get("response", ""))
                result = {"responded": True}

        return result

    async def get_readings(
        self, *, extra: Optional[Mapping[str, ValueTypes]] = None, timeout: Optional[float] = None, **kwargs
    ) -> Mapping[str, SensorReading]:
        ret:Mapping[str, SensorReading] = {}
        ret["state"] = {}
        ret["mode"]= self.config.mode
        include_dot = False
        graph: pydot.Graph|None = None
        if extra is not None and "include_dot" in extra:
            include_dot = bool(extra["include_dot"])
        
        if include_dot:
            graph = pydot.Dot("my_graph", graph_type="digraph",
                              bgcolor="white", fontname="Courier", fontsize="12pt")

        event_number = 0
        for e in self.config.events:
            # if this is a call from data management, only store events once while they are in 'triggered' or 'actioning' state
            if from_dm_from_extra(cast(Dict[str, Any], extra)): # This cast may fail if extra is not a dict, but afaik, it is always a dict?
                if (e.state == events.EventState.triggered) or (e.state == events.EventState.actioning):
                    if e.name in self.dm_sent_status and self.dm_sent_status[e.name] == e.last_triggered:
                        continue
                    else:
                        self.dm_sent_status[e.name] = e.last_triggered
                else:
                    continue
            
            if e.name not in ret["state"]:
                ret["state"][e.name] = {"state": e.state.name}

            if e.last_triggered > 0:
                ret["state"][e.name]["last_triggered"] = datetime.fromtimestamp(
                    int(e.last_triggered), timezone.utc).isoformat() + 'Z'
                ret["state"][e.name]["triggered_label"] = e.triggered_label
                ret["state"][e.name]["triggered_camera"] = e.triggered_camera
                ret["state"][e.name]["triggered_rules"] = e.triggered_rules

            if e.pause_reason != "":
                ret["state"][e.name]["pause_reason"] = e.pause_reason

            layer: pydot.Subgraph|None = None
            if include_dot:
                event_number = event_number + 1

                layer = pydot.Subgraph(
                    f'cluster_{event_number}', label=e.name, labelloc="t", style="solid")

                layer.add_node(pydot.Node(f'Setup{event_number}', label="Setup",
                               fontname="Courier", fontsize="10pt", color=layer_color(e.state, events.EventState.setup)))
                layer.add_node(pydot.Node(f'Monitoring{event_number}', label="Monitoring",
                               fontname="Courier", fontsize="10pt", color=layer_color(e.state, events.EventState.monitoring)))

                triggered_label = "Triggered"
                if "last_triggered" in ret["state"][e.name]:
                    triggered_label = triggered_label + "\n" + \
                        ret["state"][e.name]["last_triggered"]
                    triggered_label = triggered_label + "\n" + \
                        ret["state"][e.name]["triggered_label"]
                layer.add_node(pydot.Node(f'Triggered{event_number}', label=triggered_label,
                               fontname="Courier", fontsize="10pt", color=layer_color(e.state, events.EventState.triggered)))

                layer.add_node(pydot.Node(f'Paused{event_number}', label="Paused",
                               fontname="Courier", fontsize="10pt", color=layer_color(e.state, events.EventState.paused)))

                layer.add_edge(pydot.Edge(
                    f'Setup{event_number}', f'Monitoring{event_number}'))
                layer.add_edge(pydot.Edge(
                    f'Monitoring{event_number}', f'Triggered{event_number}'))
                layer.add_edge(pydot.Edge(
                    f'Paused{event_number}', f'Monitoring{event_number}'))

            actions = []
            for a in e.actions:
                a_ret = {
                    "resource": a.resource.name,
                    "payload": a.payload,
                    "method": a.method_name,
                    "taken": a.taken,
                    "response_match": a.response_match
                }
                if a.taken:
                    a_ret["when"] = datetime.fromtimestamp(
                        int(a.last_taken), timezone.utc).isoformat() + 'Z'
                actions.append(a_ret)

                if layer is not None:
                    a_label = f'Actioning\n{a.resource}/{a.method}'
                    a_font = "Courier"
                    if "when" in a_ret:
                        a_label = a_label + f'\n{a_ret["when"]}'
                        a_font = "Courier bold"
                    action_node = pydot.Node(f'a{event_number}{len(actions)}', label=a_label,
                                             fontname=a_font, fontsize="10pt", color=layer_color(e.state, events.EventState.actioning))
                    layer.add_node(action_node)
                    layer.add_edge(pydot.Edge(
                        f'Triggered{event_number}', f'a{event_number}{len(actions)}'))
                    layer.add_edge(pydot.Edge(
                        f'a{event_number}{len(actions)}', f'Paused{event_number}'))

            ret["state"][e.name]["actions"] = actions
            if include_dot:
                if len(e.actions) == 0 and layer is not None:
                    # connect straight to Paused if no configured actions
                    layer.add_edge(pydot.Edge(
                        f'Triggered{event_number}', f'Paused{event_number}'))
                if graph is not None:
                    graph.add_subgraph(layer)

        if from_dm_from_extra(cast(Dict[str, ValueTypes], extra)) and len(ret["state"]) == 0:
            raise NoCaptureToStoreError()

        if include_dot and graph is not None:
            ret["dot"] = graph.to_string()
        return ret


def layer_color(state, state_node):
    if state == state_node:
        return "red"
    else:
        return "black"
