from pymavlink import mavutil
from time import sleep

# Start a connection listening on a UDP port
vehicle = mavutil.mavlink_connection('udpin:localhost:14540')

# Wait for the first heartbeat 
#   This sets the system and component ID of remote system for the link
vehicle.wait_heartbeat()
print("Heartbeat from system (system %u component %u)" % (vehicle.target_system, vehicle.target_component))

vehicle.arducopter_arm()

# Once connected, use 'vehicle' to get and send messages
while True:
    vehicle.wait_heartbeat()
    globalPos = vehicle.messages['GLOBAL_POSITION_INT']
    print(globalPos.lat)
    print(globalPos.lon)
    print(globalPos.alt)
    message = vehicle.mav.command_long_encode(
        vehicle.target_system,  # Target system ID
        vehicle.target_component,  # Target component ID
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,  # ID of command to send
        0,  # Confirmation
        mavutil.mavlink.MAVLINK_MSG_ID_BATTERY_STATUS,  # param1: Message ID to be streamed
        1000000, # param2: Interval in microseconds
        0,       # param3 (unused)
        0,       # param4 (unused)
        0,       # param5 (unused)
        0,       # param5 (unused)
        0        # param6 (unused)
        )
    vehicle.mav.send(message)
    response = vehicle.recv_match(type='COMMAND_ACK', blocking=True)
    if response and response.command == mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL and response.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
        print("Command accepted")
    else:
        print("Command failed")