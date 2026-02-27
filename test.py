import time
import sys
from phantom import PhantomOmni

def main():
    print("Initializing Phantom Omni...")
    try:
        omni = PhantomOmni()

        print("Device initialised. Reading state… (Ctrl+C to stop)\n")
        fmt_v3 = lambda v: f"[{v[0]:7.2f},{v[1]:7.2f},{v[2]:7.2f}]"

        while True:
            s = omni.get_state()
            print(
                f"Pos(mm):{fmt_v3(s['position'])}  "
                f"Vel(mm/s):{fmt_v3(s['velocity'])}  ",
                flush=True,
            )
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        if 'omni' in locals():
            omni.close()

if __name__ == "__main__":
    main()


