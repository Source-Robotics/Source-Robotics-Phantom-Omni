import ctypes
import os
import sys
import time

# ---------------------------------------------------------------------------
# HDAPI constants – verified against this device's HD.dll via hardware scan
#
# CONFIRMED working on this installation (verified via hardware constant scanner):
#   0x2050  HD_CURRENT_POSITION      vec3 double  (mm)           CONFIRMED
#   0x2051  HD_CURRENT_VELOCITY      vec3 double  (mm/s)
#   0x2052  *** INVALID on this SDK – crashes the 1394 driver, DO NOT USE ***
#   0x2053  HD_CURRENT_JACOBIAN      matrix double (NOT joint angles)
#   0x2054  HD_CURRENT_TRANSFORM     16 doubles (4x4 matrix, NOT gimbal angles)
#   0x2100  HD_CURRENT_JOINT_ANGLES  vec3 double  (rad) waist/shoulder/elbow  CONFIRMED
#   0x2101  HD_CURRENT_GIMBAL_ANGLES vec3 double  (rad) yaw/pitch/roll
#   0x2058  HD_LAST_JOINT_TORQUE     vec3 double  (mNm)
#   0x2059  HD_LAST_GIMBAL_TORQUE    vec3 double  (mNm)
#   0x2067  HD_CURRENT_FORCE         vec3 double  (N)  set with hdSetDoublev
#   0x2116  HD_CURRENT_BUTTONS       int  bitmask  - press button during button_test.py to confirm
#   0x4001  HD_FORCE_OUTPUT          capability flag (hdEnable/hdDisable)
# ---------------------------------------------------------------------------
HD_DEFAULT_DEVICE = None

# --- double-valued state (hdGetDoublev) ---
HD_CURRENT_POSITION           = 0x2050   # vec3 mm               CONFIRMED
HD_CURRENT_VELOCITY           = 0x2051   # vec3 mm/s
# 0x2052 is INVALID on this device SDK and crashes the 1394 driver – omitted
# 0x2053 = HD_CURRENT_JACOBIAN (matrix, NOT joint angles)
# 0x2054 = HD_CURRENT_TRANSFORM (4x4 matrix first elements, NOT gimbal angles)
HD_CURRENT_JOINT_ANGLES       = 0x2100   # vec3 rad  – waist, shoulder, elbow  CONFIRMED
HD_CURRENT_GIMBAL_ANGLES      = 0x2101   # vec3 rad  – yaw, pitch, roll
HD_LAST_JOINT_TORQUE          = 0x2058   # vec3 mNm
HD_LAST_GIMBAL_TORQUE         = 0x2059   # vec3 mNm
HD_LAST_FORCE                 = 0x2010   # vec3 N    last commanded force (read-back)
HD_CURRENT_FORCE              = 0x2067   # vec3 N    set with hdSetDoublev

# --- integer-valued state (hdGetIntegerv) ---
HD_CURRENT_BUTTONS            = 0x2116   # bitmask  (HDint / c_int)
HD_CURRENT_SAFETY_SWITCH      = 0x2117
HD_CURRENT_INKWELL_SWITCH     = 0x2118

# --- capability flags for hdEnable / hdDisable (NOT data params) ---
HD_FORCE_OUTPUT               = 0x4001
HD_MAX_FORCE_CLAMPING         = 0x4002

# --- error codes ---
HD_SUCCESS                    = 0x0000

# Button bitmasks
HD_DEVICE_BUTTON_1 = 1   # gray stylus tip button
HD_DEVICE_BUTTON_2 = 2   # back button / inkwell switch
HD_DEVICE_BUTTON_3 = 4
HD_DEVICE_BUTTON_4 = 8


# ---------------------------------------------------------------------------
# HDErrorInfo struct  (returned by hdGetError)
# ---------------------------------------------------------------------------
class HDErrorInfo(ctypes.Structure):
    _fields_ = [
        ("errorCode",         ctypes.c_uint),
        ("internalErrorCode", ctypes.c_int),
        ("messageText",       ctypes.c_char_p),
    ]


class PhantomOmni:
    """
    Python library for the Phantom Omni haptic device on Windows.
    Uses ctypes to call OpenHaptics HD.dll directly – no ROS required.
    Communicates over FireWire (1394 PCIe card).
    """

    def __init__(self, device_name=HD_DEFAULT_DEVICE):
        self.device_name = device_name
        self.hHD = -1
        self.scheduler_started = False

        # ---- load HD.dll -----------------------------------------------
        try:
            self.hd_lib = ctypes.cdll.LoadLibrary("HD.dll")
        except OSError as e:
            raise RuntimeError(
                "Could not load HD.dll.  Make sure OpenHaptics is installed "
                "and HD.dll is on your PATH (usually C:\\Windows\\System32)."
            ) from e

        # ---- declare argtypes / restypes for every HDAPI call ----------
        self._setup_prototypes()

        # ---- open device -----------------------------------------------
        self._initialize()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _setup_prototypes(self):
        """Declare ctypes prototypes for all HDAPI functions we use."""
        lib = self.hd_lib

        lib.hdInitDevice.argtypes  = [ctypes.c_char_p]
        lib.hdInitDevice.restype   = ctypes.c_uint

        lib.hdEnable.argtypes      = [ctypes.c_uint]
        lib.hdEnable.restype       = None

        lib.hdDisable.argtypes     = [ctypes.c_uint]
        lib.hdDisable.restype      = None

        lib.hdStartScheduler.argtypes = []
        lib.hdStartScheduler.restype  = None

        lib.hdStopScheduler.argtypes  = []
        lib.hdStopScheduler.restype   = None

        lib.hdBeginFrame.argtypes  = [ctypes.c_uint]
        lib.hdBeginFrame.restype   = None

        lib.hdEndFrame.argtypes    = [ctypes.c_uint]
        lib.hdEndFrame.restype     = None

        lib.hdMakeCurrentDevice.argtypes = [ctypes.c_uint]
        lib.hdMakeCurrentDevice.restype  = None

        lib.hdGetDoublev.argtypes  = [ctypes.c_uint, ctypes.POINTER(ctypes.c_double)]
        lib.hdGetDoublev.restype   = None

        lib.hdSetDoublev.argtypes  = [ctypes.c_uint, ctypes.POINTER(ctypes.c_double)]
        lib.hdSetDoublev.restype   = None

        # NOTE: HDAPI stores button state as HDint (32-bit signed int)
        lib.hdGetIntegerv.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_int)]
        lib.hdGetIntegerv.restype  = None

        lib.hdDisableDevice.argtypes = [ctypes.c_uint]
        lib.hdDisableDevice.restype  = None

        # hdGetError returns a struct by value
        lib.hdGetError.argtypes = []
        lib.hdGetError.restype  = HDErrorInfo

    def _check_error(self, context=""):
        """
        Call after any HDAPI sequence to surface errors.
        Raises RuntimeError if a non-success errorCode is set.
        """
        err = self.hd_lib.hdGetError()
        if err.errorCode != HD_SUCCESS:
            msg = err.messageText.decode() if err.messageText else "unknown"
            raise RuntimeError(
                f"HDAPI error {'in ' + context + ' ' if context else ''}"
                f"(code=0x{err.errorCode:04X}, internal={err.internalErrorCode}): {msg}"
            )

    def _begin(self):
        """Set current device and begin a haptic frame."""
        self.hd_lib.hdMakeCurrentDevice(self.hHD)
        self.hd_lib.hdBeginFrame(self.hHD)

    def _end(self):
        """End the current haptic frame."""
        self.hd_lib.hdEndFrame(self.hHD)

    def _initialize(self):
        """Open and configure the Phantom Omni."""
        name_ptr = ctypes.c_char_p(
            self.device_name.encode("utf-8")) if self.device_name else None

        self.hHD = self.hd_lib.hdInitDevice(name_ptr)
        if self.hHD == 0xFFFFFFFF:   # HD_INVALID_HANDLE
            raise RuntimeError(
                "hdInitDevice failed – device not found or FireWire driver issue.")

        self._check_error("hdInitDevice")

        self.hd_lib.hdEnable(HD_FORCE_OUTPUT)
        self._check_error("hdEnable(HD_FORCE_OUTPUT)")

        self.hd_lib.hdStartScheduler()
        self._check_error("hdStartScheduler")
        self.scheduler_started = True

        print(f"Phantom Omni initialised  (handle={self.hHD})")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_state(self):
        """
        Read ALL device state in one haptic frame (most coherent/reliable).

        Returns a dict with keys:
          position        – [x, y, z] mm
          velocity        – [vx, vy, vz] mm/s
          angular_vel     – [wx, wy, wz] rad/s
          joint_angles    – [waist, shoulder, elbow] rad
          gimbal_angles   – [yaw, pitch, roll] rad
          joint_torque    – [t0, t1, t2] mNm  (arm motors)
          gimbal_torque   – [t0, t1, t2] mNm  (wrist motors)
          last_force      – [fx, fy, fz] N    (last commanded force – read-back only)
          buttons_raw     – raw bitmask int
          button1         – bool  (stylus tip / gray button)
          button2         – bool  (back / inkwell)
        """
        pos     = (ctypes.c_double * 3)()
        vel     = (ctypes.c_double * 3)()
        joints  = (ctypes.c_double * 3)()
        gimbal  = (ctypes.c_double * 3)()
        jtorque = (ctypes.c_double * 3)()
        gtorque = (ctypes.c_double * 3)()
        lforce  = (ctypes.c_double * 3)()
        btns    = ctypes.c_int(0)

        self._begin()
        self.hd_lib.hdGetDoublev(HD_CURRENT_POSITION,      pos)
        self.hd_lib.hdGetDoublev(HD_CURRENT_VELOCITY,      vel)
        # NOTE: 0x2052 (angular velocity) crashes the 1394 driver on this SDK – skipped
        self.hd_lib.hdGetDoublev(HD_CURRENT_JOINT_ANGLES,  joints)
        self.hd_lib.hdGetDoublev(HD_CURRENT_GIMBAL_ANGLES, gimbal)
        self.hd_lib.hdGetDoublev(HD_LAST_JOINT_TORQUE,     jtorque)
        self.hd_lib.hdGetDoublev(HD_LAST_GIMBAL_TORQUE,    gtorque)
        self.hd_lib.hdGetDoublev(HD_LAST_FORCE,            lforce)
        self.hd_lib.hdGetIntegerv(HD_CURRENT_BUTTONS,      ctypes.byref(btns))
        self._end()

        raw = btns.value
        return {
            "position":      list(pos),
            "velocity":      list(vel),
            "joint_angles":  list(joints),   # waist, shoulder, elbow (rad)
            "gimbal_angles": list(gimbal),   # yaw, pitch, roll (rad)
            "joint_torque":  list(jtorque),  # arm joint torques (mNm)
            "gimbal_torque": list(gtorque),  # wrist torques (mNm)
            "last_force":    list(lforce),   # last commanded force read-back (N)
            "buttons_raw":   raw,
            "button1":       bool(raw & HD_DEVICE_BUTTON_1),
            "button2":       bool(raw & HD_DEVICE_BUTTON_2),
        }

    def get_position(self):
        """Cartesian position [x, y, z] in mm."""
        pos = (ctypes.c_double * 3)()
        self._begin()
        self.hd_lib.hdGetDoublev(HD_CURRENT_POSITION, pos)
        self._end()
        return list(pos)

    def get_velocity(self):
        """Cartesian velocity [vx, vy, vz] in mm/s."""
        vel = (ctypes.c_double * 3)()
        self._begin()
        self.hd_lib.hdGetDoublev(HD_CURRENT_VELOCITY, vel)
        self._end()
        return list(vel)

    def get_gimbal_angles(self):
        """Gimbal (wrist) joint angles [a0, a1, a2] in radians."""
        angles = (ctypes.c_double * 3)()
        self._begin()
        self.hd_lib.hdGetDoublev(HD_CURRENT_GIMBAL_ANGLES, angles)
        self._end()
        return list(angles)

    def get_joint_angles(self):
        """Arm joint angles [waist, shoulder, elbow] in radians."""
        angles = (ctypes.c_double * 3)()
        self._begin()
        self.hd_lib.hdGetDoublev(HD_CURRENT_JOINT_ANGLES, angles)
        self._end()
        return list(angles)

    def get_buttons(self):
        """
        Button state dict.

        Returns:
          {"button1": bool, "button2": bool, "raw": int}

        Phantom Omni hardware:
          button1 (bit 0) = gray stylus tip button
          button2 (bit 1) = back / inkwell switch
        """
        btns = ctypes.c_int(0)
        self._begin()
        self.hd_lib.hdGetIntegerv(HD_CURRENT_BUTTONS, ctypes.byref(btns))
        self._end()

        raw = btns.value
        return {
            "button1": bool(raw & HD_DEVICE_BUTTON_1),
            "button2": bool(raw & HD_DEVICE_BUTTON_2),
            "raw":     raw,
        }

    def get_force_feedback(self):
        """
        Read back the last force that was commanded to the device.

        NOTE: The Phantom Omni has NO force sensors – it is force-output only.
        This returns the most recent force vector sent via set_force(), not a
        measured interaction force.

        Returns: [fx, fy, fz] in Newtons
        """
        f = (ctypes.c_double * 3)()
        self._begin()
        self.hd_lib.hdGetDoublev(HD_LAST_FORCE, f)
        self._end()
        return list(f)

    def get_joint_torques(self):
        """
        Read the last motor torques on the three arm joints (waist, shoulder, elbow).
        Returns [t0, t1, t2] in milli-Newton-metres.
        """
        t = (ctypes.c_double * 3)()
        self._begin()
        self.hd_lib.hdGetDoublev(HD_LAST_JOINT_TORQUE, t)
        self._end()
        return list(t)

    def get_gimbal_torques(self):
        """
        Read the last motor torques on the three gimbal (wrist) joints.
        Returns [t0, t1, t2] in milli-Newton-metres.
        """
        t = (ctypes.c_double * 3)()
        self._begin()
        self.hd_lib.hdGetDoublev(HD_LAST_GIMBAL_TORQUE, t)
        self._end()
        return list(t)

    def set_force(self, force_x, force_y, force_z):
        """
        Command a Cartesian force output (Newtons).
        HD_FORCE_OUTPUT must be enabled (done in __init__).

        WARNING: keep forces small (<2 N) to avoid collisions or injury.
        """
        force = (ctypes.c_double * 3)(force_x, force_y, force_z)
        self._begin()
        self.hd_lib.hdSetDoublev(HD_CURRENT_FORCE, force)
        self._end()

    def diagnose_buttons(self, duration=5.0, interval=0.1):
        """
        Diagnostic helper: scan several candidate HD_CURRENT_BUTTONS
        constant values simultaneously so you can confirm which one
        actually changes when you press the stylus button.

        Press the button repeatedly while this runs and look for the
        value that toggles between 0 and non-zero.

        Args:
            duration : seconds to run
            interval : polling interval in seconds
        """
        # Candidates from different SDK versions / documentation sources
        candidates = {
            "0x2116 (current)": 0x2116,
            "0x2053":           0x2053,
            "0x2060":           0x2060,
            "0x2115":           0x2115,
        }

        print("\n=== Button Diagnostic Mode ===")
        print("Press button 1 (stylus tip) repeatedly while this runs.")
        print(f"Scanning for {duration}s …\n")
        print(f"{'Time':>6}", end="")
        for name in candidates:
            print(f"  {name:>18}", end="")
        print()

        deadline = time.time() + duration
        while time.time() < deadline:
            row = {}
            for name, const in candidates.items():
                val = ctypes.c_int(0)
                self._begin()
                self.hd_lib.hdGetIntegerv(const, ctypes.byref(val))
                self._end()
                row[name] = val.value

            t = deadline - time.time()
            print(f"{duration - t:>6.1f}", end="")
            for name in candidates:
                print(f"  {row[name]:>18}", end="")
            print(flush=True)
            time.sleep(interval)

        print("\n=== End Diagnostic ===\n")

    def close(self):
        """Stop the scheduler and close the device handle."""
        if self.scheduler_started:
            self.hd_lib.hdStopScheduler()
            self.scheduler_started = False

        if self.hHD != -1:
            self.hd_lib.hdDisable(HD_FORCE_OUTPUT)
            self.hd_lib.hdDisableDevice(self.hHD)
            self.hHD = -1
            print("Phantom Omni closed.")

    def __del__(self):
        self.close()
