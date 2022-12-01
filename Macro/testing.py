import FreeCAD as App
from freecadOptics import laser, layout, optomech

from importlib import reload
import math
reload(optomech)
reload(layout)
reload(laser)

layout.create_baseplate(200, 200, layout.INCH)

beam = layout.add_beam_path(20, 0, 90)

layout.place_element_along_beam("Probe_Mirror_1", optomech.mirror_mount_k05s2, beam, 0, 20, -45)

layout.place_element_along_beam("Probe_Mirror_2", optomech.mirror_mount_k05s2, beam, 0, 20, 135)

layout.place_element_along_beam("PBS_1", optomech.pbs_on_skate_mount, beam, 0, 50, 90)

layout.place_element_along_beam("Probe_Mirror_3", optomech.mirror_mount_k05s2, beam, 1, 160, -125, 2)

#layout.place_element_along_beam("Probe_Mirror_4", optomech.mirror_mount_k05s2, beam, 2, 50, 45)

#layout.place_element_along_beam("PBS_2", optomech.pbs_on_skate_mount, beam, 1, 100, 90)

layout.place_element("Probe_Mirror_5", optomech.mirror_mount_k05s2, 40, 120, -45)

layout.place_element("Probe_Mirror_5", optomech.mirror_mount_k05s2, 100, 120, 135)

layout.redraw()
