import adsk.core
import os
import re
from ...lib import fusion360utils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_addStems'
CMD_NAME = 'KCG: Add Stabilizer Stems'
CMD_Description = 'Add stabilizer stems to the keycap bodies'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = config.WORKSPACE_ID
PANEL_ID = config.PANEL_ID
COMMAND_BESIDE_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_createSizesExtrude'

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

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    sizesSelect = inputs.addSelectionInput(
        'sizes', 'Size assembly', 'The component containing all the generated sizes. Size matching is done by name, e.g.: "*2_25U*" will be used for 2.25U.')
    sizesSelect.setSelectionLimits(1, 1)
    sizesSelect.addSelectionFilter(adsk.core.SelectionCommandInput.Occurrences)

    stemSelect = inputs.addSelectionInput(
        'stem', 'Stem Body', 'The body for the stabilizer stems')
    stemSelect.setSelectionLimits(1, 1)
    stemSelect.addSelectionFilter(adsk.core.SelectionCommandInput.SolidBodies)

    offsetTableInput = inputs.addTableCommandInput(
        'offsets', 'Offsets from center', 3, '2:2:1')
    defaultOffsets = config.STEM_OFFSETS
    # sizesTableInput.minimumVisibleRows = len(defaultSizes) # doesnt work for some reason
    for size, offset in defaultOffsets.items():
        addRowToOffsetsTable(offsetTableInput, size, offset)

    # Add inputs into the table.
    addButtonInput = inputs.addBoolValueInput(
        'offsetAdd', 'Add', False, '', True)
    offsetTableInput.addToolbarCommandInput(addButtonInput)
    deleteButtonInput = inputs.addBoolValueInput(
        'offsetDelete', 'Delete', False, '', True)
    offsetTableInput.addToolbarCommandInput(deleteButtonInput)
    clearButtonInput = inputs.addBoolValueInput(
        'offsetClear', 'Clear', False, '', True)
    offsetTableInput.addToolbarCommandInput(clearButtonInput)

    # TODO Connect to the events that are needed by this command.
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


_rowNumber = 0
# Adds a new row to the table.


def addRowToOffsetsTable(tableInput, size=200, offset=1.6):
    global _rowNumber
    # Get the CommandInputs object associated with the parent command.
    cmdInputs = adsk.core.CommandInputs.cast(tableInput.commandInputs)
    sizeInput = cmdInputs.addIntegerSpinnerCommandInput(
        'size{}'.format(_rowNumber), 'Size', 101, 9999, 25, int(size))
    offsetInput = cmdInputs.addValueInput('offset{}'.format(_rowNumber), 'Offset', 'mm',
                                          adsk.core.ValueInput.createByReal(offset))
    symmetricInput = cmdInputs.addBoolValueInput(
        'symmetric{}'.format(_rowNumber), 'Symmetric', True, '', True)
    row = tableInput.rowCount
    tableInput.addCommandInput(sizeInput, row, 0)
    tableInput.addCommandInput(offsetInput, row, 1)
    tableInput.addCommandInput(symmetricInput, row, 2)
    _rowNumber = _rowNumber+1


# This event handler is called when the user clicks the OK button in the command dialog or
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')
    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs
    # Read inputs
    stemInput: adsk.core.SelectionCommandInput = inputs.itemById('stem')
    stem = stemInput.selection(0).entity
    sizesInput: adsk.core.SelectionCommandInput = inputs.itemById('sizes')
    sizes = sizesInput.selection(0).entity
    tableInput: adsk.core.TableCommandInput = inputs.itemById('offsets')
    offsets = []
    for row in range(tableInput.rowCount):
        sizeInput: adsk.core.IntegerSpinnerCommandInput = tableInput.getInputAtPosition(
            row, 0)
        offsetInput: adsk.core.ValueCommandInput = tableInput.getInputAtPosition(
            row, 1)
        isSymmetricalInput: adsk.core.BoolValueCommandInput = tableInput.getInputAtPosition(
            row, 2)
        offsets.append([sizeInput.value, offsetInput.value,
                        isSymmetricalInput.value])
    # Select childOccurences
    design = adsk.fusion.Design.cast(app.activeProduct)
    sizeOccurrenceList = None
    if sizes == design.rootComponent:
        sizeOccurrenceList = sizes.occurrences.asList
    else:
        sizeOccurrenceList = sizes.childOccurrences
    # Add Stem
    notFound = []
    for size, offset, isSymmetrical in offsets:
        wasSizeFound = addStem(size,
                               offset,
                               isSymmetrical,
                               sizeOccurrenceList,
                               stem)
        if not wasSizeFound:
            notFound.append(size)
        # Call doEvents to give Fusion 360 a chance to react.
        adsk.doEvents()

    # Logging if a size was not found
    if int(len(notFound)) > 1:
        futil.log(f'{CMD_NAME} sizes not found: ' +
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

    if changed_input.id == 'offsetAdd':
        addRowToOffsetsTable(inputs.itemById('offsets'))

    if changed_input.id == 'offsetDelete':
        offsetsTable = inputs.itemById('offsets')
        if offsetsTable.selectedRow == -1:
            offsetsTable.deleteRow(offsetsTable.rowCount-1)
        else:
            offsetsTable.deleteRow(offsetsTable.selectedRow)

    if changed_input.id == 'offsetClear':
        offsetsTable = inputs.itemById('offsets')
        for row in range(offsetsTable.rowCount, 0, -1):
            offsetsTable.deleteRow(row-1)


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputs = args.inputs

    offsetsTableInput = inputs.itemById('offsets')
    if offsetsTableInput.rowCount == 0:
        args.areInputsValid = False
        futil.log(f'{CMD_NAME} invalid: offsets table empty')
        return

    args.areInputsValid = True


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []


def addStem(size, offset, isSymmetrical, sizeOccurrenceList, stem):
    sizeName = config.KEYCAP_SIZE_FORMAT.format(int(size/100), size % 100)
    sizeComponent = findSizeComponent(sizeName, sizeOccurrenceList)
    if sizeComponent is None:
        return False
    # Copy the stem body into the component
    copyStemFeature = sizeComponent.features.copyPasteBodies.add(stem)
    copyStem = copyStemFeature.bodies.item(0)
    # Translate stem to offset position
    moveFeatures = sizeComponent.features.moveFeatures
    translateBodyX(copyStem, offset, moveFeatures)
    # Begin combine feature
    combineFeatures = sizeComponent.features.combineFeatures
    combineBodies = adsk.core.ObjectCollection.create()
    combineBodies.add(copyStem)
    # Mirror the stem if symmetrical and add to combine
    if isSymmetrical:
        mirrorFeatures = sizeComponent.features.mirrorFeatures
        mirrorPlane = sizeComponent.yZConstructionPlane
        mirrorBodies = adsk.core.ObjectCollection.create()
        mirrorBodies.add(copyStem)
        mirrorInput = mirrorFeatures.createInput(mirrorBodies, mirrorPlane)
        mirrorFeature = mirrorFeatures.add(mirrorInput)
        combineBodies.add(mirrorFeature.bodies.item(0))
    # Execute combine
    combineInput: adsk.fusion.CombineFeatureInput = combineFeatures.createInput(
        sizeComponent.bRepBodies.item(0), combineBodies)
    combineInput.isNewComponent = False
    combineInput.isKeepToolBodies = False
    combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combineFeature = combineFeatures.add(combineInput)
    # Done
    return True


def translateBodyX(body, distance, moveFeatures):
    vector = adsk.core.Vector3D.create(distance, 0.0, 0.0)
    transform = adsk.core.Matrix3D.create()
    transform.setToIdentity
    transform.translation = vector
    bodies = adsk.core.ObjectCollection.create()
    bodies.add(body)
    moveInput = moveFeatures.createInput(bodies, transform)
    moveFeatures.add(moveInput)


def findSizeComponent(sizeName, sizeOccurrenceList):
    # Either it is the beginning of the string or there is something else than a number in front
    namePattern = re.compile('(?:[^\d]|\A)'+sizeName)
    for oo in range(sizeOccurrenceList.count):
        occurrence = sizeOccurrenceList.item(oo)
        if namePattern.search(occurrence.name) is not None:
            return occurrence.component

    return None
