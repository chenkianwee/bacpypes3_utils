import re
import socket
from typing import Any

import bacpypes3
from bacpypes3.pdu import Address
from bacpypes3.app import Application
from bacpypes3.ipv4 import IPv4Address
from bacpypes3.settings import settings
from bacpypes3.basetypes import ObjectType
from bacpypes3.vendor import get_vendor_info
from bacpypes3.apdu import SubscribeCOVRequest
from bacpypes3.constructeddata import AnyAtomic
from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.apdu import AbortReason, AbortPDU, ErrorRejectAbortNack
from bacpypes3.primitivedata import ObjectIdentifier, PropertyIdentifier

def validate_ip_address(ip: Address) -> bool:
    result = True
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if not isinstance(ip, Address):
            raise ValueError("Provide Address as bacpypes.Address object")
        s.bind(ip.addrTuple)
    except OSError:
        result = False
    finally:
        s.close()
    return result

def pdu_source2_str(pdu_source: bacpypes3.pdu.RemoteStation) -> str:
    network_number = str(pdu_source.addrNet) 
    ip_wrapper = str(IPv4Address(pdu_source.addrAddr))
    return f'{network_number}:{ip_wrapper}'

def create_bacnet_app(local_ipaddr: str = None, device_instance: int = None, device_name: str = None, 
                      vendor_id: int = None, custom_app: Application = None, debug: bool = False) -> Application:
    """
    Create a bacnet app.

    Parameters
    ----------
    local_ipaddr: str, optional
        Ip address of your local machine. If local IP is not given will just use the default IP found on your machine.

    device_instance: int, optional
        instance of this device, if not given will just use the default from bacpypes.

    device_name: str, optional
        name of this device, if not given will just use the default from bacpypes.
    
    vendor_id: int, optional
        id of vendor, if not given will just use the default from bacpypes.

    custom_app: Application, optional
        custom app to create. You can pass in a custom app you have created to create the app.

    debug: bool, optional
        print extra information about the application, if not given will just use the default is False.

    Returns
    -------
    Application
        the bacpypes application object that can be used to read bacnet server.
    """
    app = None
    args = SimpleArgumentParser().parse_args()
    if local_ipaddr != None:
        ip_cdir = local_ipaddr + '/24'
        is_valid = validate_ip_address(Address(ip_cdir))
        if is_valid:
            args.address = local_ipaddr + '/24'
        else:
            print(f'Given ip address is not valid. Using default ip from bacpypes3 settings')
    if device_instance != None:
        args.instance = device_instance
    if device_name != None:
        args.name = device_name
    if vendor_id != None:
        args.vendoridentifier = vendor_id

    if custom_app == None:
        # build the application
        app = Application.from_args(args)
    else:
        app = custom_app.from_args(args)

    if debug:
        print(f'settings: {settings}')
    return app

async def get_device_description(app: Application, device_address: bacpypes3.pdu.RemoteStation, device_identifier: ObjectIdentifier) -> str:
    """
    get device description.

    Parameters
    ----------
    app: Application
        bacnet application.

    device_address: Address
        address of the device to read

    device_identifier: ObjectIdentifier
        id or instance of the device to read.

    Returns
    -------
    str
        description of the device.
    """
    device_description = 'not available'
    try:
        device_description = await app.read_property(
            device_address, device_identifier, "description"
        )
    except ErrorRejectAbortNack as err:
        print(f"{device_identifier} description error: {err}\n")
    
    return device_description

async def get_obj_ids_from_device(app: Application, device_address: bacpypes3.pdu.RemoteStation, 
                                  device_identifier: ObjectIdentifier) -> list[ObjectIdentifier]:
    """
    Read the entire object list from a device at once, or if that fails, read the object identifiers one at a time.

    Parameters
    ----------
    app: Application
        bacnet application.

    device_address: Address
        address of the device to read

    device_identifier: ObjectIdentifier
        id or instance of the device to read.

    Returns
    -------
    list[ObjectIdentifier]
        all the objects in this device.
    """

    # try reading the whole thing at once, but it might be too big and
    # segmentation isn't supported
    try:
        object_list = await app.read_property(
            device_address, device_identifier, "object-list"
        )
        return object_list
    
    except AbortPDU as err:
        if err.apduAbortRejectReason != AbortReason.segmentationNotSupported:
            print(f"{device_identifier} object-list abort: {err}\n")
            return []
        
    except ErrorRejectAbortNack as err:
        print(f"{device_identifier} object-list error/reject: {err}\n")
        return []

    # fall back to reading the length and each element one at a time
    object_list = []
    try:
        # read the length
        object_list_length = await app.read_property(
            device_address,
            device_identifier,
            "object-list",
            array_index=0,
        )

        # read each element individually
        for i in range(object_list_length):
            object_identifier = await app.read_property(
                device_address,
                device_identifier,
                "object-list",
                array_index=i + 1,
            )
            object_list.append(object_identifier)

    except ErrorRejectAbortNack as err:
        print(f"{device_identifier} object-list length error/reject: {err}\n")

    return object_list

async def get_properties_from_obj_id(app: Application, obj_id: ObjectIdentifier, vendor_info: bacpypes3.vendor.VendorInfo, 
                                     device_address: bacpypes3.pdu.RemoteStation) -> dict:
    """
    Read the properties from the object.

    Parameters
    ----------
    app: Application
        bacnet application.

    obj_id: ObjectIdentifier
        bacnet application.

    vendor_info: bacpypes3.vendor.VendorInfo
        vendor info.

    device_address: Address
        address of the device to read

    Returns
    -------
    dict | None
        if operation fails return None. Dictionary containing the name:value of the object.
    """
    object_class = vendor_info.get_object_class(obj_id[0])
    if object_class is None:
        print(f"unknown object type: {obj_id}\n")
        return None
    
    # read the property list
    property_list = None
    try:
        property_list = await app.read_property(device_address, obj_id, "property-list")
    except ErrorRejectAbortNack as err:
        print(f"{obj_id} property-list error: {err}\n")
        return None
    
    obj_name = await app.read_property(device_address, obj_id, 'object-name')
    property_dict = {'name': obj_name}
    
    if obj_id[0] == ObjectType.device:
        property_dict['ipv4-addr'] = pdu_source2_str(device_address)
    
    for property_identifier in property_list:
        try:
            property_class = object_class.get_property_type(property_identifier)
            if property_class is None:
                print(f"{obj_id} unknown property: {property_identifier}\n")
                continue

            property_value = await app.read_property( device_address, obj_id, property_identifier)
            property_dict[str(property_identifier)] = property_value

        except ErrorRejectAbortNack as err:
            print(f"{obj_id} {property_identifier} error: {err}\n")
    
    if property_dict:
        return {str(obj_id): property_dict}
    else:
        return None

async def discover(lwr_lim: int, uppr_lim: int, local_ipaddr: str = None, device_instance: int = None, 
                   device_name: str = None, vendor_id: int = None, debug: bool = False) -> list[list[dict]]:
    """
    Discover all the bacnet devices on the network within the instance limit specified.

    Parameters
    ----------
    lwr_lim: int
        the lower limit of the device instances you are searching. If lwr_lim and uppr_lim is the same you are only searching for one device.

    uppr_lim: int
        the upper limit of the device instances you are searching. If lwr and uppr lim is the same you are only searching for one device.

    local_ipaddr: str, optional
        Ip address of your local machine. If local IP is not given will just use the default IP found on your machine.

    device_instance: int, optional
        instance of this device, if not given will just use the default from bacpypes.

    device_name: str, optional
        name of this device, if not given will just use the default from bacpypes.
    
    vendor_id: int, optional
        id of vendor, if not given will just use the default from bacpypes.

    debug: bool, optional
        print extra information about the application, if not given will just use the default is False.

    Returns
    -------
    list[list[dict]]
        list[number of devices, number of obj_ids in the devices].
    """
    app = create_bacnet_app(local_ipaddr = local_ipaddr, device_instance = device_instance, device_name = device_name, 
                            vendor_id = vendor_id, debug = debug)
    
    i_ams = await app.who_is(lwr_lim, uppr_lim)
    dev_ls = []
    for i_am in i_ams:
        device_address = i_am.pduSource
        ipv4_addr = pdu_source2_str(device_address)
        device_identifier = i_am.iAmDeviceIdentifier
        vendor_info = get_vendor_info(i_am.vendorID)
        device_description = await get_device_description(app, device_address, device_identifier)
        print(f"DEVICE FOUND: {device_identifier} @ {ipv4_addr}, from vendor: {vendor_info.vendor_identifier}, description: {device_description}")
        # for each device get all the objects on the device
        obj_id_list = await get_obj_ids_from_device(app, device_address, device_identifier)
        obj_ls = []
        for obj_id in obj_id_list:
            props_dict = await get_properties_from_obj_id(app, obj_id, vendor_info, device_address)
            obj_ls.append(props_dict)
        dev_ls.append(obj_ls)
    return dev_ls

async def read_single_property(app: Application, server_ipaddr: str, obj_id: str | ObjectIdentifier, 
                               property_id: str | PropertyIdentifier) -> bacpypes3.primitivedata:
    """
    Read the properties from the object.

    Parameters
    ----------
    app: Application
        bacnet application.

    server_ipaddr: str
        e.g. "192.168.92.5" or "1100:14.188.35.4:0". Run the discover function to find the ipaddr of the device you are interested in.

    obj_id: str | ObjectIdentifier
        the object identifier the property is located in. e.g. 'analog-value,4'

    property_id: str | PropertyIdentifier
        the property identifier. e.g. 'present-value'

    Returns
    -------
    bacpypes3.primitivedata
        results from the read.
    """
    try:
        sgl_response = await app.read_property(
                        server_ipaddr,
                        obj_id,
                        property_id,
                    )
    except ErrorRejectAbortNack as err:
        print(f"    - exception: {err}")
        sgl_response = err

    if isinstance(sgl_response, AnyAtomic):
        print("    - schedule objects")
        sgl_response = sgl_response.get_value()

    return sgl_response

async def read_multiple_property(app: Application, server_ipaddr: str, obj_prop_ids: list) -> list:
    """
    Read the properties from the object.

    Parameters
    ----------
    app: Application
        bacnet application.

    server_ipaddr: str
        e.g. "192.168.92.5" or "1100:14.188.35.4:0". Run the discover function to find the ipaddr of the device you are interested in.

    obj_prop_ids: list
        a list of object identifier and property identifiers to read. e.g. ['analog-value,4',['present-value', 'object-name'],'analog-value,5',['present-value']]

    Returns
    -------
    list
        list of results.
    """
    try:
        mltp_response = await app.read_property_multiple(server_ipaddr, obj_prop_ids)

    except ErrorRejectAbortNack as err:
            print(f"    - exception: {err}")
            mltp_response = err
    
    if isinstance(mltp_response, AnyAtomic):
            print("    - schedule objects")
            mltp_response = mltp_response.get_value()

    return mltp_response

async def write_single_property(val2write: Any, app: Application, server_ipaddr: str, obj_id: str | ObjectIdentifier, 
                                property_id: str | PropertyIdentifier, write_priority: int = None) -> bacpypes3.primitivedata:
    """
    Read the properties from the object.

    Parameters
    ----------
    val2write: Any
        the value to write.

    app: Application
        bacnet application.

    server_ipaddr: str
        e.g. "192.168.92.5" or "1100:14.188.35.4:0". Run the discover function to find the ipaddr of the device you are interested in.

    obj_id: str | ObjectIdentifier
        the object identifier the property is located in. e.g. 'analog-value,4'

    property_id: str | PropertyIdentifier
        the property identifier. e.g. 'present-value'

    write_priority: int, optional
        a value between 1 and 16. 1 being the top priority

    Returns
    -------
    bacpypes3.primitivedata
        results from the read.
    """
    property_index_re = re.compile(r"^([0-9A-Za-z-]+)(?:\[([0-9]+)\])?$")

    obj_id = ObjectIdentifier(obj_id)
    # split the property identifier and its index
    property_index_match = property_index_re.match(property_id)
    if not property_index_match:
        raise ValueError("property specification incorrect")
    property_identifier, property_array_index = property_index_match.groups()
    if property_identifier.isdigit():
        property_identifier = int(property_identifier)
    if property_array_index is not None:
        property_array_index = int(property_array_index)

    response = await app.write_property( server_ipaddr, obj_id, property_identifier, val2write, 
                                        property_array_index, write_priority)
    
    return response

def cov_subscription(target_device_address: str, object_identifier: str | ObjectIdentifier, process_identifier: int, 
                           lifetime: int, confirmation: bool = False, debug: bool = False) -> SubscribeCOVRequest:
    """
    Subscribe to a change of value (cov).

    Parameters
    ----------
    target_device_address: str
        e.g. "192.168.92.5" or "1100:14.188.35.4:0". Run the discover function to find the ipaddr of the device you are interested in.

    object_identifier: str | ObjectIdentifier
        the object identifier the property is located in. e.g. 'analog-value,4'

    process_identifier: int 
        subscriber process identifier. e.g. 1
    
    lifetime: int 
        lifetime of the subscription in seconds. e.g. 300

    confirmation: bool, optional
        issues confirmed notifications, not all controllers will ask for confirmation. default = False.

    debug: bool, optional
        print extra information about the application, if not given will just use the default is False.

    Returns
    -------
    SubscribeCOVRequest
        SubscribeCOVRequest object instance.
    """
    # interpret the address
    target_device_address = Address(target_device_address)
    if debug:
        print("target_device_address: %r", target_device_address)

    # interpret the object identifier
    if type(object_identifier) == str:
        object_identifier = ObjectIdentifier(object_identifier)
    if debug:
        print("object_identifier: %r", object_identifier)

    cov_request = SubscribeCOVRequest(
        destination=target_device_address,
        subscriberProcessIdentifier=process_identifier,
        monitoredObjectIdentifier=object_identifier,
        issueConfirmedNotifications=confirmation, # We know the device prefers False
        lifetime=lifetime
    )

    return cov_request