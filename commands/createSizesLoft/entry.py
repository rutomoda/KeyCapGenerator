import adsk.core
import os
from ...lib import fusion360utils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_createSizesLoft'
CMD_NAME = 'KCG: Create Sizes with Lofting'
CMD_Description = 'Create keycap sizes by lofting between to halfs'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = config.WORKSPACE_ID
PANEL_ID = config.PANEL_ID
COMMAND_BESIDE_ID = ''  # first command in suite

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

    # geometryGroupInput = inputs.addGroupCommandInput('geometry', 'Geometry')
    # geometryGroupInput.isExpanded = True
    # geometryInputs = geometryGroupInput.children

    leftSelect = inputs.addSelectionInput('left', 'Left', 'Left Half')
    leftSelect.setSelectionLimits(1, 1)
    leftSelect.addSelectionFilter("SolidBodies")

    rightSelect = inputs.addSelectionInput('right', 'Right', 'Right Half')
    rightSelect.setSelectionLimits(1, 1)
    rightSelect.addSelectionFilter("SolidBodies")

    connectSelect = inputs.addSelectionInput(
        'connect', 'Connect', 'Connecting Face')
    connectSelect.setSelectionLimits(1, 1)
    connectSelect.addSelectionFilter("PlanarFaces")
    connectSelect.addSelectionFilter("Profiles")

    sizingGroupInput = inputs.addGroupCommandInput('sizing', 'Sizing')
    sizingGroupInput.isExpanded = True
    sizingInputs = sizingGroupInput.children

    spacing1UInput = sizingInputs.addValueInput(
        'spacing1U', '1U Spacing', 'mm', adsk.core.ValueInput.createByReal(1.9))
    spacing1UInput.minimumValue = 0
    spacing1UInput.isMinimumValueInclusive = False

    sizesTableInput = sizingInputs.addTableCommandInput(
        'sizes', 'Sizes in U', 1, '1')
    defaultSizes = [125, 150, 175, 200, 225, 275, 300, 600, 625, 700]
    # sizesTableInput.minimumVisibleRows = len(defaultSizes) # doesnt work for some reason
    for size in defaultSizes:
        addRowToSizesTable(sizesTableInput, size)

    # Add inputs into the table.
    addButtonInput = sizingInputs.addBoolValueInput(
        'sizeAdd', 'Add', False, '', True)
    sizesTableInput.addToolbarCommandInput(addButtonInput)
    deleteButtonInput = sizingInputs.addBoolValueInput(
        'sizeDelete', 'Delete', False, '', True)
    sizesTableInput.addToolbarCommandInput(deleteButtonInput)

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


def addRowToSizesTable(tableInput, size=200):
    global _rowNumber
    # Get the CommandInputs object associated with the parent command.
    cmdInputs = adsk.core.CommandInputs.cast(tableInput.commandInputs)
    spinnerInput = cmdInputs.addIntegerSpinnerCommandInput(
        'size{}'.format(_rowNumber), 'Size', 101, 9999, 25, int(size))
    tableInput.addCommandInput(spinnerInput, tableInput.rowCount, 0)
    _rowNumber = _rowNumber+1


# This event handler is called when the user clicks the OK button in the command dialog or
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')

    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs

    # Read inputs
    spacing1U: adsk.core.ValueCommandInput = inputs.itemById('spacing1U')
    leftInput: adsk.core.SelectionCommandInput = inputs.itemById('left')
    left = leftInput.selection(0).entity
    rightInput: adsk.core.SelectionCommandInput = inputs.itemById('right')
    right = rightInput.selection(0).entity
    connectInput: adsk.core.SelectionCommandInput = inputs.itemById('connect')
    connect = connectInput.selection(0).entity
    tableInput: adsk.core.TableCommandInput = inputs.itemById('sizes')
    sizes = []
    for row in range(tableInput.rowCount):
        sizeInput: adsk.core.IntegerSpinnerCommandInput = tableInput.getInputAtPosition(
            row, 0)
        sizes.append(sizeInput.value)
    futil.log(f'{CMD_NAME} creating sizes: ' + '; '.join(map(str, sizes)))

    design = adsk.fusion.Design.cast(app.activeProduct)

    for size in sizes:
        createSize(size,
                   spacing1U.value,
                   design.rootComponent,
                   left,
                   right,
                   connect)


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

    if changed_input.id == 'sizeAdd':
        addRowToSizesTable(inputs.itemById('sizes'))

    if changed_input.id == 'sizeDelete':
        sizesTable = inputs.itemById('sizes')
        if sizesTable.selectedRow == -1:
            sizesTable.deleteRow(sizesTable.rowCount-1)
        else:
            sizesTable.deleteRow(sizesTable.selectedRow)


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Validate Input Event')

    inputs = args.inputs

    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    spacing1Uinput = inputs.itemById('spacing1U')
    if spacing1Uinput is None or not spacing1Uinput.value > 0:
        args.areInputsValid = False
        futil.log(f'{CMD_NAME} invalid: spacing1U field empty')
        return

    sizesTableInput = inputs.itemById('sizes')
    if sizesTableInput.rowCount == 0:
        args.areInputsValid = False
        futil.log(f'{CMD_NAME} invalid: sizes table empty')
        return

    args.areInputsValid = True


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Destroy Event')

    global local_handlers
    local_handlers = []


def createSize(size, spacing1U, rootComp, left, right, connect):
    trans = adsk.core.Matrix3D.create()
    occ = rootComp.occurrences.addNewComponent(trans)
    # Get the associated component.
    newComp = occ.component
    newComp.name = "{}_{:02n}U".format(int(size/100), size % 100)

    distance = (size/100-1)*spacing1U

    extrusionInput = newComp.features.extrudeFeatures.createInput(connect,
                                                                  adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrusionDistance = adsk.core.ValueInput.createByReal(distance)
    extrusionInput.setDistanceExtent(False, extrusionDistance)
    extrusion = newComp.features.extrudeFeatures.add(extrusionInput)
    connection = extrusion.bodies.item(0)

    copyLeftFeature = newComp.features.copyPasteBodies.add(left)
    copyLeft = copyLeftFeature.bodies.item(0)
    copyRightFeature = newComp.features.copyPasteBodies.add(right)
    copyRight = copyRightFeature.bodies.item(0)

    moveFeatures = newComp.features.moveFeatures

    translateBodyX(connection, -distance/2, moveFeatures)
    translateBodyX(copyLeft, -distance/2, moveFeatures)
    translateBodyX(copyRight, distance/2, moveFeatures)

    combineFeatures = newComp.features.combineFeatures
    combineBodies = adsk.core.ObjectCollection.create()
    combineBodies.add(copyLeft)
    combineBodies.add(copyRight)
    combineInput: adsk.fusion.CombineFeatureInput = combineFeatures.createInput(
        connection, combineBodies)
    combineInput.isNewComponent = False
    combineInput.isKeepToolBodies = False
    combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combineFeature = combineFeatures.add(combineInput)
    combineFeature.bodies.item(0).name = newComp.name


def translateBodyX(body, distance, moveFeatures):
    vector = adsk.core.Vector3D.create(distance, 0.0, 0.0)
    transform = adsk.core.Matrix3D.create()
    transform.setToIdentity
    transform.translation = vector
    bodies = adsk.core.ObjectCollection.create()
    bodies.add(body)
    moveInput = moveFeatures.createInput(bodies, transform)
    moveFeatures.add(moveInput)
