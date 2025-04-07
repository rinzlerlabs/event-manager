import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from logging import Logger

import bson
from viam.app.viam_client import ViamClient
from viam.proto.app.data import BinaryID, Filter, Order
from viam.utils import ValueTypes

async def request_capture(event: Any) -> Mapping[str, ValueTypes]|None:
    await asyncio.sleep(event.event_video_capture_padding_secs)
    current_time = datetime.now()
    # go back a second to ensure its not the current second
    current_time = current_time - timedelta(seconds=1)

    # Format the current time
    formatted_time_current = current_time.strftime('%Y-%m-%d_%H-%M-%S')

    # we want X seconds before and after, so subtract X*2 from current time
    time_minus = current_time - timedelta(seconds=(event.event_video_capture_padding_secs*2))

    # Format the time minus X*2
    formatted_time_minus = time_minus.strftime('%Y-%m-%d_%H-%M-%S')

    store_args = { "command": "save",
        "from": formatted_time_minus,
        "to": formatted_time_current,
        "metadata": _label(event.name, event.video_capture_resource, event.last_triggered),
        "async": True
    }
    
    try:
        if event.video_capture_resource == None:
            event.logger.error("video_capture_resource is None")
            return
        store_result:Mapping[str, ValueTypes] = await event.video_capture_resource.do_command( store_args )
        return store_result
    except Exception as e:
        event.logger.error(e)

async def get_triggered_cloud(logger:Logger, app_client:ViamClient, event_manager_name:str,organization_id:str, event_name:str|None=None, num:int=5)-> Any: # This return value is a cluster...we need to fix this
    if app_client is None:
        raise ValueError("app_client is None")
    filter_args = {}
    matched = []
    matched_index_by_dt = {}

    # first get recent tabular data, as this is the "data of record"
    # Note: the assumption is made that no other tabular data is being stored for this component
    query = []
    match:dict = {"component_name": event_manager_name}
    if event_name != None:
        match[f"data.readings.state.{event_name}" ] = { "$exists": True }
        query.append(bson.encode({ "$match": { f"data.readings.state.{event_name}" : { "$exists": True }}}))
    query.append(bson.encode({ "$match": match }))
    query.append(bson.encode({ "$sort": { "time_received": -1 } }))
    query.append(bson.encode({ "$limit": num }))

    tabular_data = await app_client.data_client.tabular_data_by_mql(organization_id=organization_id, query=query)
    for tabular in tabular_data:
        state = tabular["data"]["readings"]["state"] # type: ignore
        for reading in state:
            if event_name == None or event_name == reading:
                matched_index_by_dt[state[reading]["last_triggered"]] = len(matched)# type: ignore
                triggered_camera = ""
                if "triggered_camera" in state[reading]:# type: ignore
                    triggered_camera = state[reading]["triggered_camera"]# type: ignore
                matched.append({"event": reading, "time": state[reading]["last_triggered"],# type: ignore
                                "location_id": tabular["location_id"], "organization_id": tabular["organization_id"], "triggered_camera": triggered_camera })
            if len(matched) == num:
                break
        if len(matched) == num:
            break

    # now try to match any videos based on event timestamp
    videos = await app_client.data_client.binary_data_by_filter(filter=Filter(**filter_args), include_binary_data=False, limit=100, sort_order=Order.ORDER_DESCENDING)
    for video in videos[0]:
        logger.debug(video.metadata)
        spl = video.metadata.file_name.split('--')
        if len(spl) > 3:
            vtime = datetime.fromtimestamp( int(float(spl[3].replace('.mp4',''))), timezone.utc).isoformat() + 'Z'
            if vtime in matched_index_by_dt:
                logger.debug(video)
                matched[matched_index_by_dt[vtime]]["video_id"] = video.metadata.id
    return matched

# deletes video from the cloud
async def delete_from_cloud(app_client:ViamClient, id:str, organization_id:str, location_id:str) -> int:
    if app_client is None:
        raise ValueError("app_client is None")
    resp = await app_client.data_client.delete_binary_data_by_ids(binary_ids=[BinaryID(file_id=id, organization_id=organization_id, location_id=location_id)])
    return resp
def _name_clean(string):
    return string.replace(' ','_')

def _label(event_name, cam_name, last_triggered):
    return _name_clean(f"SAVCAM--{event_name}--{cam_name}--{str(last_triggered)}")
