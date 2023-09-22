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

class CreateSizesExtrudeValues:
    def __init__(
            self, 
            inputs: adsk.core.CommandInputs):
        prefixInput: adsk.core.StringValueCommandInput = inputs.itemById('prefix')
        self.namePrefix:str = prefixInput.value

        rowInput: adsk.core.DropDownCommandInput = inputs.itemById('row')
        selectedRow = rowInput.selectedItem.name
        self.row:str = ''
        if selectedRow != 'none':
            self.row = selectedRow

        spacing1UInput: adsk.core.ValueCommandInput = inputs.itemById('spacing1U')
        self.spacing1U:float= spacing1UInput.value

        leftInput: adsk.core.SelectionCommandInput = inputs.itemById('left')
        self.left:adsk.fusion.BRepBody = leftInput.selection(0).entity
        
        rightInput: adsk.core.SelectionCommandInput = inputs.itemById('right')
        self.right:adsk.fusion.BRepBody = rightInput.selection(0).entity

        connectInput: adsk.core.SelectionCommandInput = inputs.itemById('connect')
        self.connect:adsk.core.Base = connectInput.selection(0).entity

        stemInput: adsk.core.SelectionCommandInput = inputs.itemById('stem')
        self.stem:adsk.fusion.BRepBody = None
        if stemInput.selectionCount == 1:
            self.stem:adsk.fusion.BRepBody = stemInput.selection(0).entity

        tableInput: adsk.core.TableCommandInput = inputs.itemById('sizes')
        self.sizes = []
        for tabelRow in range(tableInput.rowCount):
            sizeInput: adsk.core.IntegerSpinnerCommandInput = tableInput.getInputAtPosition(
                tabelRow, 0)
            self.sizes.append(sizeInput.value) 
        
        sizesInput: adsk.core.SelectionCommandInput = inputs.itemById('existingAssembly')
        self.parentComponent = None
        if sizesInput.selectionCount == 1:
            sizesOccurrence = sizesInput.selection(0).entity
            self.parentComponent = sizesOccurrence.component

    def areValid(self) -> bool:
        areValid = True
        areValid &= self.left is not None
        areValid &= self.right is not None
        areValid &= self.connect is not None
        areValid &= self.sizes.count() > 0 
        areValid &= self.spacing1U is not None and self.spacing1U != 0.0
        return areValid

class SingleSizeKeycapExtrudeGenerator:
    def __init__(
            self, 
            size:int, 
            row:str = ''):
        self.size:int = size
        self.row:str = row
        self.left:adsk.fusion.BRepBody = None
        self.right:adsk.fusion.BRepBody = None
        self.connect:adsk.core.Base = None
        self.stem:adsk.fusion.BRepBody = None
        self.parentComponent:adsk.fusion.Component = None
        self.namePrefix:str = ''
        self.spacing1U:float = None

    def __init__(
            self,
            size:int,
            values:CreateSizesExtrudeValues,
            parent:adsk.fusion.Component=None):
        self.size:int = size
        self.row:str = values.row
        self.left:adsk.fusion.BRepBody = values.left
        self.right:adsk.fusion.BRepBody = values.right
        self.connect:adsk.core.Base = values.connect
        self.stem:adsk.fusion.BRepBody = values.stem
        self.namePrefix:str = values.namePrefix
        self.spacing1U:float = values.spacing1U
        if parent is None: 
            self.parentComponent:adsk.fusion.Component = values.parentComponent
        else:
            self.parentComponent:adsk.fusion.Component = parent

    def generate(self):
        features = []
        # First delete any component with the same name
        nameToken = []
        if self.namePrefix:
            nameToken.append(self.namePrefix)
            sizeName = SizeNameFormat.formatRowSizeName(self.row, self.size)
        else:
            sizeName = SizeNameFormat.formatSizeName(self.size)
        nameToken.append(sizeName)
        componentName = '_'.join(map(str, nameToken))
        # Delete present components with same name (= always override) => TODO: Implement Body Update
        for occurrence in self.parentComponent.allOccurrences:
            if occurrence.name.startswith(componentName):
                occurrence.deleteMe()
        # New component for the keycap size
        trans = adsk.core.Matrix3D.create()
        occ = self.parentComponent.occurrences.addNewComponent(trans)
        sizeComp = occ.component
        sizeComp.name = componentName

        distance = (self.size/100-1)*self.spacing1U

        if self.size > 100:
            extrusionInput = sizeComp.features.extrudeFeatures.createInput(
                self.connect, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            extrusionDistance = adsk.core.ValueInput.createByReal(distance)
            extrusionInput.setDistanceExtent(False, extrusionDistance)
            extrusion = sizeComp.features.extrudeFeatures.add(extrusionInput)
            features.append(extrusion)
            connection = extrusion.bodies.item(0)

        copyLeftFeature = sizeComp.features.copyPasteBodies.add(self.left)
        copyLeft = copyLeftFeature.bodies.item(0)
        features.append(copyLeft)
        copyRightFeature = sizeComp.features.copyPasteBodies.add(self.right)
        copyRight = copyRightFeature.bodies.item(0)
        features.append(copyRight)

        moveFeatures = sizeComp.features.moveFeatures
        if self.size > 100:
            translateBodyX(connection, -distance/2, moveFeatures, features)
            translateBodyX(copyLeft, -distance/2, moveFeatures, features)
            translateBodyX(copyRight, distance/2, moveFeatures, features)

        combineFeatures = sizeComp.features.combineFeatures
        combineBodies = adsk.core.ObjectCollection.create()
        if self.size > 100:
            combineBodies.add(copyLeft)
        combineBodies.add(copyRight)
        if self.stem is not None:
            copyStemFeature = sizeComp.features.copyPasteBodies.add(self.stem)
            copyStem = copyStemFeature.bodies.item(0)
            combineBodies.add(copyStem)
        if self.size > 100:
            combineInput: adsk.fusion.CombineFeatureInput = combineFeatures.createInput(
                connection, combineBodies)
        else:
            combineInput: adsk.fusion.CombineFeatureInput = combineFeatures.createInput(
                copyLeft, combineBodies)
        combineInput.isNewComponent = False
        combineInput.isKeepToolBodies = False
        combineInput.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
        combineFeature = combineFeatures.add(combineInput)
        features.append(combineFeature)
        combineFeature.bodies.item(0).name = sizeComp.name

        return features


# This event handler is called when the user clicks the OK button in the command dialog or
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME} Command Execute Event')

    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs
  
    values = CreateSizesExtrudeValues(inputs)
    futil.log(f'{CMD_NAME} creating sizes: ' + '; '.join(map(str, values.sizes)))

    affixes = [config.COMPONENT_NAME_SIZES]
    if values.namePrefix.value:
        affixes.append(values.namePrefix.value)

    parentComponent = values.parentComponent
    if parentComponent is None:
        # Create new assembly component
        design = adsk.fusion.Design.cast(app.activeProduct)
        trans = adsk.core.Matrix3D.create()
        occ = design.rootComponent.occurrences.addNewComponent(trans)
        # Get the associated component.
        parentComponent = occ.component
        parentComponent.name = '_'.join(map(str, affixes))

    for size in values.sizes:
        generator = SingleSizeKeycapExtrudeGenerator(
            size, 
            values, 
            parentComponent)
        generator.generate()
        # Call doEvents to give Fusion 360 a chance to react.
        adsk.doEvents()


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    inputs = args.command.commandInputs
    '''
    # Currently even just creating a single keycap seems way too performance expensive
    values = CreateSizesExtrudeValues(inputs)
    design = adsk.fusion.Design.cast(app.activeProduct)
    SingleSizeKeycapExtrudeGenerator(200, values, design.activeComponent).generate()
    '''
    args.isValidResult = False


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs
    # Button click handling for the table buttons
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
    inputs = args.inputs
    values = CreateSizesExtrudeValues(inputs)
    args.areInputsValid = values.areValid()


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []

def translateBodyX(body, distance, moveFeatures, features):
    vector = adsk.core.Vector3D.create(distance, 0.0, 0.0)
    transform = adsk.core.Matrix3D.create()
    transform.setToIdentity
    transform.translation = vector
    bodies = adsk.core.ObjectCollection.create()
    bodies.add(body)
    moveInput = moveFeatures.createInput(bodies, transform)
    moveFeature = moveFeatures.add(moveInput)
    features.append(moveFeature)
