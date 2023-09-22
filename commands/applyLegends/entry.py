import adsk.core
import adsk.fusion
import os
import json
import re
import copy
import time
from ...lib import fusion360utils as futil
from ... import config
from ...common.keyboardLayoutEditor import KLEPosition, KLE
from ...common.keyCapGeneratorUtil import KCGComponent, SizeNameFormat, KCGCommand

app = adsk.core.Application.get()
ui = app.userInterface

kcgCommand = KCGCommand(
    config.CMD_APPLY_LEGENDS_ID, 
    'KCG: Apply Legends to Keycaps',
    'Applies the legend sketches to the sizes assembly')

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

# Executed when add-in is run.
def start():
    kcgCommand.editCreatedCallback = command_created
    kcgCommand.commandCreatedCallback = command_created
    kcgCommand.start(ui, ICON_FOLDER)

# Executed when add-in is stopped.
def stop():
    kcgCommand.stop(ui)

# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    inputs = args.command.commandInputs

    inputs.addTextBoxCommandInput(
        'kleRaw', 'KLE Raw Data', '["Q","W","E","R"],["A","S","D","F"]', 7, False)

    sizesSelect = inputs.addSelectionInput(
        'sizes', config.COMPONENT_NAME_SIZES, 'The Sizes Assembly')
    sizesSelect.setSelectionLimits(1, 1)
    sizesSelect.addSelectionFilter(
        adsk.core.SelectionCommandInput.Occurrences)

    labelsSelect = inputs.addSelectionInput(
        'labels', config.COMPONENT_NAME_LEGENDS, 'The Labels Assembly')
    labelsSelect.setSelectionLimits(1, 1)
    labelsSelect.addSelectionFilter(
        adsk.core.SelectionCommandInput.Occurrences)

    rowInput = inputs.addDropDownCommandInput(
        'row', 'Row', adsk.core.DropDownStyles.TextListDropDownStyle)
    rowItems = rowInput.listItems
    rowItems.add("none", False)
    rowItems.add("auto", True)
    for rowNum in range(config.MAX_ROW):
        rowItems.add(str(rowNum), False)

    initialExtrudeInput = inputs.addValueInput(
        'initialExtrude', 
        'Sketch Extrude Distance', 
        'mm', 
        adsk.core.ValueInput.createByReal(-0.55))
    embossDepthInput = inputs.addValueInput(
        'embossDepth', 
        'Emboss Depth', 
        'mm',
        adsk.core.ValueInput.createByReal(0.05))
    
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
    design = adsk.fusion.Design.cast(app.activeProduct)
    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs

    kleRawInput: adsk.core.TextBoxCommandInput = inputs.itemById('kleRaw')
    kle = KLE(kleRawInput.text)
    positions = kle.getKLEPostions()

    labelsInput: adsk.core.SelectionCommandInput = inputs.itemById('labels')
    labelsOccurrence = labelsInput.selection(0).entity
    labels = labelsOccurrence.component

    sizesInput: adsk.core.SelectionCommandInput = inputs.itemById('sizes')
    sizesOccurrence = sizesInput.selection(0).entity
    sizes = KCGComponent(sizesOccurrence.component)

    rowInput: adsk.core.DropDownCommandInput = inputs.itemById('row')
    selectedRow = rowInput.selectedItem.name
    row = ''
    if selectedRow != 'none':
        row = selectedRow

    initialExtrudeInput: adsk.core.ValueCommandInput = inputs.itemById('initialExtrude')
    initialExtrude = initialExtrudeInput.value

    embossDepthInput: adsk.core.ValueCommandInput = inputs.itemById('embossDepth')
    embossDepth = embossDepthInput.value

    featureComponent = design.activeComponent
    timeline = design.timeline
    kcgCommand.startExecution(timeline)

    trans = adsk.core.Matrix3D.create()
    labeledSizesOccurrence = design.rootComponent.occurrences.addNewComponent(
        trans)
    labeledSizes = labeledSizesOccurrence.component
    labeledSizes.name = config.COMPONENT_NAME_LABELED

    labelNotFound = []
    sizeNotFound = []
    labeledSizeComponents = []
    for position in positions:
        size = position.sizeToInt()
        if selectedRow == 'auto':
            row = position.row
        sketchName = position.label
        labelSketch = labels.sketches.itemByName(sketchName)
        if labelSketch is None:
            labelNotFound.append(position.label)
            continue
        labeledSizeComponent = createLabeledSize(
            size,
            labelSketch,
            row,
            sizes,
            labeledSizes)
        adsk.doEvents()
        if labeledSizeComponent is None:
            sizeNotFound.append(size)
        else:
            labeledSizeComponents.append(labeledSizeComponent)

    for labeledSizeComponent in labeledSizeComponents:
        embossLabel(
            labeledSizeComponent,
            initialExtrude,
            embossDepth)
        adsk.doEvents()

    if not labeledSizeComponents:
        labeledSizesOccurrence.deleteMe()

    kcgCommand.endExecution(
        timeline, 
        featureComponent),
    # TODO UI Output non found sizes, inform if nothing was created


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

    args.areInputsValid = True


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []


def createLabeledSize(
        size: int,
        labelSketch: adsk.fusion.Sketch,
        row: str,
        sizes: KCGComponent,
        labeledSizes: adsk.fusion.Component) -> adsk.fusion.Component:
    sizeComponent = sizes.findSize(size, row)
    if sizeComponent is None:
        return None
    sizeKeycap = sizeComponent.bRepBodies.item(0)

    trans = adsk.core.Matrix3D.create()
    occ = labeledSizes.occurrences.addNewComponent(trans)
    labeledSizeComponent = occ.component
    labeledSizeComponent.name = SizeNameFormat.appendLabel(
        sizeComponent.name,
        labelSketch.name)
    # Copy keycap body to component
    labeledSizeComponent.features.copyPasteBodies.add(
        sizeKeycap)

    trans = adsk.core.Matrix3D.create()
    occ = labeledSizeComponent.occurrences.addNewComponent(trans)
    labelComponent = occ.component
    labelComponent.name = labeledSizeComponent.name+'-Label'
    # Copy label sketch to component
    sketchObjects: adsk.core.ObjectCollection = getSketchAllEntities(
        labelSketch)
    referencePlane: adsk.fusion.ConstructionPlane = labelSketch.referencePlane
    copiedSketch: adsk.fusion.Sketch = labelComponent.sketches.add(
        referencePlane)
    trans = adsk.core.Matrix3D.create()
    labelSketch.copy(
        sketchObjects,
        trans,
        copiedSketch)
    copiedSketch.name = labelSketch.name
    copiedSketch.isLightBulbOn = False

    return labeledSizeComponent


def embossLabel(
        labeledSizeComponent: adsk.fusion.Component,
        initialExtrude,
        embossDepth):
    keycap = labeledSizeComponent.bRepBodies.item(0)
    labelComponent = labeledSizeComponent.occurrences.item(
        0).component
    labelSketch = labelComponent.sketches.item(0)

    for tryNum in range(10):
        try:
            # Gather sketch profiles
            profiles = adsk.core.ObjectCollection.create()
            sketchTexts: adsk.fusion.SketchTexts = labelSketch.sketchTexts
            sketchProfiles: adsk.fusion.Profiles = labelSketch.profiles
            if sketchTexts.count > 0:
                for oo in range(sketchTexts.count):
                    profiles.add(sketchTexts.item(oo))
            if sketchProfiles.count > 0:
                for oo in range(sketchProfiles.count):
                    profiles.add(sketchProfiles.item(oo))

            # Extrude sketch
            extrusionDistance = adsk.core.ValueInput.createByReal(
                initialExtrude)
            extrudeFeatures = labelSketch.parentComponent.features.extrudeFeatures
            extrudeFeature = extrudeFeatures.addSimple(
                profiles,
                extrusionDistance,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            # Add construction axis for later move direction based on extrudeFeature
            constructionAxes = labelComponent.constructionAxes
            moveDirectionInput = constructionAxes.createInput()
            startFace: adsk.fusion.BRepFace = extrudeFeature.startFaces.item(0)
            moveDirectionInput.setByPerpendicularAtPoint(
                startFace,
                startFace.pointOnFace)
            moveDirection = constructionAxes.add(
                moveDirectionInput)
            moveDirection.isLightBulbOn = False
            moveDirection.name = 'Emboss Move Direction'
        except:
            futil.log(f'extrude try {tryNum}')
            adsk.doEvents()
            time.sleep(0.1+0.009*tryNum*tryNum)

    # Subtract size body from label bodies
    subtractLabels = allBodiesFrom(labelComponent)
    combineFeatures = labelComponent.features.combineFeatures
    subtractKeycap = adsk.core.ObjectCollection.create()
    subtractKeycap.add(keycap)
    for subtractLabel in subtractLabels:
        subtractInput = combineFeatures.createInput(
            subtractLabel,
            subtractKeycap)
        subtractInput.isNewComponent = False
        subtractInput.isKeepToolBodies = True
        subtractInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        combineFeatures.add(subtractInput)

    # Move subtracted Label bodies to embossing depth
    moveBodies = allBodiesFrom(labelComponent)
    moveFeatures = labelComponent.features.moveFeatures
    moveInput = moveFeatures.createInput2(moveBodies)
    moveDirectionVector = moveDirection.geometry.direction
    # vector length is 1, which is 1cm and it points "upward"
    adjustedMoveDirectionVector = adsk.core.Vector3D.create(
        -moveDirectionVector.x*embossDepth,
        -moveDirectionVector.y*embossDepth,
        -moveDirectionVector.z*embossDepth)
    transform = adsk.core.Matrix3D.create()
    transform.translation = adjustedMoveDirectionVector
    moveInput.defineAsFreeMove(transform)
    # defineAsTranslateAlongEntity runs into an "invalid entity" exception for some reason
    # moveInput.defineAsTranslateAlongEntity(
    #    moveDirection,
    #    adsk.core.ValueInput.createByReal(embossDepth))
    moveFeatures.add(moveInput)

    combineFeatures = labelComponent.features.combineFeatures
    intersectKeycap = adsk.core.ObjectCollection.create()
    intersectKeycap.add(keycap)
    intersectLabels = allBodiesFrom(labelComponent)
    for intersectLabel in intersectLabels:
        intersectInput = combineFeatures.createInput(
            intersectLabel,
            intersectKeycap)
        intersectInput.isNewComponent = False
        intersectInput.isKeepToolBodies = True
        intersectInput.operation = adsk.fusion.FeatureOperations.IntersectFeatureOperation
        combineFeatures.add(intersectInput)

    # adsk.doEvents()
    # time.sleep(1)
    # Cut embossing into Size
    embossingLabels = allBodiesFrom(labelComponent)
    combineFeatures = labeledSizeComponent.features.combineFeatures
    embossCutInput = combineFeatures.createInput(
        keycap, embossingLabels)
    embossCutInput.isNewComponent = False
    embossCutInput.isKeepToolBodies = True
    embossCutInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combineFeatures.add(embossCutInput)


def allBodiesFrom(component: adsk.fusion.Component) -> adsk.core.ObjectCollection:
    allBodies = adsk.core.ObjectCollection.create()
    for body in component.bRepBodies:
        allBodies.add(body)
    return allBodies


def findSizeComponentWithLabel(sizeName, sizeOccurrenceList):
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


def getSketchAllEntities(
    skt: adsk.fusion.Sketch
) -> adsk.core.ObjectCollection:
    '''see: https://forums.autodesk.com/t5/fusion-360-api-and-scripts/how-to-duplicate-a-sketch-by-using-api/td-p/9804407'''
    objs = adsk.core.ObjectCollection.create()
    [objs.add(e) for e in skt.sketchPoints if not e.isReference]
    [objs.add(e) for e in skt.sketchCurves]
    [objs.add(e) for e in skt.sketchTexts]
    return objs
