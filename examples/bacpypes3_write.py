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
# for single write
val2write = 69.6
object_identifier = 'analog-value,1'
property_identifier = 'present-value'
debug = True
write_priority = None
# ==============================================================================
# region: Funtion
# ==============================================================================
async def main():
    app = None
    try:
        app = bacpypes3_utils.create_bacnet_app(local_ipaddr=local_ipaddr, device_instance=device_instance, device_name=device_name, 
                                                vendor_id=vendor_id, debug = debug)
        
        # single write
        response = await bacpypes3_utils.write_single_property(val2write, app, server_ipaddr, object_identifier, 
                                                               property_identifier, write_priority=write_priority)
        print(response)
        
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