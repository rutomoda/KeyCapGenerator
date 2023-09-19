import adsk.core
import adsk.fusion
import os
from ...lib import fusion360utils as futil
from ... import config
from ...common.keyCapGeneratorUtil import SizeNameFormat


app = adsk.core.Application.get()
ui = app.userInterface


# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_createSizesExtrude'
CMD_NAME = 'KCG: Create Sizes with Extrude'
CMD_Description = 'Create keycap sizes by extruding between to 1U halfs'

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

    # TODO Validate only Alphnum char inputs
    inputs.addStringValueInput('prefix', 'Generation Name Prefix')
    rowInput = inputs.addDropDownCommandInput(
        'row', 'Row', adsk.core.DropDownStyles.TextListDropDownStyle)
    rowItems = rowInput.listItems
    rowItems.add("none", True)
    for rowNum in range(config.MAX_ROW):
        rowItems.add(str(rowNum), False)

    sizesSelect = inputs.addSelectionInput(
        'existingAssembly', 'Existing ' + config.COMPONENT_NAME_SIZES, 'Existing assembly to generate into')
    sizesSelect.setSelectionLimits(0, 1)
    sizesSelect.addSelectionFilter(adsk.core.SelectionCommandInput.Occurrences)

    geometryGroupInput = inputs.addGroupCommandInput('geometry', 'Geometry')
    geometryGroupInput.isExpanded = True
    geometryInputs = geometryGroupInput.children

    leftSelect = geometryInputs.addSelectionInput(
        'left', 'Left Half Body', 'The left half of the 1U keycap')
    leftSelect.setSelectionLimits(1, 1)
    leftSelect.addSelectionFilter(adsk.core.SelectionCommandInput.SolidBodies)

    rightSelect = geometryInputs.addSelectionInput(
        'right', 'Right Half Body', 'The right half of the 1U keycap')
    rightSelect.setSelectionLimits(1, 1)
    rightSelect.addSelectionFilter(adsk.core.SelectionCommandInput.SolidBodies)

    connectSelect = geometryInputs.addSelectionInput(
        'connect', 'Extrusion Face or Profile', 'Face or profile used to generate the connection between left and right half. Orientation matters!')
    connectSelect.setSelectionLimits(1, 1)
    connectSelect.addSelectionFilter(
        adsk.core.SelectionCommandInput.PlanarFaces)
    connectSelect.addSelectionFilter(adsk.core.SelectionCommandInput.Profiles)

    stemSelect = geometryInputs.addSelectionInput(
        'stem', 'Center Stem Body', 'Body for the center stem. Is optional, but recommended.')
    stemSelect.setSelectionLimits(0, 1)
    stemSelect.addSelectionFilter(adsk.core.SelectionCommandInput.SolidBodies)

    sizingGroupInput = inputs.addGroupCommandInput('sizing', 'Sizing')
    sizingGroupInput.isExpanded = True
    sizingInputs = sizingGroupInput.children

    spacing1UInput = sizingInputs.addValueInput(
        'spacing1U', '1U Spacing', 'mm', adsk.core.ValueInput.createByReal(config.DEFAULT_1U_SPACING))
    spacing1UInput.minimumValue = 0
    spacing1UInput.isMinimumValueInclusive = False

    sizesTableInput = sizingInputs.addTableCommandInput(
        'sizes', 'Generated Sizes in U', 1, '1')
    defaultSizes = config.KEYCAP_SIZES
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
    clearButtonInput = inputs.addBoolValueInput(
        'sizeClear', 'Clear', False, '', True)
    sizesTableInput.addToolbarCommandInput(clearButtonInput)

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
        'size{}'.format(_rowNumber), 'Size', 100, 9999, 25, int(size))
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
    prefix: adsk.core.StringValueCommandInput = inputs.itemById('prefix')
    rowInput: adsk.core.DropDownCommandInput = inputs.itemById('row')
    selectedRow = rowInput.selectedItem.name
    row = ''
    if selectedRow != 'none':
        row = selectedRow
    spacing1U: adsk.core.ValueCommandInput = inputs.itemById('spacing1U')
    leftInput: adsk.core.SelectionCommandInput = inputs.itemById('left')
    left = leftInput.selection(0).entity
    rightInput: adsk.core.SelectionCommandInput = inputs.itemById('right')
    right = rightInput.selection(0).entity
    connectInput: adsk.core.SelectionCommandInput = inputs.itemById('connect')
    connect = connectInput.selection(0).entity
    stemInput: adsk.core.SelectionCommandInput = inputs.itemById('stem')
    if stemInput.selectionCount == 1:
        stem = stemInput.selection(0).entity
    else:
        stem = None
    tableInput: adsk.core.TableCommandInput = inputs.itemById('sizes')
    sizes = []
    for tabelRow in range(tableInput.rowCount):
        sizeInput: adsk.core.IntegerSpinnerCommandInput = tableInput.getInputAtPosition(
            tabelRow, 0)
        sizes.append(sizeInput.value)
    futil.log(f'{CMD_NAME} creating sizes: ' + '; '.join(map(str, sizes)))

    affixes = [config.COMPONENT_NAME_SIZES]
    if prefix.value:
        affixes.append(prefix.value)

    sizesInput: adsk.core.SelectionCommandInput = inputs.itemById(
        'existingAssembly')
    if sizesInput.selectionCount == 1:
        sizesOccurrence = sizesInput.selection(0).entity
        assemblyComponent = sizesOccurrence.component
    else:
        # Create new assembly component
        design = adsk.fusion.Design.cast(app.activeProduct)
        trans = adsk.core.Matrix3D.create()
        occ = design.rootComponent.occurrences.addNewComponent(trans)
        # Get the associated component.
        assemblyComponent = occ.component
        assemblyComponent.name = '_'.join(map(str, affixes))

    for size in sizes:
        createSize(size,
                   spacing1U.value,
                   assemblyComponent,
                   left,
                   right,
                   connect,
                   stem,
                   prefix.value,
                   row)
        # Call doEvents to give Fusion 360 a chance to react.
        adsk.doEvents()


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

    if changed_input.id == 'sizeClear':
        sizesTable = inputs.itemById('sizes')
        for row in range(sizesTable.rowCount, 0, -1):
            sizesTable.deleteRow(row-1)


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


def createSize(
        size: int,
        spacing1U,
        assemblyComponent: adsk.fusion.Component,
        left,
        right,
        connect,
        stem,
        prefix: str = '',
        row: str = ''):
    # First delete any component with the same name
    nameToken = []
    if prefix:
        nameToken.append(prefix)
    if row:
        sizeName = SizeNameFormat.formatRowSizeName(row, size)
    else:
        sizeName = SizeNameFormat.formatSizeName(size)
    nameToken.append(sizeName)
    componentName = '_'.join(map(str, nameToken))
    for occurrence in assemblyComponent.allOccurrences:
        if occurrence.name.startswith(componentName):
            occurrence.deleteMe()
    # New component for the keycap size
    trans = adsk.core.Matrix3D.create()
    occ = assemblyComponent.occurrences.addNewComponent(trans)
    sizeComp = occ.component
    sizeComp.name = componentName

    distance = (size/100-1)*spacing1U

    if size > 100:
        extrusionInput = sizeComp.features.extrudeFeatures.createInput(
            connect, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        extrusionDistance = adsk.core.ValueInput.createByReal(distance)
        extrusionInput.setDistanceExtent(False, extrusionDistance)
        extrusion = sizeComp.features.extrudeFeatures.add(extrusionInput)
        connection = extrusion.bodies.item(0)

    copyLeftFeature = sizeComp.features.copyPasteBodies.add(left)
    copyLeft = copyLeftFeature.bodies.item(0)
    copyRightFeature = sizeComp.features.copyPasteBodies.add(right)
    copyRight = copyRightFeature.bodies.item(0)

    moveFeatures = sizeComp.features.moveFeatures
    if size > 100:
        translateBodyX(connection, -distance/2, moveFeatures)
        translateBodyX(copyLeft, -distance/2, moveFeatures)
        translateBodyX(copyRight, distance/2, moveFeatures)

    combineFeatures = sizeComp.features.combineFeatures
    combineBodies = adsk.core.ObjectCollection.create()
    if size > 100:
        combineBodies.add(copyLeft)
    combineBodies.add(copyRight)
    if stem is not None:
        copyStemFeature = sizeComp.features.copyPasteBodies.add(stem)
        copyStem = copyStemFeature.bodies.item(0)
        combineBodies.add(copyStem)
    if size > 100:
        combineInput: adsk.fusion.CombineFeatureInput = combineFeatures.createInput(
            connection, combineBodies)
    else:
        combineInput: adsk.fusion.CombineFeatureInput = combineFeatures.createInput(
            copyLeft, combineBodies)
    combineInput.isNewComponent = False
    combineInput.isKeepToolBodies = False
    combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
    combineFeature = combineFeatures.add(combineInput)
    combineFeature.bodies.item(0).name = sizeComp.name


def translateBodyX(body, distance, moveFeatures):
    vector = adsk.core.Vector3D.create(distance, 0.0, 0.0)
    transform = adsk.core.Matrix3D.create()
    transform.setToIdentity
    transform.translation = vector
    bodies = adsk.core.ObjectCollection.create()
    bodies.add(body)
    moveInput = moveFeatures.createInput(bodies, transform)
    moveFeatures.add(moveInput)
