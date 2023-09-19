import json
import copy
import re


class KLEPosition:
    '''The absolute position of a keycap, calculated from the KLE raw data'''

    def __init__(self) -> None:
        self.row = ''
        self.x = 0
        self.y = 0
        self.width = 1
        self.height = 1
        self.label = ''
        self.rotation = 0
        self.rotationX = 0
        self.rotationY = 0

    def incrementXresetWidthAndHeight(self):
        '''
        Width and height only ever get configured for one keycap at a time so they need to be reset 
        when going to the next.'''
        self.x += self.width
        self.width = 1
        self.height = 1

    def __str__(self):
        return str(self.__dict__)

    def sizeToInt(self) -> int:
        return int(self.width * 100)


class KLE:
    '''Manages the conversion of the GUI input into KLEPositions'''

    def __init__(self,
                 kleGuiRawText: str) -> None:
        '''Takes the raw copy-paste-string from KLE and makes it usable. Note that the raw string is NOT JSON compliant.'''
        self.kleJson = self.fixKLERaw2Json(kleGuiRawText)

    def fixKLERaw2Json(self,
                       kleGuiRawText):
        '''Converts raw KLE text into usable JSON'''
        enclosedRaw = f'[{kleGuiRawText}]'
        doubleQuotedProperties = re.sub(
            '([a-z]?[a-z0-9]):', '"\\1":', enclosedRaw)
        return doubleQuotedProperties

    def getKLEPostions(self) -> list[KLEPosition]:
        '''Calculates the absolute KLEPositions from the KLE data'''
        rows = json.loads(self.kleJson)
        currentPosition = KLEPosition()
        positions = []
        for rowNum, row in enumerate(rows):
            currentPosition.row = str(rowNum)
            for item in row:
                if isinstance(item, str):
                    labeledPosition = copy.copy(currentPosition)
                    labeledPosition.label = item
                    positions.append(labeledPosition)
                    currentPosition.incrementXresetWidthAndHeight()
                if isinstance(item, dict):
                    if 'x' in item:
                        currentPosition.x += item['x']
                    if 'y' in item:
                        currentPosition.y += item['y']
                    if 'w' in item:
                        currentPosition.width = item['w']
                    if 'h' in item:
                        currentPosition.height = item['h']
                    if 'rx' in item:
                        currentPosition.rotationX = item['rx']
                    if 'ry' in item:
                        currentPosition.rotationY = item['ry']
                    if 'r' in item:
                        currentPosition.rotation = item['r']
            currentPosition.x = 0
            currentPosition.y += 1
        return positions
