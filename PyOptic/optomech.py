import FreeCAD as App
import Mesh
import Part
from math import *
from . import layout
import numpy as np

from pathlib import Path

stl_path = str(Path(__file__).parent.resolve()) + "/stl/"
drill_depth = 100
inch = 25.4

bolt_4_40 = {
    "clear_dia":0.120*inch,
    "tap_dia":0.089*inch,
    "head_dia":5.50,
    "head_dz":2.5 # TODO measure this
}

bolt_8_32 = {
    "clear_dia":0.172*inch,
    "tap_dia":0.136*inch,
    "head_dia":7,
    "head_dz":4.4
}

bolt_14_20 = {
    "clear_dia":0.260*inch,
    "tap_dia":0.201*inch,
    "head_dia":9.8,
    "head_dz":8,
    "washer_dia":9/16*inch
}

adapter_color = (0.6, 0.9, 0.6)
mount_color = (0.5, 0.5, 0.55)
glass_color = (0.5, 0.5, 0.8)
misc_color = (0.2, 0.2, 0.2)

# Used to tranform an STL such that it's placement matches the optical center
def _import_stl(stl_name, rotate, translate, scale=1):
    mesh = Mesh.read(stl_path+stl_name)
    mat = App.Matrix()
    mat.scale(App.Vector(scale, scale, scale))
    mesh.transform(mat)
    mesh.rotate(*np.deg2rad(rotate))
    mesh.translate(*translate)
    return mesh

def _bounding_box(obj, tol, fillet, x_tol=True, y_tol=True, z_tol=False, min_offset=(0, 0, 0), max_offset=(0, 0, 0), plate_off=0):
    if hasattr(obj, "Shape"):
        obj_body = obj.Shape.copy()
    elif hasattr(obj, "Mesh"):
        obj_body = obj.Mesh.copy()
    else:
        obj_body = obj
    obj_body.Placement = App.Placement()
    if hasattr(obj, "RelativePlacement"):
        obj_body.Placement = obj.RelativePlacement
        temp = obj
        while hasattr(temp, "ParentObject") and hasattr(temp.ParentObject, "RelativePlacement"):
            temp = temp.ParentObject
            obj_body.Placement *= temp.RelativePlacement
    global_bound = obj_body.BoundBox
    obj_body.Placement = App.Placement()
    bound = obj_body.BoundBox

    x_min, x_max = bound.XMin-tol*x_tol+min_offset[0], bound.XMax+tol*x_tol+max_offset[0]
    y_min, y_max = bound.YMin-tol*y_tol+min_offset[1], bound.YMax+tol*y_tol+max_offset[1]
    z_min = min(global_bound.ZMin-tol*z_tol+min_offset[2], -layout.inch/2+plate_off)-global_bound.ZMin+bound.ZMin
    z_max = max(global_bound.ZMax+tol*z_tol+max_offset[2], -layout.inch/2+plate_off)-global_bound.ZMax+bound.ZMax
    bound_part = _custom_box(dx=x_max-x_min, dy=y_max-y_min, dz=z_max-z_min,
                    x=x_min, y=y_min, z=z_min, dir=(1, 1, 1),
                    fillet=fillet, fillet_dir=(0, 0, 1))
    return bound_part

def _add_linked_object(obj, obj_name, obj_class, pos_offset=(0, 0, 0), rot_offset=(0, 0, 0), **args):
    new_obj = App.ActiveDocument.addObject(obj_class.type, obj_name)
    new_obj.addProperty("App::PropertyLinkHidden","Baseplate").Baseplate = obj.Baseplate
    new_obj.Label = obj_name
    obj_class(new_obj, **args)
    new_obj.setEditorMode('Placement', 2)
    new_obj.addProperty("App::PropertyPlacement","BasePlacement")
    if not hasattr(obj, "ChildObjects"):
        obj.addProperty("App::PropertyLinkListChild","ChildObjects")
    obj.ChildObjects += [new_obj]
    new_obj.addProperty("App::PropertyLinkHidden","ParentObject").ParentObject = obj
    new_obj.addProperty("App::PropertyPlacement","RelativePlacement").RelativePlacement
    rotx = App.Rotation(App.Vector(1,0,0), rot_offset[0])
    roty = App.Rotation(App.Vector(0,1,0), rot_offset[1])
    rotz = App.Rotation(App.Vector(0,0,1), rot_offset[2])
    new_obj.RelativePlacement.Rotation = App.Rotation(rotz*roty*rotx)
    new_obj.RelativePlacement.Base = App.Vector(*pos_offset)
    return new_obj

def _drill_part(part, obj, drill_obj):
    if hasattr(drill_obj, "DrillPart"):
        drill = drill_obj.DrillPart.copy()
        drill.Placement = obj.BasePlacement.inverse().multiply(drill.Placement)
        part = part.cut(drill)
    if hasattr(drill_obj, "ChildObjects"):
        for sub in drill_obj.ChildObjects:
            part = _drill_part(part, obj, sub)
    return part

def _custom_box(dx, dy, dz, x, y, z, fillet=0, dir=(0,0,1), fillet_dir=None):
    if fillet_dir == None:
        fillet_dir = np.abs(dir)
    part = Part.makeBox(dx, dy, dz)
    if fillet != 0:
        for i in part.Edges:
            if i.tangentAt(i.FirstParameter) == App.Vector(*fillet_dir):
                part = part.makeFillet(fillet-1e-3, [i])
    part.translate(App.Vector(x-(1-dir[0])*dx/2, y-(1-dir[1])*dy/2, z-(1-dir[2])*dz/2))
    part = part.fuse(part)
    return part

def _fillet_all(part, fillet, dir=(0, 0, 1)):
    for i in part.Edges:
        if i.tangentAt(i.FirstParameter) == App.Vector(*dir):
            try:
                part = part.makeFillet(fillet-1e-3, [i])
            except:
                pass
    return part

def _custom_cylinder(dia, dz, x, y, z, head_dia=0, head_dz=0, dir=(0, 0, -1), countersink=False):
    part = Part.makeCylinder(dia/2, dz, App.Vector(0, 0, 0), App.Vector(*dir))
    if head_dia != 0 and head_dz != 0:
        if countersink:
            part = part.fuse(Part.makeCone(head_dia/2, dia/2, head_dz, App.Vector(0, 0, 0), App.Vector(*dir)))
        else:
            part = part.fuse(Part.makeCylinder(head_dia/2, head_dz, App.Vector(0, 0, 0), App.Vector(*dir)))
    part.translate(App.Vector(x, y, z))
    part = part.fuse(part)
    return part.removeSplitter()


class example_component:
    '''
    An example component class for reference on importing new components
    creates a simple cube which mounts using a single bolt

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        side_length (float) : The side length of the cube
    '''
    type = 'Part::FeaturePython' # if importing from stl, this will be 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, side_len=15):
        # required for all object classes
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        # define any user-accessible properties here
        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'Side_Length').Side_Length = side_len

        # additional parameters (ie color, constants, etc)
        obj.ViewObject.ShapeColor = adapter_color
        self.mount_bolt = bolt_8_32
        self.mount_dz = -obj.Baseplate.OpticsDz.Value

    # this defines the component body and drilling
    def execute(self, obj):
        part = _custom_box(dx=obj.Side_Length.Value, dy=obj.Side_Length.Value, dz=obj.Side_Length.Value,
                           x=0, y=0, z=self.mount_dz)
        part = part.cut(_custom_cylinder(dia=self.mount_bolt['clear_dia'], dz=obj.Side_Length.Value,
                                         head_dia=self.mount_bolt['head_dia'], head_dz=self.mount_bolt['head_dz'],
                                         x=0, y=0, z=obj.Side_Length.Value+self.mount_dz))
        obj.Shape = part

        # drilling part definition
        part = _custom_cylinder(dia=self.mount_bolt['tap_dia'], dz=drill_depth,
                                x=0, y=0, z=self.mount_dz)
        part.Placement = obj.Placement
        obj.DrillPart = part



class baseplate_mount:
    '''
    Mount holes for attaching to an optical table
    Uses 14_20 bolts with washers

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        bore_depth (float) : The depth for the counterbore of the mount hole
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, bore_depth=10, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'BoreDepth').BoreDepth = bore_depth
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color

    def execute(self, obj):
        bolt_len = inch-(obj.BoreDepth.Value-bolt_14_20['head_dz'])

        part = _custom_cylinder(dia=bolt_14_20['tap_dia'], dz=bolt_len,
                                head_dia=bolt_14_20['head_dia'], head_dz=bolt_14_20['head_dz'],
                                x=0, y=0, z=-inch*3/2+bolt_len)
        obj.Shape = part

        part = _custom_cylinder(dia=bolt_14_20['clear_dia'], dz=drill_depth,
                                head_dia=bolt_14_20["washer_dia"], head_dz=obj.BoreDepth.Value,
                                x=0, y=0, z=-obj.Baseplate.OpticsDz.Value)
        part.Placement = obj.Placement
        obj.DrillPart = part


class surface_adapter:
    '''
    Surface adapter for post-mounted parts

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        mount_hole_dy (float) : The spacing between the two mount holes of the adapter
        adapter_height (float) : The height of the suface adapter
        outer_thickness (float) : The thickness of the walls around the bolt holes
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, mount_hole_dy=20, adapter_height=8, outer_thickness=2):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'MountHoleDistance').MountHoleDistance = mount_hole_dy
        obj.addProperty('App::PropertyLength', 'AdapterHeight').AdapterHeight = adapter_height
        obj.addProperty('App::PropertyLength', 'OuterThickness').OuterThickness = outer_thickness
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = adapter_color
        obj.setEditorMode('Placement', 2)
        self.drill_tolerance = 1

    def execute(self, obj):
        dx = bolt_8_32['head_dia']+obj.OuterThickness.Value*2
        dy = dx+obj.MountHoleDistance.Value
        dz = obj.AdapterHeight.Value

        part = _custom_box(dx=dx, dy=dy, dz=dz,
                           x=0, y=0, z=0, dir=(0, 0, -1),
                           fillet=5)
        part = part.cut(_custom_cylinder(dia=bolt_8_32['clear_dia'], dz=dz,
                                         head_dia=bolt_8_32['head_dia'], head_dz=bolt_8_32['head_dz'],
                                         x=0, y=0, z=-dz, dir=(0,0,1)))
        for i in [-1, 1]:
            part = part.cut(_custom_cylinder(dia=bolt_8_32['clear_dia'], dz=dz,
                                             head_dia=bolt_8_32['head_dia'], head_dz=bolt_8_32['head_dz'],
                                             x=0, y=i*obj.MountHoleDistance.Value/2, z=0))
        obj.Shape = part

        part = _bounding_box(obj, self.drill_tolerance, 6)
        for i in [-1, 1]:
            part = part.fuse(_custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                              x=0, y=i*obj.MountHoleDistance.Value/2, z=0))
        part.Placement = obj.Placement
        obj.DrillPart = part
        

class skate_mount:
    '''
    Skate mount for splitter cubes

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        cube_size (float) : The side length of the splitter cube
        mount_hole_dy (float) : The spacing between the two mount holes of the adapter
        cube_depth (float) : The depth of the recess for the cube
        outer_thickness (float) : The thickness of the walls around the bolt holes
        cube_tol (float) : The tolerance for size of the recess in the skate mount
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, cube_size=10, mount_hole_dy=20, cube_depth=1, outer_thickness=2, cube_tol=0.1):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'CubeSize').CubeSize = cube_size
        obj.addProperty('App::PropertyLength', 'MountHoleDistance').MountHoleDistance = mount_hole_dy
        obj.addProperty('App::PropertyLength', 'CubeDepth').CubeDepth = cube_depth+1e-3
        obj.addProperty('App::PropertyLength', 'OuterThickness').OuterThickness = outer_thickness
        obj.addProperty('App::PropertyLength', 'CubeTolerance').CubeTolerance = cube_tol
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = adapter_color
        obj.setEditorMode('Placement', 2)

    def execute(self, obj):
        dx = bolt_8_32['head_dia']+obj.OuterThickness.Value*2
        dy = dx+obj.MountHoleDistance.Value
        dz = obj.Baseplate.OpticsDz.Value-obj.CubeSize.Value/2+obj.CubeDepth.Value
        cut_dx = obj.CubeSize.Value+obj.CubeTolerance.Value

        part = _custom_box(dx=dx, dy=dy, dz=dz,
                           x=0, y=0, z=-obj.Baseplate.OpticsDz.Value, fillet=5)
        part = part.cut(_custom_box(dx=cut_dx, dy=cut_dx, dz=obj.CubeDepth.Value+1e-3,
                                    x=0, y=0, z=-obj.CubeSize.Value/2-1e-3))
        for i in [-1, 1]:
            part = part.cut(_custom_cylinder(dia=bolt_8_32['clear_dia'], dz=dz,
                                             head_dia=bolt_8_32['head_dia'], head_dz=bolt_8_32['head_dz'],
                                             x=0, y=i*obj.MountHoleDistance.Value/2, z=-obj.Baseplate.OpticsDz.Value+dz))
        part.translate(App.Vector(0, 0, obj.CubeSize.Value/2))
        part = part.fuse(part)
        obj.Shape = part

        part = Part.Shape()
        for i in [-1, 1]:
            part = part.fuse(_custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                              x=0, y=i*obj.MountHoleDistance.Value/2, z=-obj.Baseplate.OpticsDz.Value+obj.CubeSize.Value/2))
        part.Placement = obj.Placement
        obj.DrillPart = part


class slide_mount:
    '''
    Slide mount adapter for post-mounted parts

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        slot_length (float) : The length of the slot used for mounting to the baseplate
        drill_offset (float) : The distance to offset the drill hole along the slot
        adapter_height (float) : The height of the suface adapter
        post_thickness (float) : The thickness of the post that mounts to the element
        outer_thickness (float) : The thickness of the walls around the bolt holes
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, slot_length=10, drill_offset=0, adapter_height=8, post_thickness=4, outer_thickness=2):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'SlotLength').SlotLength = slot_length
        obj.addProperty('App::PropertyDistance', 'DrillOffset').DrillOffset = drill_offset
        obj.addProperty('App::PropertyLength', 'AdapterHeight').AdapterHeight = adapter_height
        obj.addProperty('App::PropertyLength', 'PostThickness').PostThickness = post_thickness
        obj.addProperty('App::PropertyLength', 'OuterThickness').OuterThickness = outer_thickness
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')
        
        obj.ViewObject.ShapeColor = adapter_color
        obj.setEditorMode('Placement', 2)

    def execute(self, obj):
        dx = bolt_8_32['head_dia']+obj.OuterThickness.Value*2
        dy = dx+obj.SlotLength.Value+obj.PostThickness.Value
        dz = obj.AdapterHeight.Value

        part = _custom_box(dx=dx, dy=dy, dz=dz,
                           x=0, y=-dy/2, z=-obj.Baseplate.OpticsDz.Value, fillet=4)
        part = part.cut(_custom_box(dx=bolt_8_32['clear_dia'], dy=obj.SlotLength.Value+bolt_8_32['clear_dia'], dz=dz,
                                    x=0, y=-dy/2-obj.PostThickness.Value/2, z=-obj.Baseplate.OpticsDz.Value, fillet=bolt_8_32['clear_dia']/2))
        part = part.cut(_custom_box(dx=bolt_8_32['head_dia'], dy=obj.SlotLength.Value+bolt_8_32['head_dia'], dz=bolt_8_32['head_dz'],
                                    x=0, y=-dy/2-obj.PostThickness.Value/2, z=-obj.Baseplate.OpticsDz.Value+bolt_8_32['head_dz'], fillet=bolt_8_32['head_dia']/2))
        part = part.fuse(_custom_box(dx=dx, dy=obj.PostThickness.Value, dz=obj.Baseplate.OpticsDz.Value+bolt_8_32['head_dz'],
                                     x=0, y=-obj.PostThickness.Value/2, z=-obj.Baseplate.OpticsDz.Value))
        part = part.cut(_custom_cylinder(dia=bolt_8_32['clear_dia'], dz=obj.PostThickness.Value,
                                    x=0, y=0, z=0, dir=(0, -1, 0)))
        obj.Shape = part

        part = _custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                x=0, y=-dy/2-obj.PostThickness.Value/2+obj.DrillOffset.Value, z=-obj.Baseplate.OpticsDz.Value)
        part.Placement = obj.Placement
        obj.DrillPart = part


class fiberport_mount_hca3:
    '''
    Part for mounting an HCA3 fiberport coupler to the side of a baseplate

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['HCA3', 'PAF2-5A']
        self.max_angle = 0
        self.max_width = 1

    def execute(self, obj):
        mesh = _import_stl("HCA3-Step.stl", (90, -0, 90), (-6.35, 19.05, -26.87))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = Part.Shape()
        for i in [-1, 0, 1]:
            part = part.fuse(_custom_cylinder(dia=bolt_8_32['tap_dia'], dz=inch,
                                              x=0, y=i*12.7, z=-20.65, dir=(1,0,0)))
        part.Placement = obj.Placement
        obj.DrillPart = part


class rotation_stage_rsp05:
    '''
    Rotation stage, model RSP05

    Args:
        invert (bool) : Whether the mount should be offset 90 degrees from the component
        mount_hole_dy (float) : The spacing between the two mount holes of it's adapter
        wave_plate_part_num (string) : The Thorlabs part number of the wave plate being used

    Sub-Parts:
        surface_adapter (adapter_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, invert=False, adapter_args=dict()):
        adapter_args.setdefault("mount_hole_dy", 25)
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Invert').Invert = invert

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['RSP05']

        _add_linked_object(obj, "Surface Adapter", surface_adapter, pos_offset=(1.397, 0, -13.97), rot_offset=(0, 0, 90*obj.Invert), **adapter_args)

    def execute(self, obj):
        mesh = _import_stl("RSP05-Step.stl", (90, -0, 90), (2.032, -0, 0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh


class mirror_mount_k05s2:
    '''
    Mirror mount, model K05S2

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        mirror (bool) : Whether to add a mirror component to the mount
        thumbscrews (bool): Whether or not to add two HKTS 5-64 adjusters
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, thumbscrews=False):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyBool', 'ThumbScrews').ThumbScrews = thumbscrews
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['POLARIS-K05S2']

        if thumbscrews:
            _add_linked_object(obj, "Upper Thumbscrew", thumbscrew_hkts_5_64, pos_offset=(-15.03, 8.89, 8.89))
            _add_linked_object(obj, "Lower Thumbscrew", thumbscrew_hkts_5_64, pos_offset=(-15.03, -8.89, -8.89))

    def execute(self, obj):
        mesh = _import_stl("POLARIS-K05S2-Step.stl", (90, -0, -90), (-4.514, 0.254, -0.254))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                x=-8.017, y=0, z=-layout.inch/2)
        for i in [-1, 1]:
            part = part.fuse(_custom_cylinder(dia=2, dz=2.2,
                                              x=-8.017, y=i*5, z=-layout.inch/2))
        part.Placement = obj.Placement
        obj.DrillPart = part


class mirror_mount_k05s1:
    '''
    Mirror mount, model K05S1

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        mirror (bool) : Whether to add a mirror component to the mount
        thumbscrews (bool): Whether or not to add two HKTS 5-64 adjusters
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, thumbscrews=False):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyBool', 'ThumbScrews').ThumbScrews = thumbscrews
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['POLARIS-K05S1']

        if thumbscrews:
            _add_linked_object(obj, "Upper Thumbscrew", thumbscrew_hkts_5_64, pos_offset=(-11.22, 8.89, 8.89))
            _add_linked_object(obj, "Lower Thumbscrew", thumbscrew_hkts_5_64, pos_offset=(-11.22, -8.89, -8.89))

    def execute(self, obj):
        mesh = _import_stl("POLARIS-K05S1-Step.stl", (90, 0, -90), (-4.514, 0.254, -0.254))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                x=-8.017, y=0, z=-layout.inch/2)
        for i in [-1, 1]:
            part = part.fuse(_custom_cylinder(dia=2, dz=2.2,
                                              x=-8.017, y=i*5, z=-layout.inch/2))
        part.Placement = obj.Placement
        obj.DrillPart = part


class splitter_mount_b05g:
    '''
    Splitter mount, model B05G

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        splitter (bool) : Whether to add a splitter plate component to the mount

    Sub-Parts:
        circular_splitter (mirror_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['POLARIS-B05G']

    def execute(self, obj):
        mesh = _import_stl("POLARIS-B05G-Step.stl", (90, -0, 90), (-17.54, -5.313, -19.26))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                x=-5, y=0, z=-layout.inch/2)
        for i in [-1, 1]:
            part = part.fuse(_custom_cylinder(dia=2, dz=2.2,
                                              x=-5, y=i*5, z=-layout.inch/2))
        part.Placement = obj.Placement
        obj.DrillPart = part


class mirror_mount_c05g:
    '''
    Mirror mount, model C05G

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        mirror (bool) : Whether to add a mirror component to the mount

    Sub-Parts:
        circular_mirror (mirror_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['POLARIS-C05G']

    def execute(self, obj):
        mesh = _import_stl("POLARIS-C05G-Step.stl", (90, -0, 90), (-18.94, -4.246, -15.2))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                x=-6.35, y=0, z=-layout.inch/2)
        for i in [-1, 1]:
            part = part.fuse(_custom_cylinder(dia=2, dz=2.2,
                                              x=-6.35, y=i*5, z=-layout.inch/2))
        part.Placement = obj.Placement
        obj.DrillPart = part


class mirror_mount_km05:
    '''
    Mirror mount, model KM05

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        mirror (bool) : Whether to add a mirror component to the mount
        thumbscrews (bool): Whether or not to add two HKTS 5-64 adjusters
        bolt_length (float) : The length of the bolt used for mounting

    Sub-Parts:
        circular_mirror (mirror_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, thumbscrews=False, bolt_length=15):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyBool', 'ThumbScrews').ThumbScrews = thumbscrews
        obj.addProperty('App::PropertyLength', 'BoltLength').BoltLength = bolt_length
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['KM05']

        if thumbscrews:
            _add_linked_object(obj, "Upper Thumbscrew", thumbscrew_hkts_5_64, pos_offset=(-10.54, 9.906, 9.906))
            _add_linked_object(obj, "Lower Thumbscrew", thumbscrew_hkts_5_64, pos_offset=(-10.54, -9.906, -9.906))

    def execute(self, obj):
        mesh = _import_stl("KM05-Step.stl", (90, -0, 90), (2.084, -1.148, 0.498))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 2, 3, min_offset=(4.35, 0, 0))
        part = part.fuse(_bounding_box(obj, 2, 3, max_offset=(0, -20, 0)))
        part = _fillet_all(part, 3)
        part = part.fuse(_custom_cylinder(dia=bolt_8_32['clear_dia'], dz=inch,
                                          head_dia=bolt_8_32['head_dia'], head_dz=0.92*inch-obj.BoltLength.Value,
                                          x=-7.29, y=0, z=-inch*3/2, dir=(0,0,1)))
        part.Placement = obj.Placement
        obj.DrillPart = part


class prism_mount_km05pm:
    '''
    Mount, model KM05PM

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, thumbscrews=False, bolt_length=15):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyBool', 'ThumbScrews').ThumbScrews = thumbscrews
        obj.addProperty('App::PropertyLength', 'BoltLength').BoltLength = bolt_length
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['KM05PM']

        if thumbscrews:
            _add_linked_object(obj, "Upper Thumbscrew", thumbscrew_hkts_5_64, pos_offset=(-19.05, 6.985, 15.49))
            _add_linked_object(obj, "Lower Thumbscrew", thumbscrew_hkts_5_64, pos_offset=(-19.05, -12.83, -4.318))

    def execute(self, obj):
        #mesh = _import_stl("KM05PM-Step.stl", (90, 0, 90), (-12.39, -0.894, 1.514))
        mesh = _import_stl("KM05PM-Step-No-Plate.stl", (90, -0, 90), (-6.425, -4.069, 6.086))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 3, 3, min_offset=(4.35, 0, 0))
        part = part.fuse(_bounding_box(obj, 3, 3, max_offset=(0, -20, 0)))
        part = part.fuse(_bounding_box(obj, 3, 3, min_offset=(14, 0, 0), z_tol=True))
        part = _fillet_all(part, 3)
        part = part.fuse(_custom_cylinder(dia=bolt_8_32['clear_dia'], dz=drill_depth,
                                          head_dia=bolt_8_32['head_dia'], head_dz=drill_depth-obj.BoltLength.Value,
                                          x=-15.8, y=-2.921, z=-9.144-drill_depth, dir=(0,0,1)))
        part.Placement = obj.Placement
        obj.DrillPart = part


class grating_mount_on_km05pm:
    '''
    Grating and Parallel Mirror Mounted on MK05PM

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        littrow_angle (float) : The angle of the grating and parallel mirror

    Sub_Parts:
        mount_mk05pm (mount_args)
        square_grating (grating_args)
        square_mirror (mirror_args)
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, littrow_angle=55, mount_args=dict(), grating_args=dict(), mirror_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyAngle', 'LittrowAngle').LittrowAngle = littrow_angle

        obj.ViewObject.ShapeColor = adapter_color
        self.dx = 12/tan(radians(2*obj.LittrowAngle))

        gap = 10
        lit_angle = radians(90-obj.LittrowAngle.Value)
        beam_angle = radians(obj.LittrowAngle.Value)
        ref_len = gap/sin(2*beam_angle)
        ref_x = ref_len*cos(2*beam_angle)
        dx = ref_x+12.7*cos(lit_angle)+(6+3.2)*sin(lit_angle)
        extra_x = 20-dx
        grating_dx = -(6*sin(lit_angle)+12.7/2*cos(lit_angle))-extra_x
        mirror_dx = grating_dx-ref_x

        _add_linked_object(obj, "Mount MK05PM", prism_mount_km05pm, pos_offset=(-3.175, 8, -10), rot_offset=(0, 0, 180), **mount_args)
        _add_linked_object(obj, "Grating", square_grating, pos_offset=(grating_dx, 0, 0), rot_offset=(0, 0, 180-obj.LittrowAngle.Value), **grating_args)
        _add_linked_object(obj, "Mirror", square_mirror, pos_offset=(mirror_dx, gap, 0), rot_offset=(0, 0, -obj.LittrowAngle.Value), **mirror_args)

    def execute(self, obj):
        extra_y = 2
        gap = 10
        lit_angle = radians(90-obj.LittrowAngle.Value)
        beam_angle = radians(obj.LittrowAngle.Value)
        ref_len = gap/sin(2*beam_angle)
        ref_x = ref_len*cos(2*beam_angle)
        dx = ref_x+12.7*cos(lit_angle)+(6+3.2)*sin(lit_angle)
        extra_x = 20-dx
        dy = gap+12.7*sin(lit_angle)+(6+3.2)*cos(lit_angle)
        dz = inch/2
        cut_x = 12.7*cos(lit_angle)

        part = _custom_box(dx=dx+extra_x, dy=dy+extra_y, dz=dz,
                           x=extra_x, y=0, z=-10, dir=(-1, 1, 1))
        temp = _custom_box(dx=ref_len*cos(beam_angle)+6+3.2, dy=dy/sin(lit_angle)+10, dz=dz,
                           x=-cut_x, y=-(dx-cut_x)*cos(lit_angle), z=-6, dir=(-1, 1, 1))
        temp.rotate(App.Vector(-cut_x, 0, 0), App.Vector(0, 0, 1), -obj.LittrowAngle.Value)
        part = part.cut(temp)
        part = part.cut(_custom_box(dx=8, dy=16, dz=dz-4,
                           x=extra_x, y=dy+extra_y, z=-6, dir=(-1, -1, 1)))
        part.translate(App.Vector(-extra_x, -12.7/2*sin(lit_angle)-6*cos(lit_angle), 0))
        part = part.fuse(part)
        part = part.cut(_custom_cylinder(dia=bolt_4_40['clear_dia'], dz=4,
                                         head_dia=bolt_4_40['head_dia'], head_dz=2,
                                         x=-3.175, y=8, z=-6, dir=(0, 0, -1)))
        part = part.cut(_custom_cylinder(dia=bolt_4_40['clear_dia'], dz=4,
                                         head_dia=bolt_4_40['head_dia'], head_dz=2,
                                         x=-3.175, y=8+2*3.175, z=-6, dir=(0, 0, -1)))
        obj.Shape = part


class mount_tsd_405sluu:
    '''
    Mount, model KM05PM

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['TSD-405SLUU']

    def execute(self, obj):
        mesh = _import_stl("TSD-405SLUU.stl", (0, 0, -90), (-19, 0, -62))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 3, 3)
        for x, y in [(-34.88, 15.88), (-34.88, -15.88), (-3.125, 15.88), (-3.125, -15.88)]:
            part = part.fuse(_custom_cylinder(dia=bolt_4_40['tap_dia'], dz=drill_depth,
                                            x=x, y=y, z=-62))
        part.Placement = obj.Placement
        obj.DrillPart = part


class mirror_mount_ks1t:
    '''
    Mirror mount, model KS1T

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        mirror (bool) : Whether to add a mirror component to the mount

    Sub-Parts:
        circular_mirror (mirror_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['KM1T']

    def execute(self, obj):
        mesh = _import_stl("KS1T-Step.stl", (90, -0, -90), (22.06, 13.37, -30.35))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        dz = -inch-obj.Mesh.BoundBox.ZMin
        part = _bounding_box(obj, 3, 3, min_offset=(0, 0, dz))
        part = part.fuse(_bounding_box(obj, 3, 3, z_tol=True, max_offset=(-28, 0, 0)))
        part = part.fuse(_custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                          x=-16.94, y=0, z=-layout.inch/2, dir=(0,0,-1)))
        part.Placement = obj.Placement
        obj.DrillPart = part


class fiberport_mount_km05:
    '''
    Mirror mount, model KM05, adapted to use as fiberport mount

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled

    Sub-Parts:
        mirror_mount_km05 (mount_args)
        fiber_adapter_sm05fca2
        lens_tube_sm05l05
        lens_adapter_s05tm09
        mounted_lens_c220tmda
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, mount_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill

        obj.ViewObject.ShapeColor = misc_color

        _add_linked_object(obj, "Mount", mirror_mount_km05, pos_offset=(0, 0, 0), **mount_args)
        _add_linked_object(obj, "Fiber Adapter", fiber_adapter_sm05fca2, pos_offset=(1.524, 0, 0))
        _add_linked_object(obj, "Lens Tube", lens_tube_sm05l05, pos_offset=(1.524+3.812, 0, 0))
        _add_linked_object(obj, "Lens Adapter", lens_adapter_s05tm09, pos_offset=(1.524+5, 0, 0))
        _add_linked_object(obj, "Lens", mounted_lens_c220tmda, pos_offset=(1.524+3.167+5, 0, 0))


class fiberport_mount_ks1t:
    '''
    Mirror mount, model KM05, adapted to use as fiberport mount

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled

    Sub-Parts:
        mirror_mount_km05 (mount_args)
        fiber_adapter_sm05fca2
        lens_tube_sm05l05
        lens_adapter_s05tm09
        mounted_lens_c220tmda
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, mount_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill

        obj.ViewObject.ShapeColor = misc_color

        _add_linked_object(obj, "Mount", mirror_mount_ks1t, pos_offset=(0, 0, 0), **mount_args)
        _add_linked_object(obj, "Fiber Adapter", fiber_adapter_sm1fca2, pos_offset=(-3, 0, 0))
        _add_linked_object(obj, "Lens Tube", lens_tube_sm1l05, pos_offset=(0, 0, 0))
        _add_linked_object(obj, "Lens Adapter", lens_adapter_s1tm09, pos_offset=(1.524+6, 0, 0))
        _add_linked_object(obj, "Lens", mounted_lens_c220tmda, pos_offset=(1.524+2, 0, 0))


class km05_50mm_laser:
    '''
    Mirror mount, model KM05, adapted to use as laser mount

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        tec_thickness (float) : The thickness of the TEC used

    Sub-Parts:
        mirror_mount_km05 (mount_args)
        km05_tec_upper_plate (upper_plate_args)
        km05_tec_lower_plate (lower_plate_args)
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, tec_thickness=4, mount_args=dict(), upper_plate_args=dict(), lower_plate_args=dict()):
        mount_args.setdefault("bolt_length", 2)
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'TecThickness').TecThickness = tec_thickness
        obj.ViewObject.ShapeColor = misc_color
        
        self.part_numbers = [] # TODO add part numbers
        self.max_angle = 0
        self.max_width = 1

        dx = -5.334+2.032
        _add_linked_object(obj, "Diode Adapter", diode_adapter_s05lm56, pos_offset=(0, 0, 0))
        _add_linked_object(obj, "Lens Tube", lens_tube_sm05l05, pos_offset=(dx+1.524+3.812, 0, 0))
        _add_linked_object(obj, "Lens Adapter", lens_adapter_s05tm09, pos_offset=(dx+1.524+5, 0, 0))
        _add_linked_object(obj, "Lens", mounted_lens_c220tmda, pos_offset=(dx+1.524+3.167+5, 0, 0))

        mount = _add_linked_object(obj, "Mount", mirror_mount_km05, pos_offset=(dx, 0, 0), drill=False, **mount_args)
        upper_plate = _add_linked_object(obj, "Upper Plate", km05_tec_upper_plate, pos_offset=(dx-4, 0, -0.08*inch), drill_obj=mount, **upper_plate_args)
        _add_linked_object(obj, "Lower Plate", km05_tec_lower_plate, pos_offset=(dx-4, 0, -0.08*inch-tec_thickness-upper_plate.Thickness.Value), **lower_plate_args)


class km05_tec_upper_plate:
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill_obj, width=inch, thickness=0.25*inch):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyLength', 'Width').Width = width
        obj.addProperty('App::PropertyLength', 'Thickness').Thickness = thickness
        obj.addProperty('App::PropertyLinkHidden', 'DrillObject').DrillObject = drill_obj

        obj.ViewObject.ShapeColor = adapter_color

    def execute(self, obj):
        part = _custom_box(dx=obj.Width.Value, dy=obj.Width.Value, dz=obj.Thickness.Value,
                           x=0, y=0, z=-inch/2, dir=(0, 0, -1))
        part = _drill_part(part, obj, obj.DrillObject)
        obj.Shape = part


class km05_tec_lower_plate:
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, width=1.5*inch, thickness=0.25*inch):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'Width').Width = width
        obj.addProperty('App::PropertyLength', 'Thickness').Thickness = thickness
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = adapter_color

    def execute(self, obj):
        part = _custom_box(dx=obj.Width.Value, dy=obj.Width.Value, dz=obj.Thickness.Value,
                                     x=0, y=0, z=-inch/2, dir=(0, 0, -1))
        for x, y in [(1,1), (1,-1), (-1,1), (-1,-1)]:
            part = part.cut(_custom_cylinder(dia=bolt_8_32['clear_dia'], dz=obj.Thickness.Value,
                                        x=(obj.Width.Value/2-4)*x, y=(obj.Width.Value/2-4)*y, z=-inch/2, dir=(0, 0, -1)))
        obj.Shape = part

        part = _bounding_box(obj, 3, 3)
        for x, y in [(1,1), (1,-1), (-1,1), (-1,-1)]:
            part = part.fuse(_custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                              x=(obj.Width.Value/2-4)*x, y=(obj.Width.Value/2-4)*y, z=0, dir=(0, 0, -1)))
        part = part.fuse(_custom_box(dx=20, dy=5, dz=inch/2,
                                     x=part.BoundBox.XMin, y=(part.BoundBox.YMax+part.BoundBox.YMin)/2, z=0,
                                     dir=(-1, 0, -1)))
        part.Placement = obj.Placement
        obj.DrillPart = part


class mirror_mount_mk05:
    '''
    Mirror mount, model MK05

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled

    Sub-Parts:
        circular_mirror (mirror_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['MK05']
        self.reflection_angle = 0
        self.max_angle = 90
        self.max_width = inch/2

    def execute(self, obj):
        mesh = _import_stl("MK05-Step.stl", (90, -0, -90), (-22.91-obj.ChildObjects[0].Thickness.Value, 26, -5.629))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _custom_cylinder(dia=bolt_4_40['tap_dia'], dz=drill_depth,
                           head_dia=bolt_4_40['head_dia'], head_dz=drill_depth-10,
                           x=-5.562, y=0, z=-10.2-drill_depth, dir=(0, 0, 1))
        part.Placement = obj.Placement
        obj.DrillPart = part


class mount_mk05pm:
    '''
    Mount, model MK05PM

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['MK05PM']

    def execute(self, obj):
        mesh = _import_stl("MK05PM-Step.stl", (180, 90, 0), (-7.675, 7.699, 4.493))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 2, 2)
        part = part.cut(_custom_box(dx=4, dy=15, dz=-layout.inch/2-obj.Mesh.BoundBox.ZMin,
                                    x=part.BoundBox.XMin, y=part.BoundBox.YMax, z=part.BoundBox.ZMin,
                                    dir=(1, -1, 1), fillet=2))
        part = _fillet_all(part, 2)
        part = part.fuse(_custom_cylinder(dia=bolt_4_40['tap_dia'], dz=drill_depth,
                           head_dia=bolt_4_40['head_dia'], head_dz=drill_depth-5,
                           x=-7.675, y=7.699, z=4.493-10.2-drill_depth, dir=(0,0,1)))
        part.Placement = obj.Placement
        obj.DrillPart = part


#Nishat Edited : Imported this part
class dichoric_mirror_mount_km05fl:
    '''
    Mirror mount, model MK05

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled

    Sub-Parts:
        circular_mirror (mirror_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['KM05fl']
        self.reflection_angle = 0
        self.max_angle = 90
        self.max_width = inch/2

    def execute(self, obj):
        mesh = _import_stl("KM05FL-Step.stl", (-180, 0, -90), (-11.53, -10.16, -10.16))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 2, 2)
        part = part.cut(_custom_box(dx=4, dy=15, dz=-layout.inch/2-obj.Mesh.BoundBox.ZMin,
                                    x=part.BoundBox.XMin, y=part.BoundBox.YMax, z=part.BoundBox.ZMin,
                                    dir=(1, -1, 1), fillet=2))
        part = _fillet_all(part, 2)

        part = part.fuse(_custom_cylinder(dia=bolt_4_40['tap_dia'], dz=drill_depth,
                           head_dia=bolt_4_40['head_dia'], head_dz=drill_depth-10,
                           x=7.378, y=7.378, z=-4.373-drill_depth, dir=(0, 0, 1)))
        part.Placement = obj.Placement
        obj.DrillPart = part


#Nishat Edited : Imported this part
class dichoric_mirror_mount_km05fR:
    '''
    Mirror mount, model KM05FR

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled

    Sub-Parts:
        circular_mirror (mirror_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['KM05fR']
        self.reflection_angle = 0
        self.max_angle = 90
        self.max_width = inch/2

    def execute(self, obj):
        mesh = _import_stl("KM05FR_M-Step.stl", (-90, 0, 0), (-11.53, -10.16, -10.16))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 2, 2)
        part = part.cut(_custom_box(dx=4, dy=15, dz=-layout.inch/2-obj.Mesh.BoundBox.ZMin,
                                    x=part.BoundBox.XMin, y=part.BoundBox.YMax, z=part.BoundBox.ZMin,
                                    dir=(1, -1, 1), fillet=2))
        part = _fillet_all(part, 2)
        part = part.fuse(_custom_cylinder(dia=bolt_4_40['tap_dia'], dz=drill_depth,
                           head_dia=bolt_4_40['head_dia'], head_dz=drill_depth-5,
                           x=-11.53, y=14.53, z=.275-drill_depth, dir=(0,0,1)))
        part.Placement = obj.Placement
        obj.DrillPart = part


class grating_mount_on_mk05pm:
    '''
    Grating and Parallel Mirror Mounted on MK05PM

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        littrow_angle (float) : The angle of the grating and parallel mirror

    Sub_Parts:
        mount_mk05pm (mount_args)
        square_grating (grating_args)
        square_mirror (mirror_args)
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, littrow_angle=45, mount_args=dict(), grating_args=dict(), mirror_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyAngle', 'LittrowAngle').LittrowAngle = littrow_angle

        obj.ViewObject.ShapeColor = adapter_color
        self.dx = 12/tan(radians(2*obj.LittrowAngle))

        _add_linked_object(obj, "Mount MK05PM", mount_mk05pm, pos_offset=(-12, -4, -4-12.7/2+2), **mount_args)
        _add_linked_object(obj, "Grating", square_grating, pos_offset=(0, 0, 2), rot_offset=(0, 0, -obj.LittrowAngle.Value), **grating_args)
        _add_linked_object(obj, "Mirror", square_mirror, pos_offset=(self.dx, -12, 2), rot_offset=(0, 0, -obj.LittrowAngle.Value+180), **mirror_args)

    def execute(self, obj):
        # TODO add some variables to make this cleaner
        part = _custom_box(dx=25+self.dx, dy=35, dz=4,
                           x=-3.048, y=17.91, z=0, dir=(1, -1, 1))
        
        part = part.cut(_custom_box(dx=6, dy=8.1, dz=4,
                                    x=-3.048, y=17.91, z=0, dir=(1, -1, 1)))
        part = part.cut(_custom_cylinder(dia=bolt_4_40['clear_dia'], dz=4,
                                    x=0, y=0, z=0, dir=(0, 0, 1)))
        part = part.cut(_custom_cylinder(dia=bolt_4_40['clear_dia'], dz=4,
                                    x=13.34, y=15.62, z=0, dir=(0, 0, 1)))
        part.translate(App.Vector(-12, -4, -4))

        temp = _custom_box(dx=4, dy=12, dz=12,
                           x=-6, y=0, z=0, dir=(-1, 0, 1))
        temp.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), -obj.LittrowAngle.Value)
        part = part.fuse(temp)
        temp = _custom_box(dx=4, dy=12, dz=12,
                           x=self.dx+3.2, y=-12, z=0, dir=(1, 0, 1))
        temp.rotate(App.Vector(self.dx, -12, 0), App.Vector(0, 0, 1), -obj.LittrowAngle.Value)
        part = part.fuse(temp)
        part.translate(App.Vector(0, 0, -12.7/2+2))
        part = part.fuse(part)
        obj.Shape = part


class lens_holder_l05g:
    '''
    Lens Holder, Model L05G

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled

    Sub-Parts:
        circular_lens (lens_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['POLARIS-L05G']

    def execute(self, obj):
        mesh = _import_stl("POLARIS-L05G-Step.stl", (90, -0, 90), (-26.57, -13.29, -18.44))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                x=-8, y=0, z=-layout.inch/2)
        for i in [-1, 1]:
            part = part.fuse(_custom_box(dx=5, dy=2, dz=2.2,
                                         x=-8, y=i*5, z=-layout.inch/2,
                                         fillet=1, dir=(0, 0, -1)))
        part.Placement = obj.Placement
        obj.DrillPart = part


class pinhole_ida12:
    '''
    Pinhole Iris, Model IDA12

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled

    Sub-Parts:
        slide_mount (adapter_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, adapter_args=dict()):
        adapter_args.setdefault("slot_length", 10)
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['IDA12-P5']
        self.transmission = True
        self.max_angle = 90
        self.max_width = 1
        self.block_width=inch/2
        self.slot_length=adapter_args['slot_length']

        _add_linked_object(obj, "Slide Mount", slide_mount,
                           pos_offset=(1.956, -12.83, 0), **adapter_args)

    def execute(self, obj):
        mesh = _import_stl("IDA12-P5-Step.stl", (90, 0, -90), (1.549, 0, -0))
        mesh.rotate(-pi/2, 0, 0)
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _custom_box(dx=6.5, dy=15+obj.ChildObjects[0].SlotLength.Value, dz=1,
                           x=1.956, y=0, z=-layout.inch/2,
                           fillet=2, dir=(0,0,-1))
        part.Placement = obj.Placement
        obj.DrillPart = part


class prism_mount_km100pm:
    '''
    Kinematic Prism Mount, Model KM100PM

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['KM100PM']

    def execute(self, obj):
        mesh = _import_stl("KM100PM-Step.stl", (90, -0, -90), (-8.877, 38.1, -6.731))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 3, 4, max_offset=(-18, -38, 0), z_tol=True)
        part = part.fuse(_bounding_box(obj, 3, 4, min_offset=(17, 0, 0.63)))
        part = part.fuse(_custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                     x=-14.02, y=12.63, z=17.5))
        part.Placement = obj.Placement
        obj.DrillPart = part


class mount_for_km100pm:
    '''
    Adapter for mounting isomet AOMs to km100pm kinematic mount

    Args:
        mount_offset (float[3]) : The offset position of where the adapter mounts to the component
        drill (bool) : Whether baseplate mounting for this part should be drilled
        slot_length (float) : The length of the slots used for mounting to the km100pm
        countersink (bool) : Whether to drill a countersink instead of a counterbore for the AOM mount holes
        counter_depth (float) : The depth of the countersink/bores for the AOM mount holes
        arm_thickness (float) : The thickness of the arm the mounts to the km100PM
        arm_clearance (float) : The distance between the bottom of the adapter arm and the bottom of the km100pm
        stage_thickness (float) : The thickness of the stage that mounts to the AOM
        stage_length (float) : The length of the stage that mounts to the AOM
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, slot_length=5, countersink=False, counter_depth=3, arm_thickness=8, arm_clearance=2, stage_thickness=4, stage_length=21):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'SlotLength').SlotLength = slot_length
        obj.addProperty('App::PropertyBool', 'Countersink').Countersink = countersink
        obj.addProperty('App::PropertyLength', 'CounterDepth').CounterDepth = counter_depth
        obj.addProperty('App::PropertyLength', 'ArmThickness').ArmThickness = arm_thickness
        obj.addProperty('App::PropertyLength', 'ArmClearance').ArmClearance = arm_clearance
        obj.addProperty('App::PropertyLength', 'StageThickness').StageThickness = stage_thickness
        obj.addProperty('App::PropertyLength', 'StageLength').StageLength = stage_length
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = adapter_color
        obj.setEditorMode('Placement', 2)

    def execute(self, obj):
        dx = obj.ArmThickness.Value
        dy = 47.5
        dz = 16.92
        stage_dx = obj.StageLength.Value
        stage_dz = obj.StageThickness.Value

        part = _custom_box(dx=dx, dy=dy, dz=dz-obj.ArmClearance.Value,
                           x=0, y=0, z=obj.ArmClearance.Value)
        part = part.fuse(_custom_box(dx=stage_dx, dy=dy, dz=stage_dz,
                                     x=0, y=0, z=dz, dir=(1, 0, -1)))
        for ddy in [15.2, 38.1]:
            part = part.cut(_custom_box(dx=dx, dy=obj.SlotLength.Value+bolt_4_40['clear_dia'], dz=bolt_4_40['clear_dia'],
                                        x=dx/2, y=25.4-ddy, z=6.4,
                                        fillet=bolt_4_40['clear_dia']/2, dir=(-1, 0, 0)))
            part = part.cut(_custom_box(dx=dx/2, dy=obj.SlotLength.Value+bolt_4_40['head_dia'], dz=bolt_4_40['head_dia'],
                                        x=dx/2, y=25.4-ddy, z=6.4,
                                        fillet=bolt_4_40['head_dia']/2, dir=(-1, 0, 0)))
        for ddy in [0, -11.42, -26.65, -38.07]:
            part = part.cut(_custom_cylinder(dia=bolt_4_40['clear_dia'], dz=stage_dz, head_dia=bolt_4_40['head_dia'],
                                        head_dz=obj.CounterDepth.Value, countersink=obj.Countersink,
                                        x=11.25, y=18.9+ddy, z=dz-4, dir=(0,0,1)))
        part.translate(App.Vector(dx/2, 25.4-15.2+obj.SlotLength.Value/2, -6.4))
        part = part.fuse(part)
        obj.Shape = part

        part = _bounding_box(obj, 3, 4, z_tol=True, min_offset=(0, 0, 0.668))
        part.Placement = obj.Placement
        obj.DrillPart = part
        

class isomet_1205c_on_km100pm:
    '''
    Isomet 1205C AOM on KM100PM Mount

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        diffraction_angle (float) : The diffraction angle (in degrees) of the AOM
        forward_direction (integer) : The direction of diffraction on forward pass (1=right, -1=left)
        backward_direction (integer) : The direction of diffraction on backward pass (1=right, -1=left)

    Sub-Parts:
        prism_mount_km100pm (mount_args)
        mount_for_km100pm (adapter_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, diffraction_angle=degrees(0.026), forward_direction=1, backward_direction=1, mount_args=dict(), adapter_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyAngle', 'DiffractionAngle').DiffractionAngle = diffraction_angle
        obj.addProperty('App::PropertyInteger', 'ForwardDirection').ForwardDirection = forward_direction
        obj.addProperty('App::PropertyInteger', 'BackwardDirection').BackwardDirection = backward_direction

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['ISOMET_1205C']
        self.diffraction_angle = diffraction_angle
        self.diffraction_dir = (forward_direction, backward_direction)
        self.transmission = True
        self.max_angle = 10
        self.max_width = 5

        # TODO fix these parts to remove arbitrary translations
        _add_linked_object(obj, "Mount KM100PM", prism_mount_km100pm,
                           pos_offset=(-15.25, -20.15, -17.50), **mount_args)
        _add_linked_object(obj, "Adapter Bracket", mount_for_km100pm,
                           pos_offset=(-15.25, -20.15, -17.50), **adapter_args)

    def execute(self, obj):
        mesh = _import_stl("isomet_1205c.stl", (0, 0, 90), (0, 0, 0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh


class isolator_670:
    '''
    Isolator Optimized for 670nm, Model IOT-5-670-VLP

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled

    Sub-Parts:
        surface_adapter (adapter_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, adapter_args=dict()):
        adapter_args.setdefault("mount_hole_dy", 45)
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['IOT-5-670-VLP']
        self.transmission = True
        self.max_angle = 10
        self.max_width = 5

        _add_linked_object(obj, "Surface Adapter", surface_adapter,
                           pos_offset=(0, 0, -22.1), **adapter_args)

    def execute(self, obj):
        mesh = _import_stl("IOT-5-670-VLP-Step.stl", (90, 0, -90), (-19.05, -0, 0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _custom_box(dx=80, dy=25, dz=5,
                           x=0, y= 0, z=-layout.inch/2,
                           fillet=5, dir=(0, 0, -1))
        part.Placement = obj.Placement
        obj.DrillPart = part


class isolator_405:
    '''
    Isolator Optimized for 405nm, Model IO-3D-405-PBS

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled

    Sub-Parts:
        surface_adapter
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, adapter_args=dict()):
        adapter_args.setdefault("mount_hole_dy", 36)
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['IO-3D-405-PBS']
        self.transmission = True
        self.max_angle = 10
        self.max_width = 5

        _add_linked_object(obj, "Surface Adapter", surface_adapter,
                           pos_offset=(0, 0, -17.15), **adapter_args)

    def execute(self, obj):
        mesh = _import_stl("IO-3D-405-PBS-Step.stl", (90, 0, -90), (-9.461, 0, 0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _custom_box(dx=25, dy=15, dz=drill_depth,
                           x=0, y=0, z=-layout.inch/2,
                           fillet=5, dir=(0, 0, 1))
        part.Placement = obj.Placement
        obj.DrillPart = part


class rb_cell:
    '''
    Rubidium Cell Holder

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = adapter_color
        self.transmission = True
        self.max_angle = 10
        self.max_width = 1

    def execute(self, obj):
        mesh = _import_stl("rb_cell_holder_middle.stl", (0, 0, 0), ([0, 5, 0]))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 6, 3)
        dx = 90
        for x, y in [(1,1), (-1,1), (1,-1), (-1,-1)]:
            part = part.fuse(_custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                         x=x*dx/2, y=y*15.7, z=-layout.inch/2))
        part = part.fuse(_custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                     x=45, y=-15.7, z=-layout.inch/2))
        for x in [1,-1]:
            part = part.fuse(_custom_cylinder(dia=bolt_8_32['tap_dia'], dz=drill_depth,
                                         x=x*dx/2, y=25.7, z=-layout.inch/2))
        part.Placement = obj.Placement
        obj.DrillPart = part


class rb_cell_new:
    '''
    Rubidium Cell Holder

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = adapter_color
        self.transmission = True
        self.max_angle = 10
        self.max_width = 1

    def execute(self, obj):
        cell_dx = 88
        cell_dia = 25
        end_dia = 28
        wall_thickness = 15
        base_dy=4*inch
        dx = cell_dx+wall_thickness*2
        dy = dz = cell_dia+wall_thickness*2
        base = _custom_box(dx=dx, dy=dy, dz=dz/2,
                           x=0, y=0, z=dz/2, dir=(0, 0, -1))
        base = base.fuse(_custom_box(dx=dx, dy=base_dy, dz=3/4*inch,
                           x=0, y=0, z=-(1/2*inch-dz/2), dir=(0, 0, -1)))
        cover = _custom_box(dx=dx, dy=dy, dz=dz/2,
                           x=0, y=0, z=dz/2, dir=(0, 0, 1))
        cover = cover.cut(_custom_box(dx=20, dy=dy/2, dz=5,
                           x=0, y=0, z=dz/2+2.5, dir=(0, -1, 0)))
        cell = _custom_cylinder(dia=cell_dia, dz=cell_dx,
                                x=-cell_dx/2, y=0, z=dz/2,
                                dir=(1, 0, 0))
        cell = cell.fuse(_custom_cylinder(dia=end_dia, dz=10,
                                          x=-cell_dx/2, y=0, z=dz/2,
                                          dir=(1, 0, 0)))
        cell = cell.fuse(_custom_cylinder(dia=end_dia, dz=10,
                                          x=cell_dx/2, y=0, z=dz/2,
                                          dir=(-1, 0, 0)))
        cell = cell.fuse( _custom_cylinder(dia=5, dz=dx,
                                           x=-dx/2, y=0, z=dz/2,
                                           dir=(1, 0, 0)))
        cell = cell.fuse(_custom_cylinder(dia=15, dz=cell_dia/2+10,
                                         x=0, y=0, z=dz/2,
                                         dir=(0, 1, 0)))
        
        base = base.cut(cell)
        cover = cover.cut(cell)

        for x, y in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            hole = _custom_cylinder(dia=bolt_8_32['clear_dia'], dz=dz/2,
                                    x=x*(dx/2-wall_thickness/2), y=y*(dy/2-wall_thickness/2), z=dz,
                                    head_dia=bolt_8_32['head_dia'], head_dz=dz/4)
            hole = hole.fuse(_custom_cylinder(dia=bolt_8_32['tap_dia'], dz=3/2*inch,
                                    x=x*(dx/2-wall_thickness/2), y=y*(dy/2-wall_thickness/2), z=dz/2))
            base = base.cut(hole)
            cover = cover.cut(hole)
            base = base.cut(_custom_cylinder(dia=bolt_14_20['clear_dia'], dz=inch,
                                             x=x*1.5*inch, y=y*1.5*inch, z=-(1/2*inch-dz/2),
                                             head_dia=bolt_14_20['washer_dia'], head_dz=10))

        base.translate(App.Vector(0, 0, -dz/2))
        cover.translate(App.Vector(0, 0, -dz/2))
   
        obj.Shape = Part.Compound([base, cover])



class photodetector_pda10a2:
    '''
    Photodetector, model pda10a2

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled

    Sub-Parts:
        surface_adapter (adapter_args)
    
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, adapter_args=dict()):
        adapter_args.setdefault("mount_hole_dy", 60)
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['PDA10A2']
        self.max_angle = 80
        self.max_width = 5

        _add_linked_object(obj, "Surface Adapter", surface_adapter, pos_offset=(-10.54, 0, -25), **adapter_args)
        _add_linked_object(obj, "Lens Tube", lens_tube_SM1L03, pos_offset=(-0.124, 0, -0))

    def execute(self, obj):
        mesh = _import_stl("PDA10A2-Step.stl", (90, 0, -90), (-19.87, -0, -0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 3, 4)
        part.Placement = obj.Placement
        obj.DrillPart = part


class lens_tube_SM1L03:
    '''
    SM1 Lens Tube, model SM1L03
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['SM1L03']
        self.max_angle = 0
        self.max_width = 1

    def execute(self, obj):
        mesh = _import_stl("SM1L03-Step.stl", (90, -0, 0), (8.382, 0, 0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 2, 3, z_tol=True, min_offset=(0, 4, 0), max_offset=(0, -4, 0))
        part.Placement = obj.Placement
        obj.DrillPart = part


class periscope:
    '''
    Custom periscope mount

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        lower_dz (float) : Distance from the bottom of the mount to the center of the lower mirror
        upper_dz (float) : Distance from the bottom of the mount to the center of the upper mirror
        mirror_type (obj class) : Object class of mirrors to be used
        table_mount (bool) : Whether the periscope is meant to be mounted directly to the optical table

    Sub-Parts:
        mirror_type x2 (mirror_args)
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, lower_dz=inch, upper_dz=3*inch, invert=False, mirror_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'LowerHeight').LowerHeight = lower_dz
        obj.addProperty('App::PropertyLength', 'UpperHeight').UpperHeight = upper_dz
        obj.addProperty('App::PropertyBool', 'Invert').Invert = invert

        obj.ViewObject.ShapeColor = adapter_color
        if obj.Baseplate == None:
            self.z_off = -layout.inch*3/2
        else:
            self.z_off = 0

        _add_linked_object(obj, "Lower Mirror", circular_mirror, rot_offset=((-1)**invert*90, -45, 0), pos_offset=(0, 0, obj.LowerHeight.Value+self.z_off), **mirror_args)
        _add_linked_object(obj, "Upper Mirror", circular_mirror, rot_offset=((-1)**invert*90, 135, 0), pos_offset=(0, 0, obj.UpperHeight.Value+self.z_off), **mirror_args)

    def execute(self, obj):
        width = 2*inch #Must be inch wide to keep periscope mirrors 1 inch from mount holes. 
        fillet = 15
        part = _custom_box(dx=70, dy=width, dz=obj.UpperHeight.Value+20,
                           x=0, y=0, z=0)
        for i in [-1, 1]:
            part = part.cut(_custom_box(dx=fillet*2+4, dy=width, dz=obj.UpperHeight.Value+20,
                                        x=i*(35+fillet), y=0, z=20, fillet=15,
                                        dir=(-i,0,1), fillet_dir=(0,1,0)))
            for y in [-inch/2, inch/2]:
                part = part.cut(_custom_cylinder(dia=bolt_14_20['clear_dia']+0.5, dz=inch+5,
                                            head_dia=bolt_14_20['head_dia']+0.5, head_dz=10,
                                            x=i*inch, y=y, z=25, dir=(0,0,-1)))
        part.translate(App.Vector(0, (-1)**obj.Invert*(width/2+inch/2), self.z_off))
        part = part.fuse(part)
        for i in obj.ChildObjects:
            part = _drill_part(part, obj, i)
        obj.Shape = part


class thumbscrew_hkts_5_64:
    '''
    Thumbscrew for 5-64 hex adjusters, model HKTS 5-64

    Sub-Parts:
        slide_mount (adapter_args)
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True, adapter_args=dict()):
        adapter_args.setdefault("slot_length", 10)
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['HKTS-5/64(P4)']

    def execute(self, obj):
        mesh = _import_stl("HKTS-5_64-Step.stl", (90, 0, 90), (-11.31, -0.945, 0.568))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 2, 3, z_tol=True, min_offset=(-6, 0, 0), max_offset=(-6, 0, 0))
        part.Placement = obj.Placement
        obj.DrillPart = part

class fiber_adapter_sm05fca2:
    '''
    Fiber Adapter Plate, model SM05FCA2
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['SM05FCA2']
        self.max_angle = 0
        self.max_width = 1

    def execute(self, obj):
        mesh = _import_stl("SM05FCA2-Step.stl", (0, 90, 0), (-2.334, -3.643, -0.435))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh


class fiber_adapter_sm1fca2:
    '''
    Fiber Adapter Plate, model SM1FCA2
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['SM1FCA2']
        self.max_angle = 0
        self.max_width = 1

    def execute(self, obj):
        mesh = _import_stl("SM1FCA2-Step.stl", (-180, 90, 0), (-12.47, -0.312, 15.41))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh


class lens_adapter_s05tm09:
    '''
    SM05 to M9x0.5 Lens Cell Adapter, model S05TM09
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['S05TM09']

    def execute(self, obj):
        mesh =  _import_stl("S05TM09-Step.stl", (90, 0, -90), (6.973, 0, -0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh


class lens_adapter_s1tm09:
    '''
    SM1 to M9x0.5 Lens Cell Adapter, model S1TM09
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['S1TM09']

    def execute(self, obj):
        mesh =  _import_stl("S1TM09-Step.stl", (90, 0, 90), (-3.492, 0, 0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh


class lens_tube_sm05l05:
    '''
    Lens Tube, model SM05L05
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['SM05L05']

    def execute(self, obj):
        mesh = _import_stl("SM05L05-Step.stl", (90, 0, -90), (0, 0, -0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh


class lens_tube_sm1l05:
    '''
    Lens Tube, model SM1L05
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj, drill=True):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('Part::PropertyPartShape', 'DrillPart')

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['SM1L05']

    def execute(self, obj):
        mesh = _import_stl("SM1L05-Step.stl", (90, -0, 0), (13.46, 0, 0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

        part = _bounding_box(obj, 2, 3, z_tol=True)
        part.Placement = obj.Placement
        obj.DrillPart = part


class mounted_lens_c220tmda:
    '''
    Mounted Aspheric Lens, model C220TMD-A
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.ViewObject.ShapeColor = glass_color
        self.part_numbers = ['C220TMD-A']

    def execute(self, obj):
        mesh = _import_stl("C220TMD-A-Step.stl", (-90, 0, -180), (0.419, 0, 0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh


class diode_adapter_s05lm56:
    '''
    Diode Mount Adapter, model S05LM56
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.ViewObject.ShapeColor = misc_color
        self.part_numbers = ['S05LM56']

    def execute(self, obj):
        mesh = _import_stl("S05LM56-Step.stl", (90, 0, -90), (0, 0, -0))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh

#Nishat's Edited
class Room_temp_chamber:
    '''
    Nishat importing the room temperature schamber
    Room_temperature_Chamber_simplified_version

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        mirror (bool) : Whether to add a mirror component to the mount
        thumbscrews (bool): Whether or not to add two HKTS 5-64 adjusters
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['Room_temp_chamber']

    def execute(self, obj):
        mesh = _import_stl("Room_temp_chamber_step.stl", (0, 0, 0), (-48.89, 1.266, 0.813))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh


class Room_temp_chamber_Mechanical:
    '''
    Nishat importing the room temperature schamber
    Room_temperature_Chamber_version

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        mirror (bool) : Whether to add a mirror component to the mount
        thumbscrews (bool): Whether or not to add two HKTS 5-64 adjusters
    '''
    type = 'Mesh::FeaturePython'
    def __init__(self, obj):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.ViewObject.ShapeColor = mount_color
        self.part_numbers = ['Room_temp_chamber']

    def execute(self, obj):
        mesh = _import_stl("Room Temp Chamber Mechanical.stl", (0, 0, 0), (-33.46, -10.12, -59.69))
        mesh.Placement = obj.Mesh.Placement
        obj.Mesh = mesh



class square_grating:
    '''
    Square Grating

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        thickness (float) : The thickness of the grating
        width (float) : The width of the grating
        height (float) : The height of the grating
        part_number (string) : The part number of the grating being used
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, thickness=6, width=12.7, height=12.7, part_number=''):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'Thickness').Thickness = thickness
        obj.addProperty('App::PropertyLength', 'Width').Width = width
        obj.addProperty('App::PropertyLength', 'Height').Height = height

        obj.ViewObject.ShapeColor = glass_color
        self.part_numbers = [part_number]
        self.reflection_angle = 0
        self.max_angle = 90
        self.max_width = width

    def execute(self, obj):
        part = _custom_box(dx=obj.Thickness.Value, dy=obj.Width.Value, dz=obj.Height.Value,
                           x=0, y=0, z=0, dir=(-1, 0, 0))
        obj.Shape = part


class circular_splitter:
    '''
    Circular Beam Splitter Plate

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        thickness (float) : The edge thickness of the plate
        diameter (float) : The width of the plate
        part_number (string) : The part number of the plate being used
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, thickness=3, diameter=inch/2, part_number='', mount_type=None, mount_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'Thickness').Thickness = thickness
        obj.addProperty('App::PropertyLength', 'Diameter').Diameter = diameter

        if mount_type != None:
            _add_linked_object(obj, "Mount", mount_type, pos_offset=(-thickness, 0, 0), **mount_args)

        obj.ViewObject.ShapeColor = glass_color
        obj.ViewObject.Transparency=50
        self.part_numbers = [part_number]
        self.transmission = True
        self.reflection_angle = 0
        self.max_angle = 90
        self.max_width = diameter

    def execute(self, obj):
        part = _custom_cylinder(dia=obj.Diameter.Value, dz=obj.Thickness.Value,
                           x=0, y=0, z=0, dir=(-1, 0, 0))
        obj.Shape = part


class cube_splitter:
    '''
    Beam-splitter cube

    Args:
        cube_size (float) : The side length of the splitter cube
        invert (bool) : Invert pick-off direction, false is left, true is right
        cube_part_number (string) : The Thorlabs part number of the splitter cube being used
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, cube_size=10, invert=False, cube_part_number='', mount_type=None, mount_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyLength', 'CubeSize').CubeSize = cube_size
        obj.addProperty('App::PropertyBool', 'Invert').Invert = invert

        obj.ViewObject.ShapeColor = glass_color
        obj.ViewObject.Transparency=50
        self.part_numbers = [cube_part_number]
        
        if invert:
            self.reflection_angle = -135
        else:
            self.reflection_angle = 135
        self.transmission = True
        self.max_angle = 90
        self.max_width = sqrt(200)

        if mount_type != None:
            _add_linked_object(obj, "Mount", mount_type, pos_offset=(0, 0, -cube_size/2), **mount_args)

    def execute(self, obj):
        part = _custom_box(dx=obj.CubeSize.Value, dy=obj.CubeSize.Value, dz=obj.CubeSize.Value,
                           x=0, y=0, z=0, dir=(0, 0, 0))
        temp = _custom_box(dx=sqrt(200)-0.25, dy=0.1, dz=obj.CubeSize.Value-0.25,
                           x=0, y=0, z=0, dir=(0, 0, 0))
        temp.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), -self.reflection_angle)
        part = part.cut(temp)
        obj.Shape = part


class circular_lens:
    '''
    Circular Lens

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        focal_length (float) : The focal length of the lens
        thickness (float) : The edge thickness of the lens
        diameter (float) : The width of the lens
        part_number (string) : The part number of the lens being used
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, focal_length=50, thickness=3, diameter=inch/2, part_number='', mount_type=None, mount_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'FocalLength').FocalLength = focal_length
        obj.addProperty('App::PropertyLength', 'Thickness').Thickness = thickness
        obj.addProperty('App::PropertyLength', 'Diameter').Diameter = diameter

        if mount_type != None:
            _add_linked_object(obj, "Mount", mount_type, pos_offset=(-thickness/2, 0, 0), **mount_args)

        obj.ViewObject.ShapeColor = glass_color
        obj.ViewObject.Transparency=50
        self.part_numbers = [part_number]
        self.transmission = True
        self.focal_length = obj.FocalLength.Value
        self.max_angle = 90
        self.max_width = diameter

    def execute(self, obj):
        part = _custom_cylinder(dia=obj.Diameter.Value, dz=obj.Thickness.Value,
                                x=-obj.Thickness.Value/2, y=0, z=0, dir=(1, 0, 0))
        obj.Shape = part


class waveplate:
    '''
    Waveplate

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        thickness (float) : The thickness of the waveplate
        diameter (float) : The width of the waveplate
        part_number (string) : The part number of the waveplate being used
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, thickness=1, diameter=inch/2, part_number='', mount_type=None, mount_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'Thickness').Thickness = thickness
        obj.addProperty('App::PropertyLength', 'Diameter').Diameter = diameter

        if mount_type != None:
            _add_linked_object(obj, "Mount", mount_type, pos_offset=(-thickness/2, 0, 0), **mount_args)

        obj.ViewObject.ShapeColor = glass_color
        obj.ViewObject.Transparency=50
        self.part_numbers = [part_number]
        self.transmission = True
        self.max_angle = 90
        self.max_width = diameter

    def execute(self, obj):
        part = _custom_cylinder(dia=obj.Diameter.Value, dz=obj.Thickness.Value,
                                x=-obj.Thickness.Value/2, y=0, z=0, dir=(1, 0, 0))
        obj.Shape = part


class circular_mirror:
    '''
    Circular Mirror

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        thickness (float) : The thickness of the mirror
        diameter (float) : The width of the mirror
        part_number (string) : The part number of the mirror being used
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, thickness=6, diameter=inch/2, part_number='', mount_type=None, mount_args=dict()):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'Thickness').Thickness = thickness
        obj.addProperty('App::PropertyLength', 'Diameter').Diameter = diameter

        if mount_type != None:
            _add_linked_object(obj, "Mount", mount_type, pos_offset=(-thickness, 0, 0), **mount_args)

        obj.ViewObject.ShapeColor = glass_color
        self.part_numbers = [part_number]
        self.reflection_angle = 0
        self.max_angle = 90
        self.max_width = diameter

    def execute(self, obj):
        part = _custom_cylinder(dia=obj.Diameter.Value, dz=obj.Thickness.Value,
                           x=0, y=0, z=0, dir=(-1, 0, 0))
        obj.Shape = part


class square_mirror:
    '''
    Square Mirror

    Args:
        drill (bool) : Whether baseplate mounting for this part should be drilled
        thickness (float) : The thickness of the mirror
        width (float) : The width of the mirror
        height (float) : The height of the mirror
        part_number (string) : The part number of the mirror being used
    '''
    type = 'Part::FeaturePython'
    def __init__(self, obj, drill=True, thickness=3.2, width=12.7, height=12.7, part_number=''):
        obj.Proxy = self
        ViewProvider(obj.ViewObject)

        obj.addProperty('App::PropertyBool', 'Drill').Drill = drill
        obj.addProperty('App::PropertyLength', 'Thickness').Thickness = thickness
        obj.addProperty('App::PropertyLength', 'Width').Width = width
        obj.addProperty('App::PropertyLength', 'Height').Height = height

        obj.ViewObject.ShapeColor = glass_color
        self.part_numbers = [part_number]
        self.reflection_angle = 0
        self.max_angle = 90
        self.max_width = width

    def execute(self, obj):
        part = _custom_box(dx=obj.Thickness.Value, dy=obj.Width.Value, dz=obj.Height.Value,
                           x=0, y=0, z=0, dir=(-1, 0, 0))
        obj.Shape = part


class ViewProvider:
    def __init__(self, obj):
        obj.Proxy = self
        self.Object = obj.Object

    def attach(self, obj):
        return

    def getDefaultDisplayMode(self):
        return "Shaded"

    def onDelete(self, feature, subelements):
        if hasattr(feature.Object, "ParentObject"):
            if feature.Object.ParentObject != None:
                return False
        if hasattr(feature.Object, "ChildObjects"):
            for obj in feature.Object.ChildObjects:
                App.ActiveDocument.removeObject(obj.Name)
        return True
    
    def updateData(self, obj, prop):
        if str(prop) == "BasePlacement":
            if obj.Baseplate != None:
                obj.Placement.Base = obj.BasePlacement.Base + obj.Baseplate.Placement.Base
                obj.Placement = App.Placement(obj.Placement.Base, obj.Baseplate.Placement.Rotation, -obj.BasePlacement.Base)
                obj.Placement.Rotation = obj.Placement.Rotation.multiply(obj.BasePlacement.Rotation)
            else:
                obj.Placement = obj.BasePlacement
            if hasattr(obj, "ChildObjects"):
                for child in obj.ChildObjects:
                    child.BasePlacement.Base = obj.BasePlacement.Base + child.RelativePlacement.Base
                    if hasattr(child, "Angle"):
                        obj.BasePlacement.Rotation = App.Rotation(App.Vector(0, 0, 1), obj.Angle)
                    else:
                        child.BasePlacement = App.Placement(child.BasePlacement.Base, obj.BasePlacement.Rotation, -child.RelativePlacement.Base)
                        child.BasePlacement.Rotation = child.BasePlacement.Rotation.multiply(child.RelativePlacement.Rotation)
            if hasattr(obj, "RelativeObjects"):
                for child in obj.RelativeObjects:
                    child.BasePlacement.Base = obj.BasePlacement.Base + child.RelativePlacement.Base
        if str(prop) == "Angle":
            obj.BasePlacement.Rotation = App.Rotation(App.Vector(0, 0, 1), obj.Angle)
        return
    
    def claimChildren(self):
        if hasattr(self.Object, "ChildObjects"):
            return self.Object.ChildObjects
        else:
            return []

    def getIcon(self):
        return """
            /* XPM */
            static char *_e94ebdf19f64588ceeb5b5397743c6amoxjrynTrPg9Fk5U[] = {
            /* columns rows colors chars-per-pixel */
            "16 16 2 1 ",
            "  c None",
            "& c red",
            /* pixels */
            "                ",
            "  &&&&&&&&&&&&  ",
            "  &&&&&&&&&&&&  ",
            "  &&&&&&&&&&&&  ",
            "  &&&&&&&&&&&&  ",
            "      &&&&      ",
            "      &&&&      ",
            "      &&&&      ",
            "      &&&&      ",
            "      &&&&      ",
            "      &&&&      ",
            "      &&&&      ",
            "      &&&&      ",
            "      &&&&      ",
            "      &&&&      ",
            "                "
            };
            """

    def __getstate__(self):
        return None

    def __setstate__(self,state):
        return None
