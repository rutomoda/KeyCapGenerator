import adsk.core
import adsk.fusion
import os
import json
import copy
import re

from ...common.keyboardLayoutEditor import KLEPosition, KLE
from ...common.keyCapGeneratorUtil import KCGComponent, SizeNameFormat
from ...lib import fusion360utils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_generateLayout'
CMD_NAME = 'KCG: Generate Layout'
CMD_Description = 'Generate the KLE layout with the keycap bodies by generating legends and moving the corresponding keycap bodies to the correct position'
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
        CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = workspace.toolbarPanels.itemById(PANEL_ID)

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

    # Specify if the command is promoted to the main toolbar.
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

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

    sizesSelect = inputs.addSelectionInput(
        'sizes', config.COMPONENT_NAME_SIZES, 'The component containing all the base generated sizes. Size matching is done by name, e.g.: "*2_25U*" will be used for 2.25U.')
    sizesSelect.setSelectionLimits(1, 1)
    sizesSelect.addSelectionFilter(adsk.core.SelectionCommandInput.Occurrences)

    labeledSizesSelect = inputs.addSelectionInput(
        'labeledSizes', config.COMPONENT_NAME_LABELED, 'The component containing all the labeled generated sizes. Size matching is done by name, e.g.: "*2_25U+A" will be used for legend "A" and size 2.25U.')
    labeledSizesSelect.setSelectionLimits(0, 1)
    labeledSizesSelect.addSelectionFilter(
        adsk.core.SelectionCommandInput.Occurrences)

    spacing1UXInput = inputs.addValueInput(
        'spacing1UX', '1U Spacing Horizontal', 'mm', adsk.core.ValueInput.createByReal(config.DEFAULT_1U_SPACING))
    spacing1UXInput.minimumValue = 0
    spacing1UXInput.isMinimumValueInclusive = False

    spacing1UYInput = inputs.addValueInput(
        'spacing1UY', '1U Spacing Vertical', 'mm', adsk.core.ValueInput.createByReal(config.DEFAULT_1U_SPACING))
    spacing1UYInput.minimumValue = 0
    spacing1UYInput.isMinimumValueInclusive = False

    inputs.addTextBoxCommandInput(
        'kleRaw', 'KLE Raw Data', '["Q","W","E","R"],["A","S","D","F"],["Z","X","C","V"]', 7, False)

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
    sizesInput: adsk.core.SelectionCommandInput = inputs.itemById('sizes')
    sizes = KCGComponent(sizesInput.selection(0).entity.component)
    kleRawInput: adsk.core.TextBoxCommandInput = inputs.itemById('kleRaw')
    kle = KLE(kleRawInput.text)
    positions = kle.getKLEPostions()

    labeledSizesInput: adsk.core.SelectionCommandInput = inputs.itemById(
        'labeledSizes')
    if labeledSizesInput.selectionCount == 1:
        labeledSizes = KCGComponent(
            labeledSizesInput.selection(0).entity.component)
    else:
        labeledSizes = None

    # Create new assembly component
    design = adsk.fusion.Design.cast(app.activeProduct)
    trans = adsk.core.Matrix3D.create()
    layoutOccurrence = design.rootComponent.occurrences.addNewComponent(trans)
    layout = layoutOccurrence.component
    layout.name = config.COMPONENT_NAME_LAYOUT

    # Generate body and move to position
    notFound = []
    for position in positions:
        wasSizeFound = generateBodyAtPosition(
            position,
            sizes,
            labeledSizes,
            layout,
            1.9,  # TODO GUI Value!
            -1.9)
        if not wasSizeFound:
            notFound.append(position)
        # Call doEvents to give Fusion 360 a chance to react.
        adsk.doEvents()

    # Logging if a size was not found
    if int(len(notFound)) > 1:
        futil.log(f'{CMD_NAME} sizes not found for positions: ' +
                  '; '.join(map(str, notFound)))


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
    args.areInputsValid = True


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []


def generateBodyAtPosition(
        position: KLEPosition,
        sizes: KCGComponent,
        labeledSizes: KCGComponent,
        layoutComponent: adsk.fusion.Component,
        spacing1Ux,
        spacing1Uy):
    size = None
    if labeledSizes is not None:
        size = labeledSizes.findLabeledSize(
            position.sizeToInt(),
            position.label,
            position.row)
        if size is None:
            size = labeledSizes.findLabeledSize(
                position.sizeToInt(),
                position.label)
    if size is None:
        size = sizes.findSize(
            position.sizeToInt(),
            position.row)
    if size is None:
        size = sizes.findSize(
            position.sizeToInt())
    if size is None:
        return False
    # Calculate Position
    transform = adsk.core.Matrix3D.create()
    xMove = position.x * spacing1Ux + ((position.width - 1)/2) * spacing1Ux
    yMove = position.y * spacing1Uy + ((position.height - 1)/2) * spacing1Uy
    if xMove != 0 or yMove != 0:
        vector = adsk.core.Vector3D.create(xMove, yMove, 0.0)
        # transform.setToIdentity
        transform.translation = vector

    copyCapOccurrence = layoutComponent.occurrences.addExistingComponent(
        size,
        transform)

    return True


def findSizeComponentWithLabel(sizeName, label, sizeOccurrenceList):
    # Either it is the beginning of the string or there is something else than a number in front
    namePattern = re.compile('(?:[^\d]|\A)'+sizeName)
    for oo in range(sizeOccurrenceList.count):
        occurrence = sizeOccurrenceList.item(oo)
        if namePattern.search(occurrence.name) is not None:
            return occurrence.component

    return None


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