from __future__ import annotations
from adsk.fusion import Component, CustomFeatureDefinition, Timeline, BRepBody, MoveFeature, MoveFeatures, Occurrence
from adsk.core import Matrix3D, ObjectCollection, Vector3D, ValueInput
import re
from .. import config
from ..config import KCG_ID
from ..lib import fusion360utils as futil

class KCGCommand:
    '''Common functions for feature registration'''
    def __init__(
            self, 
            kcgId:KCG_ID, 
            name:str, 
            description:str): 
        self.kcgId:KCG_ID = kcgId
        self.editId = kcgId.id + '-edit'
        self.featureId = kcgId.id + '-feature'
        self.name:str = name
        self.description: str = description
        self.isPromoted: bool = True
        self.workspaceId: str = config.WORKSPACE_ID
        self.panelId: str = config.PANEL_ID
        self.featureDefinition: CustomFeatureDefinition = None
        self.commandCreatedCallback = None
        self.editCreatedCallback = None
        self.computeCallback = None

    def start(
            self,
            ui,
            iconFolder='') -> None:
        # Create a command Definition.
        commandDefinition = ui.commandDefinitions.addButtonDefinition(
            self.kcgId.id, 
            self.name, 
            self.description, 
            iconFolder)

        # Define an event handler for the command created event. It will be called when the button is clicked.
        futil.add_handler(
            commandDefinition.commandCreated, 
            self.commandCreatedCallback)

        # ******** Add a button into the UI so the user can run the command. ********
        # Get the target workspace the button will be created in.
        workspace = ui.workspaces.itemById(self.workspaceId)
        # Get the panel the button will be created in.
        panel = workspace.toolbarPanels.itemById(self.panelId)
        # Create the button command control in the UI after the specified existing command.
        control = panel.controls.addCommand(
            commandDefinition, 
            self.kcgId.besideId, 
            False)
        # Specify if the command is promoted to the main toolbar.
        control.isPromoted = self.isPromoted

        editDefinition = ui.commandDefinitions.addButtonDefinition(
            self.editId, 
            'Edit ' + self.name, 
            'Edits ' + self.name, 
            '')

        # Define an event handler for the edit command created event. It will be called when the button is clicked.
        futil.add_handler(
            editDefinition.commandCreated, 
            self.editCreatedCallback) 
        
        # Define a new custom feature definition (does not need to be deleted, returns the old one if already created)
        self.featureDefinition = CustomFeatureDefinition.create(
            self.featureId,
            self.name,
            iconFolder)
        self.featureDefinition.editCommandId = editDefinition.id
        if self.computeCallback:
            self.featureDefinition.customFeatureCompute.add(self.computeCallback)
    
    def stop(
            self, 
            ui) -> None:
        # Get the UI elements for this command
        workspace = ui.workspaces.itemById(self.workspaceId)
        panel = workspace.toolbarPanels.itemById(self.panelId)

        # Delete the button command control
        commandControl = panel.controls.itemById(self.kcgId.id)
        if commandControl:
            commandControl.deleteMe()

        # Delete the command definition
        commandDefinition = ui.commandDefinitions.itemById(self.kcgId.id)
        if commandDefinition:
            commandDefinition.deleteMe()

        # Delete the edit definition
        editDefinition = ui.commandDefinitions.itemById(self.editId)
        if editDefinition:
            editDefinition.deleteMe()

class KCGCustomFeatureParameter:
    def __init__(
            self, 
            paramId: str, 
            label: str, 
            value: ValueInput, 
            units: str, 
            isVisible: bool=True) -> None:
        self.id: str = paramId
        self.label: str = label
        self.value: ValueInput = value
        self.units: str = units
        self.isVisible: bool = isVisible

class KCGCustomDependencyParameter:
    def __init__(
            self,
            paramId: str,
            entity) -> None:
        self.id: str = paramId
        self.entity = entity

class KCGCustomFeature:
    OCCURRENCE_TYPE = Occurrence.classType()
    def __init__(
            self,
            featureDefinition: CustomFeatureDefinition,
            timeline: Timeline,
            featureComponent: Component) -> None:
        self.timeline: Timeline = timeline
        self.featureComponent: Component = featureComponent
        self.executionTimelineStartIndex: int = None
        self.featureDefinition: CustomFeatureDefinition = featureDefinition
        self.parameters: list[KCGCustomFeatureParameter] = []
        self.dependencies: list[KCGCustomDependencyParameter] = []

    def startExecution(self) -> None:
        self.executionTimelineStartIndex = self.timeline.count

    def addParameter(self,
            paramId: str, 
            label: str, 
            value: ValueInput, 
            units: str, 
            isVisible: bool=True) -> None:
        self.parameters.append(
            KCGCustomFeatureParameter(
                paramId, 
                label, 
                value, 
                units, 
                isVisible))

    def addDependency(self,
            paramId: str,
            entity) -> None:
        self.dependencies.append(
            KCGCustomDependencyParameter(
                paramId,
                entity))

    def endExecution(
            self) -> None:
        endIndex = self.timeline.count - 1
        startIndex = self.executionTimelineStartIndex
        startEntity = self.timeline.item(startIndex).entity
        while startEntity.objectType == self.OCCURRENCE_TYPE and startIndex < endIndex:
           startIndex += 1
           startEntity = self.timeline.item(startIndex).entity

        endEntity = self.timeline.item(endIndex).entity
        
        # Custom feature does not work with Occurences atm
        if startEntity.objectType != self.OCCURRENCE_TYPE and endEntity != self.OCCURRENCE_TYPE:
            customFeatures = self.featureComponent.features.customFeatures
            featureInput = customFeatures.createInput(self.featureDefinition)
            featureInput.setStartAndEndFeatures(
                startEntity,
                endEntity)  
            for parameter in self.parameters:
                featureInput.addCustomParameter(
                    parameter.id,
                    parameter.label,
                    parameter.value,
                    parameter.units,
                    parameter.isVisible)
            for dependency in self.dependencies:
                featureInput.addDependency(
                    dependency.id, 
                    dependency.entity)
            customFeatures.add(featureInput)

class MoveUtil:
    @staticmethod
    def translateBodyX(
        body:BRepBody, 
        distance:float, 
        moveFeatures:MoveFeatures) -> MoveFeature:
        vector = Vector3D.create(distance, 0.0, 0.0)
        transform = Matrix3D.create()
        transform.setToIdentity
        transform.translation = vector
        bodies = ObjectCollection.create()
        bodies.add(body)
        moveInput = moveFeatures.createInput(bodies, transform)
        return moveFeatures.add(moveInput)
            

class KCGComponent:
    '''Provides some common functions for component handling especially in regards to naming conventions'''

    def __init__(self, 
            component: Component) -> None:
        self.component = component

    def findSize(self, 
            size: int, 
            row: str = '') -> Component:
        if row:
            sizeName = SizeNameFormat.formatRowSizeName(row, size)
        else:
            sizeName = SizeNameFormat.formatSizeName(size)
        return self.findComponentWithLabel(sizeName)

    def findLabeledSize(self, 
            size: int, 
            label: str, 
            row: str = '') -> Component:
        if row:
            sizeName = SizeNameFormat.formatLabeledRowSizeName(
                row,
                size,
                label)
        else:
            sizeName = SizeNameFormat.formatLabeledSizeName(size, label)
        return self.findComponentWithLabel(sizeName)

    def findComponentWithLabel(self, 
            sizeName: str):
        sizeName = re.escape(sizeName)
        if sizeName.startswith('R'):
            # Either it is the beginning of the string or there is something else than a number in front
            namePattern = re.compile(f'(_|\A){sizeName}(\Z|:)')
        else:
            # Either it is the beginning of the string or there is something else than a number in front
            namePattern = re.compile(f'(?:[^\d]|\A){sizeName}(\Z|:)')
        sizeOccurrenceList = self.component.occurrences.asList
        for oo in range(sizeOccurrenceList.count):
            occurrence = sizeOccurrenceList.item(oo)
            if namePattern.search(occurrence.name) is not None:
                return occurrence.component

        return None

    def setSizeName(self, 
            size: int) -> None:
        self.component.name = SizeNameFormat.formatSizeName(size)

    def setLabeledSizeName(self, 
            size: int, 
            label: str) -> None:
        self.component.name = SizeNameFormat.formatLabeledSizeName(size, label)

    def createChild(self, 
            name: str = None) -> Component:
        transform = Matrix3D.create()
        occurrence = self.component.occurrences.addNewComponent(transform)
        child = occurrence.component
        if name is not None:
            child.name = name
        return child

    def createKCGChild(self) -> KCGComponent:
        return KCGComponent(self.createChild())


class SizeNameFormat:
    @staticmethod
    def formatSizeName(size: int) -> str:
        return config.KEYCAP_SIZE_FORMAT.format(
            int(size/100), size % 100)

    @staticmethod
    def formatLabeledSizeName(
            size: int,
            label: str) -> str:
        return config.KEYCAP_LABELED_SIZE_FORMAT.format(
            int(size/100),
            size % 100, label)

    @staticmethod
    def formatRowSizeName(
            row: str,
            size: int) -> str:
        return config.KEYCAP_ROW_SIZE_FORMAT.format(
            row,
            int(size/100),
            size % 100)

    @staticmethod
    def formatLabeledRowSizeName(
            row: str,
            size: int,
            label: str) -> str:
        return config.KEYCAP_LABELED_ROW_SIZE_FORMAT.format(
            row,
            int(size/100),
            size % 100,
            label)

    @staticmethod
    def appendLabel(
            name: str,
            label: str) -> str:
        return name + '+' + label
