from ... import config
from ...lib import fusion360utils as futil
import adsk.fusion
import adsk.core
import sys
import re
import copy
import json
import os
import adsk.core
from pathlib import Path

from fontTools import ttLib

app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_initiateLabelSketches'
CMD_NAME = 'KCG: Initiate Labels sketches'
CMD_Description = 'Initiates the Labels sketches for generation of labeled keycaps'
# legends are either alpha or from sketch with same name

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = config.WORKSPACE_ID
PANEL_ID = config.PANEL_ID
COMMAND_BESIDE_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_addStems'

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(
        CMD_ID, 
        CMD_NAME, 
        CMD_Description, 
        ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(
        cmd_def.commandCreated, 
        command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = workspace.toolbarPanels.itemById(PANEL_ID)

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(
        cmd_def, 
        COMMAND_BESIDE_ID, 
        False)

    # Specify if the command is promoted to the main toolbar.
    control.isPromoted = IS_PROMOTED

    editCmdDef = ui.commandDefinitions.addButtonDefinition(
        CMD_ID + '-edit', 
        'Edit ' + CMD_NAME, 
        'Edits ' + CMD_NAME, 
        '')

    # Define an event handler for the edit command created event. It will be called when the button is clicked.
    futil.add_handler(
        editCmdDef.commandCreated, 
        command_created) 
    
    global featureDef    
    featureDef = adsk.fusion.CustomFeatureDefinition.create(
        CMD_ID + '-feature',
        CMD_NAME,
        ICON_FOLDER)
    featureDef.editCommandId = editCmdDef.id


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    edit_command_definition = ui.commandDefinitions.itemById(CMD_ID+'-edit')

    if edit_command_definition:
        edit_command_definition.deleteMe()

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Created Event')

    inputs = args.command.commandInputs

    inputs.addTextBoxCommandInput(
        'kleRaw', 'KLE Raw Data', '["Q","W","E","R"],["A","S","D","F"]', 7, False)

    sizesSelect = inputs.addSelectionInput(
        'labels', 'Existing '+config.COMPONENT_NAME_LABELS, 'If a label assembly already exists, selecting it will lead to an update of the component.')
    sizesSelect.setSelectionLimits(0, 1)
    sizesSelect.addSelectionFilter(adsk.core.SelectionCommandInput.Occurrences)

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
        'sketchDistance', 'Sketch Distance', 'mm', adsk.core.ValueInput.createByReal(1.1))
    sketchAngleInput = sketchConstructionInputs.addAngleValueCommandInput(
        'sketchAngle', 'Sketch Angle', adsk.core.ValueInput.createByReal(0.0))

    fontConfigInput = inputs.addGroupCommandInput(
        'fontConfig', 'Font Config')
    fontConfigInput.isExpanded = True
    fontConfigInputs = fontConfigInput.children

    fonts = getFontList()

    fontInput = fontConfigInputs.addDropDownCommandInput(
        'font', 'Font', adsk.core.DropDownStyles.TextListDropDownStyle)
    fontItems = fontInput.listItems
    for font in fonts.keys():
        fontItems.add(font, False)
    fontItems[0].isSelected = True

    fontSizeInput = fontConfigInputs.addValueInput(
        'fontSize', 'Font Size', 'mm', adsk.core.ValueInput.createByReal(0.4))
    fontXOffsetInput = fontConfigInputs.addValueInput(
        'fontXOffset', 'Font X Offset', 'mm', adsk.core.ValueInput.createByReal(0.0))
    fontYOffsetInput = fontConfigInputs.addValueInput(
        'fontYOffset', 'Font Y Offset', 'mm', adsk.core.ValueInput.createByReal(0.0))
    # TODO: Bold, italic, rotation, KLE label position

    futil.add_handler(args.command.execute, command_execute,
                      local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged,
                      command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview,
                      command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs,
                      command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy,
                      local_handlers=local_handlers)


# This event handler is called when the user clicks the OK button in the command dialog or
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')

    inputs = args.command.commandInputs
    kleRawInput: adsk.core.TextBoxCommandInput = inputs.itemById('kleRaw')
    kleJson = fixKLERaw2Json(kleRawInput.text)
    futil.log(f'{CMD_NAME} kleRaw: ' + kleJson)
    positions = readKLEjson(kleJson)
    futil.log(f'{CMD_NAME} Positions: ' + '; '.join(map(str, positions)))

    labelsInput: adsk.core.SelectionCommandInput = inputs.itemById('labels')
    labels:adsk.fusion.Component = None
    if labelsInput.selectionCount == 1:
        labelsOccurrence = labelsInput.selection(0).entity
        labels = labelsOccurrence.component

    planeInput: adsk.core.SelectionCommandInput = inputs.itemById(
        'legendPlane')
    if planeInput.selectionCount == 1:
        plane = planeInput.selection(0).entity
    else:
        plane = None

    offsetInput: adsk.core.ValueCommandInput = inputs.itemById(
        'sketchDistance')
    offset = offsetInput.value
    angleInput: adsk.core.ValueCommandInput = inputs.itemById(
        'sketchAngle')
    angle = angleInput.value

    fontInput: adsk.core.DropDownCommandInput = inputs.itemById('font')
    selectedFont = fontInput.selectedItem
    font = selectedFont.name
    futil.log(f'{CMD_NAME} selected font: ' + str(font))
    fontSizeInput: adsk.core.ValueCommandInput = inputs.itemById('fontSize')
    fontSize = fontSizeInput.value
    fontXOffsetInput: adsk.core.ValueCommandInput = inputs.itemById(
        'fontXOffset')
    fontXOffset = fontXOffsetInput.value
    fontYOffsetInput: adsk.core.ValueCommandInput = inputs.itemById(
        'fontYOffset')
    fontYOffset = fontYOffsetInput.value

    # Create new assembly component

    design = adsk.fusion.Design.cast(app.activeProduct)
    
    startOp: adsk.core.Base = None
    endOp: adsk.core.Base = None
    if labels is None:
        trans = adsk.core.Matrix3D.create()
        labelsOccurrence = design.rootComponent.occurrences.addNewComponent(
            trans)
        startOp = setStartOp(startOp, labelsOccurrence)
        labels = labelsOccurrence.component
        labels.name = config.COMPONENT_NAME_LABELS

    if plane is None:
        planes = labels.constructionPlanes
        if angle is not None and angle != 0.0:
            anglePlaneInput = planes.createInput()
            anglePlaneInput.setByAngle(
                labels.xConstructionAxis,
                adsk.core.ValueInput.createByReal(angle),
                labels.xYConstructionPlane)
            basePlane = planes.add(anglePlaneInput)
            startOp = setStartOp(startOp, basePlane)
            basePlane.isLightBulbOn = False
            basePlane.name = 'Font Angle Base'
        else:
            basePlane = labels.xYConstructionPlane
        offsetPlaneInput = planes.createInput()
        offsetPlaneInput.setByOffset(
            basePlane,
            adsk.core.ValueInput.createByReal(offset))
        sketchPlane = planes.add(offsetPlaneInput)
        startOp = setStartOp(startOp, sketchPlane)
        sketchPlane.name = 'Font Sketch Plane'
    else:
        sketchPlane = plane
    sketchTranslation = sketchPlane.transform.translation
    futil.log(f'{CMD_NAME} sketchTranslation: ' + ', '.join(map(str,
              [sketchTranslation.x, sketchTranslation.y, sketchTranslation.z])))

    cornerPoint = adsk.core.Point3D.create(
        -fontSize*30+fontXOffset-sketchTranslation.x,
        fontSize*3+fontYOffset-sketchTranslation.y,
        0)
    diagonalPoint = adsk.core.Point3D.create(
        fontSize*30+fontXOffset-sketchTranslation.x,
        -fontSize*3+fontYOffset-sketchTranslation.y,
        0)
    # Delete old sketches, if present, and make new ones
    notFound = []
    for position in positions:
        sketchName = position.label
        oldSketch = labels.sketches.itemByName(sketchName)
        if oldSketch is not None:
            if not oldSketch.deleteMe():
                oldSketch.name = '##' + oldSketch.name
        sketch = labels.sketches.add(sketchPlane)
        startOp = setStartOp(startOp, sketch)
        sketch.name = position.label
        texts = sketch.sketchTexts
        labelInput = texts.createInput2(
            position.label,
            fontSize)
        labelInput.setAsMultiLine(
            cornerPoint,
            diagonalPoint,
            adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
            adsk.core.VerticalAlignments.MiddleVerticalAlignment,
            0.0)
        labelInput.fontName = font
        text = texts.add(labelInput)
        endOp = sketch
        adsk.doEvents()

    # Logging if a size was not found
    if int(len(notFound)) > 1:
        futil.log(f'{CMD_NAME} sizes not found for positions: ' +
                  '; '.join(map(str, notFound)))

    featureComponent = design.activeComponent
    customFeature = featureComponent.features.customFeatures.createInput(featureDef)
    customFeature.setStartAndEndFeatures(startOp, endOp)
    featureComponent.features.customFeatures.add(customFeature)
    
def setStartOp(startOp: adsk.core.Base,
               nextOp: adsk.core.Base) ->adsk.core.Base:
    if startOp is None:
        return nextOp
    else:
        return startOp 

# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Preview Event')
    inputs = args.command.commandInputs


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs

    # General logging for debug.
    futil.log(
        f'{CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputs = args.inputs


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []


def fixKLERaw2Json(kleRaw):
    enclosedRaw = '[' + kleRaw + ']'
    doubleQuotedProperties = re.sub('([a-z]?[a-z0-9]):', '"\\1":', enclosedRaw)
    return doubleQuotedProperties


def readKLEjson(kleJson):
    rows = json.loads(kleJson)
    currentPosition = Position()
    positions = []
    for rowNum, row in enumerate(rows):
        for item in row:
            if isinstance(item, str):
                labeledPosition = copy.copy(currentPosition)
                labeledPosition.label = item
                positions.append(labeledPosition)
                currentPosition.incrementXresetW()
            if isinstance(item, dict):
                if 'x' in item:
                    currentPosition.x += item['x']
                if 'y' in item:
                    currentPosition.y += item['y']
                if 'w' in item:
                    currentPosition.w = item['w']
                if 'h' in item:
                    currentPosition.h = item['h']
                if 'rx' in item:
                    currentPosition.rx = item['rx']
                if 'ry' in item:
                    currentPosition.ry = item['ry']
                if 'r' in item:
                    currentPosition.r = item['r']
        currentPosition.x = 0
        currentPosition.y += 1
    return positions


class Position:
    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self.w = 1
        self.h = 1
        self.label = ''
        self.r = 0
        self.rx = 0
        self.ry = 0

    def incrementXresetW(self):
        self.x += self.w
        self.w = 1
        self.h = 1

    def __str__(self):
        return f'(x={self.x}, y={self.y}, w={self.w}, h={self.h}, l={self.label}, r={self.r}, rx={self.rx} , ry={self.ry})'


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
