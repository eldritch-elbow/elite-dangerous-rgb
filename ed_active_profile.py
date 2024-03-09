from cuesdk import (CueSdk, CorsairDeviceFilter, CorsairDeviceType, CorsairError, CorsairLedId_Keyboard, CorsairLedColor, CorsairSessionState, CorsairDeviceInfo)
import json
import sys
from time import sleep

def init_cue_sdk():
    """Initializes the CUE SDK and connects to the Corsair device."""

    sdk_ready = False

    sdk = CueSdk()

    def print_device(device: CorsairDeviceInfo):
        print(f"Device found, ID = [{str(device.device_id)}] found:")
        print(f"   Type:       {str(device.type)}")
        print(f"   Model:      {device.model}")
        print(f"   LED count:  {device.led_count}")
        print(f"   Chan count: {device.channel_count}")

    def on_state_changed(evt):
        nonlocal sdk_ready

        print(evt.state)

        # The app must wait for CSS_Connected event before proceeding
        if evt.state == CorsairSessionState.CSS_Connected:
            details, err = sdk.get_session_details()
            print(details)

            devices, err = sdk.get_devices(
                CorsairDeviceFilter(
                    device_type_mask=CorsairDeviceType.CDT_All))
            if err == CorsairError.CE_Success and devices:

                for d in devices:
                    device, err = sdk.get_device_info(d.device_id)
                    if device:
                        print_device(device)

            else:
                print(err)
 
            sdk_ready = True

    connected = sdk.connect(on_state_changed)

    if not connected:
        print("CUE SDK not connected")
        exit()

    while not sdk_ready:
        print(f"Waiting for SDK connected state")
        sleep(1)


    return sdk

def set_key_color(sdk, dev_id, key_id, r, g, b, opacity):
    """
    Sets the color of a specific key.
    
    :param sdk: Instance of CueSdk to communicate with Corsair devices.
    :param key_id: The CorsairLedId of the key to set the color.
    :param r: Red component of the color (0-255).
    :param g: Green component of the color (0-255).
    :param b: Blue component of the color (0-255).
    """
    try:
        sdk.set_led_colors(dev_id, [CorsairLedColor(key_id, r,g,b, opacity)])
    except CorsairError as e:
        print(f"Error setting key color: {e}")

# Key mappings
ED_HPt_key = CorsairLedId_Keyboard.CLK_PrintScreen
ED_Cargo_key = CorsairLedId_Keyboard.CLK_ScrollLock
ED_LandG_key = CorsairLedId_Keyboard.CLK_PauseBreak
ED_Mode_key = CorsairLedId_Keyboard.CLK_M

ED_Numpad_keys = [ \
    CLK_Keypad0,CLK_Keypad1,CLK_Keypad2,CLK_Keypad3,CLK_Keypad4,CLK_Keypad5,CLK_Keypad6, \
    CLK_Keypad7,CLK_Keypad8,CLK_Keypad9,CLK_KeypadSlash,CLK_KeypadAsterisk,CLK_KeypadMinus, \
    CLK_KeypadPlus,CLK_KeypadComma,CLK_KeypadEnter,CLK_KeypadPeriodAndDelete]

def deployments(flags):

    # Hardpoints, Cargo, Landing gear
    # Deployed: 2, 205, 250 (blue)
    # Undeployed: 250, 167, 2 (orange)

    hardpt_status = flags & 0x00000040 
    cargo_status = flags & 0x00000200 
    landgear_status = flags & 0x00000004

    print(f"Flags [{flags}] -> HP {hardpt_status }, Cargo {cargo_status}, LG {landgear_status}")

    def deploy(k):
        set_key_color(sdk, device_id, k, 2, 205, 250, 255)
    def undeploy(k):
        set_key_color(sdk, device_id, k, 250, 167, 2, 255)

    deploy(ED_HPt_key)      if flags & 0x00000040 else undeploy(ED_HPt_key)
    deploy(ED_Cargo_key)    if flags & 0x00000200 else undeploy(ED_Cargo_key)
    deploy(ED_LandG_key)    if flags & 0x00000004 else undeploy(ED_LandG_key)    

def power(pips):

    # Power distributor
    sys_pips = pips[0]
    eng_pips = pips[1]
    wep_pips = pips[2]

    print(f"Pips: SYS {sys_pips} ENG {eng_pips} WEP {wep_pips} ")

    def get_power_rgb(pips):
        if pips <= 1: 
            return 255,255,255,0
        elif pips <= 4:
            return 255,255,255,255
        elif pips <= 6:
            return 250, 167,0,255
        else:
            return 255,0,0,255


    def set_power_pips(k, r,g,b, opac):
        set_key_color(sdk, device_id, k, r, g, b, opac)


    set_power_pips(CorsairLedId_Keyboard.CLK_LeftArrow, *get_power_rgb(sys_pips))
    set_power_pips(CorsairLedId_Keyboard.CLK_UpArrow, *get_power_rgb(eng_pips))
    set_power_pips(CorsairLedId_Keyboard.CLK_RightArrow, *get_power_rgb(wep_pips))    

def modes(flags):

    # HUD mode
    analysis_mode = flags & 0x08000000
    if (analysis_mode):
        set_key_color(sdk, device_id, ED_Mode_key, 12, 209, 240, 255) # Discovery blue
    else:
        set_key_color(sdk, device_id, ED_Mode_key, 250, 167, 2, 255) # Hud orange

def alert_status(flags):

    # Alert status
    def keypad_alert(r,g,b,o):
        for k in ED_Numpad_keys:
            set_key_color(sdk, device_id, k, r,g,b,o) # Hud orange

    # Process alerts in priority order
    if (flags & 0x00400000) or not (flags & 0x00000008):    # IsInDanger, Shields not up (red alert)
        keypad_alert(255,15,15,255)  
    elif flags & 0x00100000:            # On fire (fire orange)
        keypad_alert(250,114,2,255)  
    elif flags & 0x00080000:            # Low fuel (blue)
        keypad_alert(0,191,255,255)
    else:                               # Nominal (neon green)
        keypad_alert(15,255,80,255)

def main(status_file, dev_id):

    global sdk, device_id

    print("\n***** Initialising CUE SDK *****")
    device_id = dev_id
    sdk = init_cue_sdk()    

    print("\n***** SDK ready - initiating main loop *****")

    while True:

        sleep(1)

        with open(status_file) as f:

            try:

                data = json.load(f)

                print(data)                

                flags = int(data["Flags"])
                pips = data["Pips"]

                # Prepare key LED status for ship functions / status
                deployments(flags)
                modes(flags)
                power(pips)
                alert_status()
 
            except Exception as e:
                print(f"Error processing JSON file: {e}")    


if __name__ == "__main__":
    print("\n***** Elite Dangerous active keyboard profile *****")
    print ('Processing Status file: ', sys.argv[1])
    print ('Updating device: ', sys.argv[2])

    main(sys.argv[1], sys.argv[2])

