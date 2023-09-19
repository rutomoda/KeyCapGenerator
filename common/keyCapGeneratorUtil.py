from __future__ import annotations
from adsk.fusion import Component
from adsk.core import Matrix3D
import re
from .. import config


class KCGComponent:
    '''Provides some common functions for component handling especially in regards to naming conventions'''

    def __init__(self, component: Component) -> None:
        self.component = component

    def findSize(self, size: int, row: str = '') -> Component:
        if row:
            sizeName = SizeNameFormat.formatRowSizeName(row, size)
        else:
            sizeName = SizeNameFormat.formatSizeName(size)
        return self.findComponentWithLabel(sizeName)

    def findLabeledSize(self, size: int, label: str, row: str = '') -> Component:
        if row:
            sizeName = SizeNameFormat.formatLabeledRowSizeName(
                row,
                size,
                label)
        else:
            sizeName = SizeNameFormat.formatLabeledSizeName(size, label)
        return self.findComponentWithLabel(sizeName)

    def findComponentWithLabel(self, sizeName: str):
        sizeName = sizeName.replace('+', '\\+')
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

    def setSizeName(self, size: int) -> None:
        self.component.name = SizeNameFormat.formatSizeName(size)

    def setLabeledSizeName(self, size: int, label: str) -> None:
        self.component.name = SizeNameFormat.formatLabeledSizeName(size, label)

    def createChild(self, name: str = None) -> Component:
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
