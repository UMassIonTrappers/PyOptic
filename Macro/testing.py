import FreeCAD as App
from freecadOptics import laser, layout, optomech

from importlib import reload
import math
reload(optomech)
reload(layout)
reload(laser)

layout.create_baseplate(200, 200, layout.INCH)

beam = layout.add_beam_path(20, 200, -90)

layout.place_element_along_beam("Testing", optomech.pinhole_ida12, beam_obj=beam, beam_index=0b1, angle=-90, distance=25)
#layout.place_element_along_beam("Wavemeter_Mirror_1", optomech.mirror_mount_k05s2, beam_obj=beam, beam_index=0b1, angle=-135, distance=25)
#layout.place_element_along_beam("Input_Rotation_Stage", optomech.rotation_stage_rsp05, beam_obj=beam, beam_index=0b1, angle=-90, distance=80)
#layout.place_element_along_beam("Beam_Splitter_1", optomech.pbs_on_skate_mount, beam, 0b1, -90, 50)

layout.redraw()
