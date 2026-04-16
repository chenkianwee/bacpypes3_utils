import asyncio
import bacpypes3_utils
# ==============================================================================
# User Inputs
# ==============================================================================
server_ipaddr = "172.16.10.196"
local_ipaddr = '172.16.10.111'
# server_ipaddr = "1100:14.188.35.4:0"
# local_ipaddr = '192.168.92.5'
device_instance = 908
device_name = 'BACnetRead'
vendor_id = 999
# for single read
object_identifier = 'analog-value,1' # 'multi-state-value,3'
property_identifier = 'present-value'
# for multiple reads
obj_prop_ids = ['analog-value,4',['present-value', 'object-name'],'analog-value,5',['present-value']]
debug = True

# ==============================================================================
# region: Funtion
# ==============================================================================
async def main():
    app = None
    try:
        app = bacpypes3_utils.create_bacnet_app(local_ipaddr=local_ipaddr, device_instance=device_instance, device_name=device_name, 
                                                      vendor_id=vendor_id, debug = debug)
        
        # single read
        res = await bacpypes3_utils.read_single_property(app, server_ipaddr, object_identifier, property_identifier)
        print(res)
        # multiple read
        results = await bacpypes3_utils.read_multiple_property(app, server_ipaddr, obj_prop_ids)
        print(f'{results}')
        
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