from __future__ import annotations

from adsk.fusion import CustomFeatureEventArgs
from ... import config
from ...lib import fusion360utils as futil
import adsk.fusion
import adsk.core
import sys
import time
import os
import adsk.core
from pathlib import Path

from ...common.keyCapGeneratorUtil import KCGCommand, KCGCustomFeature
from ...common.keyboardLayoutEditor import KLE, KLEPosition

from fontTools import ttLib

app = adsk.core.Application.get()
ui = app.userInterface

kcgCommand = KCGCommand(
    config.CMD_INITIATE_LEGEND_SKETCHES_ID, 
    'KCG: Initiate Legend sketches',
    'Initiates the Legend sketches for generation of labeled keycaps')

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# Executed when add-in is run.
def start():
    kcgCommand.editCreatedCallback = command_created_edit
    kcgCommand.commandCreatedCallback = command_created
    kcgCommand.computeCallback = ComputeLegendSketches()
    kcgCommand.start(ui, ICON_FOLDER)

# Executed when add-in is stopped.
def stop():
    kcgCommand.stop(ui)

class InitiateLegendSketchesValues:
    def __init__(self) -> None:
        self.kleRaw:str = None
        self.positions: list[KLEPosition] = []
        self.legendsComponent: adsk.fusion.Component = None
        self.legendsPlane: adsk.fusion.ConstructionPlane = None 
        self.offset: float = None
        self.angle: float = None
        self.font: str = None
        self.fontSize: float = None
        self.fontXOffset: float = None
        self.fontYOffset: float = None
        self.fontStyle = None

    @classmethod
    def readInputs(
            cls,
            inputs: adsk.core.CommandInputs) -> InitiateLegendSketchesValues:
        values = cls()
        kleRawInput: adsk.core.TextBoxCommandInput = inputs.itemById('kleRaw')
        values.kleRaw = kleRawInput.text 
        kle = KLE(kleRawInput.text)
        values.positions: list[KLEPosition] = kle.getKLEPositions()

        legendsInput: adsk.core.SelectionCommandInput = inputs.itemById('legends')
        if legendsInput.selectionCount == 1:
            legendsOccurrence = legendsInput.selection(0).entity
            values.legendsComponent = legendsOccurrence.component

        planeInput: adsk.core.SelectionCommandInput = inputs.itemById(
            'legendPlane')
        if planeInput.selectionCount == 1:
            values.legendsPlane: adsk.fusion.ConstructionPlane = planeInput.selection(0).entity
        else:
            values.legendsPlane: adsk.fusion.ConstructionPlane = None

        offsetInput: adsk.core.ValueCommandInput = inputs.itemById(
            'sketchDistance')
        values.offset = offsetInput.value
        angleInput: adsk.core.ValueCommandInput = inputs.itemById(
            'sketchAngle')
        values.angle = angleInput.value

        fontInput: adsk.core.DropDownCommandInput = inputs.itemById('font')
        selectedFont = fontInput.selectedItem
        values.font = selectedFont.name
        fontSizeInput: adsk.core.ValueCommandInput = inputs.itemById('fontSize')
        values.fontSize = fontSizeInput.value
        fontXOffsetInput: adsk.core.ValueCommandInput = inputs.itemById(
            'fontXOffset')
        values.fontXOffset = fontXOffsetInput.value
        fontYOffsetInput: adsk.core.ValueCommandInput = inputs.itemById(
            'fontYOffset')
        values.fontYOffset = fontYOffsetInput.value

        values.fontStyle = None # TODO
        return values
    
    @classmethod
    def readFeature(
            cls,
            customFeature: adsk.fusion.CustomFeature) -> InitiateLegendSketchesValues:
        values = cls() 
        parameters = customFeature.parameters
        dependencies = customFeature.dependencies

        '''
        parent: adsk.fusion.CustomFeatureDependency = dependencies.itemById('legendsParent')
        values.legendsComponent = parent.entity
        plane: adsk.fusion.CustomFeatureDependency = dependencies.itemById('legendsPlane')
        values.legendsPlane = plane.entity
        '''
        try: # for some reason there's a "invalid argument id" error instead of returning null
            distance: adsk.fusion.CustomFeatureParameter = parameters.itemById('legendsSketchDistance')
            if distance:
                values.offset = distance.value
        except:
            pass
        try: # for some reason there's a "invalid argument id" error instead of returning null
            angle: adsk.fusion.CustomFeatureParameter = parameters.itemById('legendsSketchAngle')
            if angle:
                values.angle = angle.value
        except:
            pass

        fontSize: adsk.fusion.CustomFeatureParameter = parameters.itemById('legendsFontSize')
        values.fontSize = fontSize.value
        xOffset: adsk.fusion.CustomFeatureParameter = parameters.itemById('legendsXOffset')
        values.fontXOffset = xOffset.value
        yOffset: adsk.fusion.CustomFeatureParameter = parameters.itemById('legendsYOffset')
        values.fontYOffset = yOffset.value

        return values
    
    def addValuesToFeature(
            self,
            feature: KCGCustomFeature):
        '''
        feature.addDependency(
            'legendsParent',
            self.legendsComponent)
        feature.addDependency(
            'legendsPlane',
            self.legendsPlane) 
        '''
        # Because of fusion bugs we can either set angle or offset
        if self.angle == 0.0:
            feature.addParameter(
                'legendsSketchDistance', 
                'Legends Sketch Distance', 
                adsk.core.ValueInput.createByReal(self.offset), 
                'mm', 
                True)
        else:
            feature.addParameter(
                'legendsSketchAngle', 
                'Legends Sketch Angle', 
                adsk.core.ValueInput.createByReal(self.angle), 
                'deg', 
                True)

        
        feature.addParameter(
            'legendsFontSize', 
            'Legends Font Size', 
            adsk.core.ValueInput.createByReal(self.fontSize), 
            'mm', 
            True)
        feature.addParameter(
            'legendsXOffset', 
            'Legends X Offset', 
            adsk.core.ValueInput.createByReal(self.fontXOffset), 
            'mm', 
            False)
        feature.addParameter(
            'legendsYOffset', 
            'Legends Y Offset', 
            adsk.core.ValueInput.createByReal(self.fontYOffset), 
            'mm', 
            False)


def createInitiateLegendSketchesGui(
        inputs: adsk.core.CommandInputs,
        values: InitiateLegendSketchesValues = InitiateLegendSketchesValues()):
    inputs.addTextBoxCommandInput(
        'kleRaw', 
        'KLE Raw Data', 
        values.kleRaw if values.kleRaw else '["Q","W","E","R"],["A","S","D","F"]', 
        7, 
        False)
    legendsComponentSelect = inputs.addSelectionInput(
        'legends', 
        'Existing '+config.COMPONENT_NAME_LEGENDS, 
        'If a label assembly already exists, selecting it will lead to an update of the component.')
    legendsComponentSelect.setSelectionLimits(0, 1)
    legendsComponentSelect.addSelectionFilter(adsk.core.SelectionCommandInput.Occurrences)

    sketchConstructionInput = inputs.addGroupCommandInput(
        'sketchConstruction', 'Sketch Construction Config')
    sketchConstructionInput.isExpanded = True
    sketchConstructionInputs = sketchConstructionInput.children
    # Either select an existing plane...
    legendPlaneSelect = sketchConstructionInputs.addSelectionInput(
        'legendPlane', 'Existing construction plane', 'Construction plane for the label sketches.')
    legendPlaneSelect.setSelectionLimits(0, 1)
    legendPlaneSelect.addSelectionFilter(
        adsk.core.SelectionCommandInput.ConstructionPlanes)
    # ...or config a new one
    sketchDistanceInput = sketchConstructionInputs.addValueInput(
        'sketchDistance', 
        'Sketch Distance', 
        'mm', 
        adsk.core.ValueInput.createByReal(
            values.offset if values.offset else 1.1))
    sketchAngleInput = sketchConstructionInputs.addAngleValueCommandInput(
        'sketchAngle', 
        'Sketch Angle', 
        adsk.core.ValueInput.createByReal(
            values.angle if values.angle else 0.0))

    fontConfigInput = inputs.addGroupCommandInput(
        'fontConfig', 'Font Config')
    fontConfigInput.isExpanded = True
    fontConfigInputs = fontConfigInput.children

    fonts = getFontList()

    fontInput = fontConfigInputs.addDropDownCommandInput(
        'font', 
        'Font', 
        adsk.core.DropDownStyles.TextListDropDownStyle)
    fontItems = fontInput.listItems
    wasSelected = False
    for font in fonts.keys():
        isSelected =values.font == font 
        fontItems.add(font, isSelected)
        wasSelected |= isSelected
    if not wasSelected:
        fontItems[0].isSelected = True

    fontSizeInput = fontConfigInputs.addValueInput(
        'fontSize', 
        'Font Size', 
        'mm', 
        adsk.core.ValueInput.createByReal(
            values.fontSize if values.fontSize else 0.4))
    fontXOffsetInput = fontConfigInputs.addValueInput(
        'fontXOffset', 
        'Font X Offset', 
        'mm', 
        adsk.core.ValueInput.createByReal(
            values.fontXOffset if values.fontXOffset else 0.0))
    fontYOffsetInput = fontConfigInputs.addValueInput(
        'fontYOffset', 
        'Font Y Offset', 
        'mm', 
        adsk.core.ValueInput.createByReal(
            values.fontYOffset if values.fontYOffset else 0.0))


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    inputs = args.command.commandInputs

    createInitiateLegendSketchesGui(inputs)

    futil.add_handler(args.command.execute, 
                      command_execute,
                      local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged,
                      command_input_changed, 
                      local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview,
                      command_preview, 
                      local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs,
                      command_validate_input, 
                      local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, 
                      command_destroy,
                      local_handlers=local_handlers)

def command_created_edit(args: adsk.core.CommandCreatedEventArgs):
    inputs = args.command.commandInputs

    customFeature: adsk.fusion.CustomFeature = ui.activeSelections.item(0).entity
    values = InitiateLegendSketchesValues.readFeature(customFeature)
    createInitiateLegendSketchesGui(
        inputs,
        values)
    
    futil.add_handler(args.command.execute, 
                      command_execute,
                      local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged,
                      command_input_changed, 
                      local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview,
                      command_preview, 
                      local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs,
                      command_validate_input, 
                      local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, 
                      command_destroy,
                      local_handlers=local_handlers)

class LegendSketchGenerator:
    def __init__(
            self, 
            parent: adsk.fusion.Component,
            values: InitiateLegendSketchesValues,
            text: str,
            label: str) -> None:
        self.parent = parent
        self.sketchPlane = values.legendsPlane
        # Sketches do not need to be centered on origin
        sketchTranslation = self.sketchPlane.transform.translation
        self.cornerPoint = adsk.core.Point3D.create(
            -values.fontSize*30 + values.fontXOffset - sketchTranslation.x,
            values.fontSize*3 + values.fontYOffset - sketchTranslation.y,
            0)
        self.diagonalPoint = adsk.core.Point3D.create(
            values.fontSize*30 + values.fontXOffset - sketchTranslation.x,
            -values.fontSize*3 + values.fontYOffset - sketchTranslation.y,
            0)
        self.name = label
        self.text = text
        self.font = values.font
        self.fontSize = values.fontSize
        self.fontStyle = values.fontStyle

    def generate(self):
        oldSketch = self.parent.sketches.itemByName(self.name)
        if oldSketch:
            self.updateSketch(oldSketch)
        else:
            self.newSketch()
            
    def updateSketch(
            self,
            sketch: adsk.fusion.Sketch):
        texts = sketch.sketchTexts
        for text in texts:
            if text.text == self.text:
                text.fontName = self.font
                text.height = self.fontSize
                if self.fontStyle:
                    text.textStyle = self.fontStyle
                # TODO update offsets

    def newSketch(
            self):
        sketches = self.parent.sketches
        sketch = sketches.add(self.sketchPlane)
        sketch.name = self.name
        texts = sketch.sketchTexts
        labelInput = texts.createInput2(
            self.text,
            self.fontSize)
        labelInput.setAsMultiLine(
            self.cornerPoint,
            self.diagonalPoint,
            adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
            adsk.core.VerticalAlignments.MiddleVerticalAlignment,
            0.0)
        labelInput.fontName = self.font
        texts.add(labelInput)

class ComputeLegendSketches(adsk.fusion.CustomFeatureEventHandler):
    def __init__(self):
        super().__init__()

    def notify(
            self, 
            eventArgs: CustomFeatureEventArgs) -> None:
        customFeature = eventArgs.customFeature

        try: 
            values = InitiateLegendSketchesValues.readFeature(customFeature)
            offsetPlane: adsk.fusion.ConstructionPlane = None
            anglePlane: adsk.fusion.ConstructionPlane = None
            for feature in customFeature.features:
                if feature.objectType == adsk.fusion.ConstructionPlane.classType():
                    if offsetPlane:
                        anglePlane = offsetPlane
                        offsetPlane = feature
                    else:
                        offsetPlane = feature
                if feature.objectType == adsk.fusion.Sketch.classType():
                    label = feature.name
                    text: adsk.fusion.SketchText
                    for text in feature.sketchTexts:
                        if text.text == label:
                            text.height = values.fontSize
                            # TODO definition: adsk.fusion.MultiLineTextDefinition = text.definition
            # There's a bug which crashes fusion if we adjust both planes
            if anglePlane and values.angle:
                definition: adsk.fusion.ConstructionPlaneAtAngleDefinition = anglePlane.definition
                definition.redefine(
                    adsk.core.ValueInput.createByReal(values.angle),
                    definition.linearEntity,
                    None)
            if offsetPlane and values.offset:
                definition: adsk.fusion.ConstructionPlaneOffsetDefinition = offsetPlane.definition
                definition.redefine(
                    adsk.core.ValueInput.createByReal(values.offset),
                    definition.planarEntity)
        except Exception as e:
            eventArgs.computeStatus.statusMessages.addError(kcgCommand.kcgId.id+'_COMPUTE_FAILED', f'caught {type(e)}: {e.args[0]}')
        adsk.doEvents()

# This event handler is called when the user clicks the OK button in the command dialog or
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    inputs = args.command.commandInputs
    values = InitiateLegendSketchesValues.readInputs(inputs)
    # Create new assembly component

    design = adsk.fusion.Design.cast(app.activeProduct)
    activeComponent = design.activeComponent

    # Create legends component if not selected
    sketchComponent = values.legendsComponent
    if sketchComponent is None:
        trans = adsk.core.Matrix3D.create()
        labelsOccurrence = activeComponent.occurrences.addNewComponent(trans)
        sketchComponent = labelsOccurrence.component
        sketchComponent.name = config.COMPONENT_NAME_LEGENDS
        values.legendsComponent = sketchComponent
    # Start feature (currently cannot capture occurrence creation decently)
    feature = KCGCustomFeature(
        kcgCommand.featureDefinition, 
        design.timeline, 
        activeComponent)
    feature.startExecution()
    # Create sketch plane if not selected
    if values.legendsPlane is None:
        planes = sketchComponent.constructionPlanes
        if values.angle is not None and values.angle != 0.0:
            anglePlaneInput = planes.createInput()
            anglePlaneInput.setByAngle(
                sketchComponent.xConstructionAxis,
                adsk.core.ValueInput.createByReal(values.angle),
                sketchComponent.xYConstructionPlane)
            basePlane = planes.add(anglePlaneInput)
            basePlane.isLightBulbOn = False
            basePlane.name = 'Font Angle Base'
        else:
            basePlane = sketchComponent.xYConstructionPlane
        offsetPlaneInput = planes.createInput()
        offsetPlaneInput.setByOffset(
            basePlane,
            adsk.core.ValueInput.createByReal(values.offset))
        sketchPlane = planes.add(offsetPlaneInput)
        sketchPlane.name = 'Font Sketch Plane'
        values.legendsPlane = sketchPlane
    # Iterate positions and create or update sketches
    for position in values.positions:
        generator = LegendSketchGenerator(
            sketchComponent, 
            values, 
            position.text,
            position.label)
        generator.generate()
        adsk.doEvents()
    # End feature
    values.addValuesToFeature(feature)
    feature.endExecution()
    

# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    inputs = args.command.commandInputs


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    inputs = args.inputs


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []


######### begin functions for Font ##################
# see: https://gist.github.com/pklaus/dce37521579513c574d0 and https://forums.autodesk.com/t5/fusion-360-api-and-scripts/api-access-to-list-of-available-supported-fonts/td-p/8899284
FONT_SPECIFIER_NAME_ID = 4
FONT_SPECIFIER_FAMILY_ID = 1
# short name of a truetype font
# platformID: Windows or Mac


def shortName(font, platformID):
    name = ""
    family = ""
    for record in font['name'].names:
        if b'\x00' in record.string:
            name_str = record.string.decode('utf-16-be')
        else:
            try:
                name_str = record.string.decode('utf-8')
            except UnicodeDecodeError:
                name_str = "<<UTF-8 DECODING ERROR>>"
        if record.nameID == FONT_SPECIFIER_NAME_ID and not name and record.platformID == platformID:
            name = name_str
        elif record.nameID == FONT_SPECIFIER_FAMILY_ID and not family and record.platformID == platformID:
            family = name_str
        if name and family:
            break

    return name, family


def getFontList():
    dic = {}
    app = adsk.core.Application.get()
    ui = app.userInterface
    if sys.platform.startswith('win') or sys.platform.startswith('cygwin'):
        # Windows
        FontPath = os.path.join(os.environ['WINDIR'], 'Fonts')
        PlatFormID = 3
    elif sys.platform.startswith('darwin'):
        # Mac
        FontPath = '/Library/Fonts/'
        PlatFormID = 1
    else:
        if ui:
            ui.messageBox('This is an unknown OS!!')
            return

    # iterate each *.ttf font in the specific folder
    for file in os.listdir(FontPath):
        if file.lower().endswith(".ttf") or file.lower().endswith(".ttc"):
            source_file_name = FontPath+"/"+file
            tt = ttLib.TTFont(source_file_name, fontNumber=0)
            font_ori_name = shortName(tt, PlatFormID)[1]
            # store this font to fonts map
            if not font_ori_name in dic:
                dic[font_ori_name] = source_file_name
    return dic
