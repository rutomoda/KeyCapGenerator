# Application Global Variables
# This module serves as a way to share variables across different
# modules (global variables).
import os
import sys

# Flag that indicates to run in Debug mode or not. When running in Debug mode
# more information is written to the Text Command window. Generally, it's useful
# to set this to True while developing an add-in and set it to False when you
# are ready to distribute it.
DEBUG = True

# Gets the name of the add-in from the name of the folder the py file is in.
# This is used when defining unique internal names for various UI elements
# that need a unique name. It's also recommended to use a company name as
# part of the ID to better ensure the ID is unique.
ADDIN_NAME = os.path.basename(os.path.dirname(__file__))
COMPANY_NAME = 'rutomoda'
LIB_FOLDER = os.path.dirname(__file__) + '/lib'
if not LIB_FOLDER in sys.path:
    sys.path.append(LIB_FOLDER)

# COMMON_FOLDER = os.path.dirname(__file__) + '/common'
# if not COMMON_FOLDER in sys.path:
#    sys.path.append(COMMON_FOLDER)

# Panel ID
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'

# See also: https://cdn.sparkfun.com/datasheets/Components/Switches/MX%20Series.pdf and https://deskthority.net/wiki/Space_bar_dimensions
STEM_OFFSETS = {
    200: 1.1938,  # = 0.94in/2
    225: 1.1938,
    275: 1.1938,
    300: 1.95,
    625: 5.0,
    700: 5.715
}

KEYCAP_SIZES = [100, 125, 150, 175, 200, 225, 275, 300, 625, 700]
MAX_ROW = 7

KEYCAP_SIZE_FORMAT = '{}_{:02n}U'
KEYCAP_LABELED_SIZE_FORMAT = KEYCAP_SIZE_FORMAT+'+{}'
KEYCAP_ROW_SIZE_FORMAT = 'R{}-' + KEYCAP_SIZE_FORMAT
KEYCAP_LABELED_ROW_SIZE_FORMAT = 'R{}-' + KEYCAP_LABELED_SIZE_FORMAT

DEFAULT_1U_SPACING = 1.9

COMPONENT_NAME_SIZES = 'KCG-Keycap-Sizes-Assembly'
COMPONENT_NAME_LAYOUT = 'KCG-Layout-Assembly'
COMPONENT_NAME_LEGENDS = 'KCG-Legend-Sketches-Assembly'
COMPONENT_NAME_LABELED = 'KCG-Labeled-Keycap-Assembly'

def toId(idTag:str) -> str: 
   return f'{COMPANY_NAME}_{ADDIN_NAME}_{idTag}'

class KCG_ID:
    def __init__(self, id:str, besideId:str=''):
        self.id:str = id
        self.besideId:str = id

CMD_CREATE_SIZES_EXTRUDE_ID = KCG_ID(
   toId('createSizesExtrude'))
CMD_ADD_STEMS_ID = KCG_ID(
    toId('addStems'),
    CMD_CREATE_SIZES_EXTRUDE_ID.id
)
CMD_INITIATE_LEGEND_SKETCHES_ID = KCG_ID(
    toId('initiateLegendSketches'),
    CMD_ADD_STEMS_ID.id
)
CMD_APPLY_LEGENDS_ID = KCG_ID(
    toId('applyLegendes'),
    CMD_INITIATE_LEGEND_SKETCHES_ID.id
)
CMD_GENERATE_LAYOUT_ID = KCG_ID(
    toId('generateLayout'),
    CMD_APPLY_LEGENDS_ID.id
)


