import FreeCAD as App
from freecadOptics import laser, layout, optomech

from importlib import reload
import math
reload(optomech)
reload(layout)
reload(laser)

INCH = 25.4

base_dx = 15*INCH
base_dy = 16*INCH
base_dz = INCH

ddx = INCH
ddy = 1.5*INCH


layout.create_baseplate(base_dx, base_dy, base_dz)

# Offsets from table grid and positions for mounting holes
xoff = INCH/2
yoff = INCH/2

mount_holes = [[0*INCH, 0*INCH],
               [base_dx-INCH, 0*INCH],
               [base_dx-INCH, base_dy-INCH],
               [0*INCH, base_dy-INCH]]

input_y = base_dy-INCH
R1_CC_PBS_pos = [7*INCH, 15*INCH]

for xy in mount_holes:
	layout.place_element("Screw_hole_baseplate", optomech.baseplate_mount, xoff+xy[0], yoff+xy[1], 0)

beam = layout.add_beam_path(base_dx, input_y, -180)

layout.place_element("Input_Fiberport", optomech.fiberport_holder, base_dx, input_y, 180)

layout.place_element_along_beam("Beam_Splitter_1", optomech.pbs_on_skate_mount, beam, 0b1, 180, base_dy-100)
layout.place_element_along_beam("Input_Split", optomech.splitter_mount_c05g, beam, 0b10, -45, 30)

layout.place_element_along_beam("F_300_Lens", optomech.lens_holder_l05g, beam, 0b101, -90, 30)

layout.place_element_along_beam("Half_waveplate", optomech.rotation_stage_rsp05, beam, 0b101, -90, 30)
layout.place_element_along_beam("Beam_Splitter_1", optomech.pbs_on_skate_mount, beam, 0b101, -90, 30)

layout.place_element_along_beam("AOM_1", optomech.isomet_1205c_on_km100pm, beam, 0b1011, 0, 240)
layout.place_element_along_beam("Output_Mirror_1", optomech.mirror_mount_k05s2, beam, 0b1011, -135-3, 20)
layout.place_element_along_beam("Output_Mirror_2", optomech.mirror_mount_k05s2, beam, 0b1011, 45, 40)

layout.place_element_along_beam("Half_waveplate_2", optomech.rotation_stage_rsp05, beam, 0b1010, -90, 35)
layout.place_element_along_beam("Beam_Splitter_2", optomech.pbs_on_skate_mount, beam, 0b1010, -90, 35)

layout.place_element_along_beam("AOM_2", optomech.isomet_1205c_on_km100pm, beam, 0b10101, 0, 170)
layout.place_element_along_beam("Output_2_Mirror_1", optomech.mirror_mount_k05s2, beam, 0b10101, -135-3, 20)
layout.place_element_along_beam("Output_2_Mirror_2", optomech.mirror_mount_k05s2, beam, 0b10101, 45, 40)

layout.place_element_along_beam("Half_waveplate_3", optomech.rotation_stage_rsp05, beam, 0b10100, -90, 35)
layout.place_element_along_beam("Beam_Splitter_3", optomech.pbs_on_skate_mount, beam, 0b10100, -90, 35)

layout.place_element_along_beam("AOM_3", optomech.isomet_1205c_on_km100pm, beam, 0b101001, 0, 100)
layout.place_element_along_beam("Output_3_Mirror_1", optomech.mirror_mount_k05s2, beam, 0b101001, -135-3, x=R1_CC_PBS_pos[0])

layout.place_element_along_beam("AOM_4", optomech.isomet_1205c_on_km100pm, beam, 0b101000, -90, 100)
layout.place_element_along_beam("Output_4_Mirror_1", optomech.mirror_mount_k05s2, beam, 0b101000, 45-3, y=R1_CC_PBS_pos[1])

#layout.place_element("R1_CC_PBS", optomech.pbs_on_skate_mount, *R1_CC_PBS_pos, 0)

layout.redraw()