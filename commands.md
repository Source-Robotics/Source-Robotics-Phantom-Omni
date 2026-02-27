# My Phantom Folder

This is a Python library for interfacing with the Phantom Omni haptic device on Windows. It uses the OpenHaptics HDAPI via `ctypes` and does not require ROS.

## Requirements

- Windows OS
- PCIe Firewire card (for connecting the Phantom Omni)
- Phantom Omni device drivers installed
- OpenHaptics Toolkit installed (provides `HD.dll` and `HDU.dll`)
- Python 3.x

Make sure that the OpenHaptics `bin` directory (which contains `HD.dll`) is in your system's `PATH` environment variable, or that `HD.dll` is located in `C:\Windows\System32`.

## Usage

You can use the `PhantomOmni` class to initialize the device, read data (position, velocity, gimbal angles, buttons), and send force commands.

### Example

```python
import time
from phantom import PhantomOmni

def main():
    # Initialize the device
    omni = PhantomOmni()
    
    try:
        # Read data in a loop
        for _ in range(100):
            pos = omni.get_position()
            vel = omni.get_velocity()
            buttons = omni.get_buttons()
            
            print(f"Position: {pos}")
            print(f"Buttons: {buttons}")
            
            # Send a force command (e.g., a small spring force towards the origin)
            # omni.set_force(-0.01 * pos[0], -0.01 * pos[1], -0.01 * pos[2])
            
            time.sleep(0.1)
    finally:
        # Always close the connection when done
        omni.close()

if __name__ == "__main__":
    main()
```

## API Reference

### `PhantomOmni(device_name=None)`
Initializes the Phantom Omni device. If `device_name` is `None`, it connects to the default device.

### `get_position()`
Returns the current Cartesian position of the device as a list `[x, y, z]`.

### `get_velocity()`
Returns the current Cartesian velocity of the device as a list `[x, y, z]`.

### `get_gimbal_angles()`
Returns the current gimbal angles (roll, pitch, yaw) as a list `[roll, pitch, yaw]`.

### `get_buttons()`
Returns a dictionary with the current state of the stylus buttons: `{"button1": bool, "button2": bool}`.

### `set_force(force_x, force_y, force_z)`
Sends a force command to the device in Newtons.

### `close()`
Stops the scheduler and disables the device. This is called automatically when the object is destroyed, but it's good practice to call it explicitly or use a `try...finally` block.
