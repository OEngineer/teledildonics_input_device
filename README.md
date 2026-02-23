# The (as yet unnamed) Teledildonic Input Device
## What it is
## What it does
## The firmware
## Building
### Parts required
  - 3D printed parts (see below)
  - 155mm length of M6 threaded rod
  - 2x M6 threaded inserts
  - 2x 1.5mm x 6mm long plastic screws
  - Unexpected Maker TinyS3
  - Flexible stranded hookup wire, ideally solderable and in different colors (I used 24AWG silicone wire)
  - Li-poly cell (I used a 400mAh one that fit; check space available in model or 3D print)
  - Solid tinned or silver-coated wire, 20-22 AWG. Make sure that this is solderable (much "craft wire" is enameled and so not easily soldered).
### Tools and supplies required
  - Soldering iron and solder
  - Heat setting tool for threaded inserts (or use your soldering iron)
  - Wire stripper
  - Needlenose pliers
  - Low- or medium-strength thread locker (green or blue)
  - Binder clip to hold the spacers in place during assembly (or you can use masking tape pieces)
### 3D Print
Print the following parts (models in the `hardware/` directory):
  - 9x `spacer`
  - 1x `top`
  - 1x `base`
  - 1x `base_cover`
### Attach threaded inserts
Use a soldering iron or similar to melt the threaded inserts into the `top` and `base` parts.
### Making the sensors
Make 9 sensors:
  - Insert the end of your solid wire into one of the two holes on the side of the `spacer`.
  - Twist the end into a loop. You will be soldering to this loop.
  - Pass the wire around the spacer, keeping it tight
  - Bend the wire sharply so it can pass through the other hole.
  - Cut the wire about 2cm from the bend
  - Insert the cut end into the hole
  - Bend it over or twist it into a loop
### Final Assembly
Start at the base.
  - Thread the M5 rod into the base. If you have threadlocker, use a dab of it here.
  - For each of the nine sensors:
    - Slide the next `spacer` (wired with solid wire) over the threaded rod
    - Rotate it so that the four holes line up with the ones in the base and other sensors and the ends of the solid wire are positioned 90 degrees clockwise from the prior one. This will ensure that a single one of the 4 channels won't get over-filled with hookup wire.
    - Clip the binder clip onto the threaded rod just above the spacer. This will keep it in place while you're working on it. If you don't have a binder clip, you can use a piece of masking tape to stick it to the prior sensor.
    - Solder the stripped end of a piece of hookup wire to the end of the solid wire
    - Cut the hookup wire long enough to reach the base cover plus 3cm or so
    - Strip the cut end of the hookup wire about 2-3mm.
    - Insert the hookup wire into the next GPIO pad of the TinyS3 (start at GPIO0)
    - Solder the wire onto the TinyS3 board
## Installing the firmware
  - Install MicroPython from the [micropython.org website](https://micropython.org/download/UM_TINYS3/)
  - Install `mpremote` (or you can use `rshell`, `Thonny`, etc.)
  - Copy the contents of `src/` (and `src/lib`) to the root of the filesystem:
    ```bash
    mpremote cp -r src/* :/
    ```
  - The first time you run the firmware, you will be prompted to create a calibration file.
  - You can remove '/calibration.json' from your flash filesystem to be prompted again.
  - Test by running ```mpremote repl```:
  ```bash
  [OEngineer/teledildonics_input_device] % mpremote repl
  Connected to MicroPython at /dev/cu.usbmodem3144101
  Use Ctrl-] or Ctrl-x to exit this shell
  <ctrl-D>
  MPY: soft reboot
  No valid calibration found; using defaults.
  Do you want to calibrate now (y/n)?y
  Phase 1 (3 s): set the device down - do not touch it.
  Press Enter to start rest phase...
  Press Enter to start handling phase...
  Phase 2 (10 s): stroke, fondle, and handle the device now.
  Calibration done.
    offsets: [25714, 25038, 26755, 26214, 24746, 26703, 26815, 29324, 28949]
    scales:  [7910, 10332, 11986, 12678, 11635, 9600, 11263, 11661, 13998]
  Calibration saved.
  focus: 0 insertion: 88 center: 51
  focus: 0 insertion: 89 center: 52
  ...
  ```