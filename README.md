# Phantom-Omni-Source-Robotics
Guide on how to use Phanom Omni device with Source Robotics robots!

FIRE WIRE PCI CARD WE USED: Digitus DS-30201-5 3+1

1. This device is 20+ years old.
2. https://kyle.machul.is/2016/10/03/using-a-firewire-phantom-omni-on-windows-8-10/ good guide
3. Download legacy drivers from here: https://support.microsoft.com/en-us/topic/firewire-port-based-device-does-not-work-correctly-in-windows-8-1-or-windows-8-2242eed9-e8e2-00eb-c854-9335ea06c5fe
4. For your system x64 or x84
5. driver folder and "successfully" installed the Legacy1394.inf file. In our case they were here: C:\Program Files (x86)\1394 OHCI Compliant Host Controller (Legacy)\x64_driver
6.  https://support.3dsystems.com/s/article/Haptic-Device-Drivers?language=en_US We are using windows 10 so we isntall v3.5 Phantom Device Driver v5.1.7:
for Firewire or Parallel devices

Docs: https://s3.amazonaws.com/dl.3dsystems.com/binaries/support/downloads/Sensable/3DS/PDD_InstallGuide.pdf

Download OpenHaptics_Developer_Edition_v3.4.0.zip from: https://softwaresupport.oqton.com/s/article/OpenHaptics-for-Windows-Developer-Edition-v34?language=en_US
https://support.3dsystems.com/s/article/OpenHaptics-for-Windows-Developer-Edition-v34?language=en_US


Possible repos that will allow control of external arms: 

https://github.com/abdulbasit656/Bio_Med_Phantom_Robot

https://github.com/tbs-ualberta/PHANSIM

URDF files: https://github.com/gripsCAR/phantom_omni
