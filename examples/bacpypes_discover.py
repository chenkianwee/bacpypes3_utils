import json
import asyncio
import bacpypes3_utils

from pathlib import Path
# ==============================================================================
# User Inputs
# ==============================================================================
# local_ipaddr = '172.16.10.111'
local_ipaddr = '192.168.92.5'
device_instance = 910
device_name = 'BACnetRead'
vendor_id = 999
# range of device instance to search for
lwr_lim = 0
uppr_lim = 1000
debug = True
json_path = Path(__file__).parent.joinpath('whois.json')
# ==============================================================================
# region: Funtion
# ==============================================================================
async def main():
    app = None
    try:
        dev_ls = await bacpypes3_utils.discover(lwr_lim, uppr_lim, local_ipaddr=local_ipaddr, device_instance=device_instance, device_name=device_name, 
                                                vendor_id=vendor_id, debug=debug)
        # write all the information into a json file to be read by people
        new_dev_ls = []
        for dev_objs in dev_ls:
            new_dev_objs = []
            for obj in dev_objs:
                properties = list(obj.values())[0]
                new_properties = {k: str(v) for k,v in properties.items()}
                new_obj = {list(obj.keys())[0]: new_properties}
                new_dev_objs.append(new_obj)
            new_dev_ls.append(new_dev_objs)

        pretty_json_data = json.dumps(new_dev_ls, indent=4)
        with open(json_path, 'w') as f:
            f.write(pretty_json_data)
    finally:
        if app:
            app.close()
# ==============================================================================
# endregion: Function
# ==============================================================================
# Main
# ==============================================================================
if __name__== "__main__":
    asyncio.run(main())