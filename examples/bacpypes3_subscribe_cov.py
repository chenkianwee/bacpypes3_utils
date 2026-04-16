import asyncio
import bacpypes3_utils
from bacpypes3.app import Application
from bacpypes3.basetypes import StatusFlags, PropertyIdentifier
# ==============================================================================
# User Inputs
# ==============================================================================
# target_device_ipaddr = "172.16.10.250"
# local_ipaddr = '172.16.10.111'
# object_identifier = "analog-value,1"
target_device_ipaddr = "1100:14.188.35.4:0"
local_ipaddr = '192.168.92.5'
object_identifier = 'multi-state-value,4'
device_instance = 909
device_name = 'BACnetRead'
vendor_id = 999
# for cov subscription
process_identifier = 1
lifetime = 300
debug = True
# ==============================================================================
# region: Funtion
# ==============================================================================
class MyCOVApp(Application):
    # This catches Unconfirmed COVs (which your debug log shows the device is sending)
    async def do_UnconfirmedCOVNotificationRequest(self, apdu):
        print("\n--- UNCONFIRMED COV RECEIVED ---")
        print(f"From: {apdu.pduSource}")
        print(f"Object: {apdu.monitoredObjectIdentifier}")
        self.parse_notification(apdu)

    # Just in case it ever sends a Confirmed one, catch it and ACK it
    async def do_ConfirmedCOVNotificationRequest(self, apdu):
        print("\n--- CONFIRMED COV RECEIVED ---")
        print(f"From: {apdu.pduSource}")
        print(f"Object: {apdu.monitoredObjectIdentifier}")
        self.parse_notification(apdu)
        await self.response(apdu.ack())
    
    def parse_notification(self, apdu):
        for value in apdu.listOfValues:
            prop_id = value.propertyIdentifier
            raw_any = value.value  # This is the <Any object>
            
            try:
                if prop_id == PropertyIdentifier.presentValue:
                    # Grab the pure data tag directly (ignoring the open/close tags) the data is always sitting at index 1
                    data_tag = raw_any.tagList[1]
                    #============================================================
                    # for enocean contemporary controls
                    massive_number = data_tag.app_to_object()
                    # Apply the bitwise mask to chop off the uninitialized memory garbage! 0xFFFF keeps only the lowest 16 bits (values 0-65535)
                    clean_value = massive_number & 0xFFFF
                    print(f"Raw Gateway Garbage: {massive_number}")
                    print(f"Clean Present Value -> {clean_value}")
                    #============================================================
                    # actual_value = data_tag.app_to_object()
                    # print(f"Present Value -> {actual_value}")

                elif prop_id == PropertyIdentifier.statusFlags:
                    actual_flags = raw_any.cast_out(StatusFlags)
                    in_alarm = actual_flags[0]
                    fault = actual_flags[1]
                    overridden = actual_flags[2]
                    out_of_service = actual_flags[3]
                    # Convert the raw 1/0 bits into nice True/False booleans for readability
                    print(f"Status Flags -> Alarm: {bool(in_alarm)} | Fault: {bool(fault)} | Overridden: {bool(overridden)} | OOS: {bool(out_of_service)}")
                    
                else:
                    print(f"{prop_id} -> [Uncast Data]")
            
            except Exception as err:
                print(f"\n CRASH CAUGHT while casting '{prop_id}': {err}")
                print("--- What the device actually sent ---")
                # This will dump the raw BACnet tags to the console so we can see if it sent a Null, an Error, or something else!
                if hasattr(raw_any, 'debug_contents'):
                    raw_any.debug_contents()
                else:
                    print(f"Raw Object: {raw_any}")
                print("-------------------------------------")
                
async def main():
    app = None
    try:
        app = bacpypes3_utils.create_bacnet_app(local_ipaddr=local_ipaddr, device_instance=device_instance, device_name=device_name, 
                                                vendor_id=vendor_id, custom_app = MyCOVApp, debug = debug)
        cov_request = bacpypes3_utils.cov_subscription(target_device_ipaddr, object_identifier, process_identifier, lifetime, 
                                                       confirmation=False, debug=debug)
        renewal_interval = lifetime - 30
        while True:
            print(f"\n[SYSTEM] Sending/Renewing Subscription to {target_device_ipaddr}...")
            response = await app.request(cov_request)
            print(f"Subscription accepted! Response: {response}")
            print(f"[SYSTEM] Subscription active! Next renewal in {renewal_interval} seconds.")
            await asyncio.sleep(renewal_interval)

    except asyncio.CancelledError:
        print("Exiting...")

    except Exception as e:
        print(f"Failed: {e}")

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