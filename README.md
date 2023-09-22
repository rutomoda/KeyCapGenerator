# KeyCapGenerator
Python-based add-in for Autodesk Fusion360 offering commands to generate keycap models to cover keyboard layouts made with http://www.keyboard-layout-editor.com/

# How to install
Clone or download the repo into "C:\Users\\<user\>\AppData\Roaming\Autodesk\Autodesk Fusion 360\API\AddIns" and restart Fusion360. 

# Currently only available on the dev-branch
## Outstanding issues:
- Command Previews need to be implemented
- Command Edit Definition for the timeline needs to implemented (see: https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-FA7EF128-1DE0-4115-89A3-795551E2DEF2)
- Failure states need to be improved: Errors during most feature operations just kill the workflow mid-step leaving half finished components
- Command Validations need to be implemented
- Code is really messy and needs to be cleaned up and properly encapsulated
- Honor KLE legend positioning; right now all legends are centered, but can be offset in one single direction
- Support KLE row feature: keycap rows can be configured in KLE, might be useful to utilize, especially to generate GMK base set style layouts
- Support KLE rotation feature
- Offer more options for keycap generation (automatic lofting and scaling)
- Add "Cut switch cavity" command
- Make it easier to apply different appearances to legends and keycaps
- This may not probably support designs where XYZ uses the default Fusion360 orientation. Developed with X=left,right Y=front,back Z=up,down
- Multithread generating independent entities for each position

# How to use
The add-in provides its commands in the Solid Design space of Fusion360 under the Create group. You will need to provide the following:
- 1U model of your keycap with the switch cavity already cut into the bottom
- A distinct stem model compatible with the cut switch cavity
- A KLE layout

## Step 0: Model preparation
- The center of the 1U model bottom face must be the origin of the design; the bottom face should be on the XY-plane
- Move the stem model to the correct position in relation to the 1U body
- Use the "Split Body" command under "Modify" and split the 1U model with the YZ construction plane into a left and right half
- If you inserted components make sure all links are broken

## Step 1: Create Sizes with Extrude
Creates the configured keycap sizes by moving the 1U halves apart and extruding the profile between them. For this to work:
- Select left and right half bodies
- Select the face of the left half (due to orientation this needs to be this one right now) that should connect the two halves
- It is recommended to generate rowed profiles all into the same Sizes-Assembly: for this set the Row field and select the target component; row=0 is automapped to the top most row in KLE - automapping probably does not work with columnar staggered layouts or rotation

## Step 2: Add Stabilizer Stems
Adds stabilizer stems to the bigger keycaps. 

## Step 3: Initiate Label Sketches
Generates a component containing sketches for the keycap legends. This is seperate to allow for modification of those sketches after generation:
- Paste your KLE raw data. For this steps only the legends are read.
- Either select an existing construction plane or set the auto-generation parameters. The sketch plane dictates from where the legends are projected onto the keycap.
- Selecting an existing component allows to overwrite all matching sketches (for easier font tweaking)
  
Warning: due to font loading the mask takes forever to load!

## Step 4: Apply Labels to Keycaps
Extrudes the sketches from Step 3, then intersects them with the keycap model multiple times to create the embossing:
- Paste your KLE raw data. This time it is used to match the legend sketches with the keycap sizes.
- Select the components generated in step 1 and step 3.
- Sketch Extrude Distance: The legend sketch is extruded "into" the keycap. This distance needs to be set to a value, that the whole end face of the extrusion is within the keycap body!
  
This is a long operation. Depending on your computing power and number of keycaps to generate this will take several minutes.

## Step 5: Generate Layout
Uses the generated keycap models and copies them to a position defined by KLE:
- Paste your KLE raw data. This time it is used to determine the position of where what keycap needs to be moved to.
- Select the components generated in step 1 and step 4. The step 1 component is used as a fallback, if no corresponding model from step 4 is found.
Since this uses component occurrences it is rather quick and should only take a couple of seconds.

# fontTools
This add-in uses fontTools-4.42.1. Since Fusion360 uses its own Python installation the files for the library are copied into the lib-folder of this add-in.
