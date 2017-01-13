#Author-Mike Fogel
#Description-

import itertools, traceback
import adsk.core, adsk.fusion

defaultBoneDiameter = '1mm'

# global set of event handlers to keep them referenced for the duration of the command
handlers = []
app = adsk.core.Application.get()
if app:
    ui = app.userInterface

product = app.activeProduct
design = adsk.fusion.Design.cast(product)


def createNewComponent():
    # Get the active design.
    rootComp = design.rootComponent
    allOccs = rootComp.occurrences
    newOcc = allOccs.addNewComponent(adsk.core.Matrix3D.create())
    return newOcc.component


def createSkeleton(targetBody, boneDiameter, parentComponent):

    planes = parentComponent.constructionPlanes
    axes = parentComponent.constructionAxes
    sketches = parentComponent.sketches
    sweeps = parentComponent.features.sweepFeatures
    revolves = parentComponent.features.revolveFeatures

    objCol = adsk.core.ObjectCollection.create()
    for edge in targetBody.edges:
        objCol.add(edge)

    for edge in targetBody.edges:
        planeInput = planes.createInput()
        planeInput.setByDistanceOnPath(edge, adsk.core.ValueInput.createByReal(0.5))
        plane = planes.add(planeInput)

        sketch = sketches.add(plane)
        sketch.sketchCurves.sketchCircles.addByCenterRadius(sketch.originPoint, boneDiameter/2)

        path = adsk.fusion.Path.create(edge, adsk.fusion.ChainedCurveOptions.noChainedCurves)
        profile = sketch.profiles.item(0)

        sweepInput = sweeps.createInput(profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        sweep = sweeps.add(sweepInput)
        sweepBody = sweep.bodies.item(0)

        for face in itertools.chain(sweep.startFaces, sweep.endFaces):
            axisLinePt = face.geometry.origin
            axisLineDirection = face.geometry.origin.vectorTo(face.vertices.item(0).geometry)
            axisLine = adsk.core.InfiniteLine3D.create(axisLinePt, axisLineDirection)

            axisInput = axes.createInput()
            axisInput.setByLine(axisLine)

            # TODO: FIXME
            # this raises an system error:
            # "Runtime Error: 3 : Environment is not supported
            axis = axes.add(axisInput)

            revolveInput = revolves.createInput(face, axis, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            revolveInput.createionOccurrence = sweepBody
            revolves.add(revolveInput)


class SkeletorizeCommandExecuteHandler(adsk.core.CommandEventHandler):

    def notify(self, args):
        try:
            unitsMgr = app.activeProduct.unitsManager
            command = args.firingEvent.sender
            inputs = command.commandInputs

            if inputs.count != 3:
                raise ValueError('Unexpected number of inputs: {}'.format(inputs.count))

            for input in inputs:
                if input.id == 'body':
                    targetBody = input.selection(0).entity
                elif input.id == 'boneDiameter':
                    boneDiameter = unitsMgr.evaluateExpression(input.expression, "mm")
                elif input.id == 'operation':
                    operation = input.selectedItem.name
                else:
                    raise ValueError('Unexpected input iud: {}'.format(input.id))

            # ensure our target has edges and such (ex: a sphere doesn't)
            if targetBody.edges.count == 0:
                raise ValueError('Target Body has no edges')

            # create a new component if requested
            if operation == 'New Body':
                parentComponent = design.activeComponent
            elif operation == 'New Component':
                parentComponent = createNewComponent()
            else:
                raise ValueError('Unexpected operation: {}'.format(operation))

            # do the real work
            createSkeleton(targetBody, boneDiameter, parentComponent)
            adsk.terminate()

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class SkeletorizeCommandDestroyHandler(adsk.core.CommandEventHandler):

    def notify(self, args):
        try:
            # when the command is done, terminate the script
            # this will release all globals which will remove all event handlers
            adsk.terminate()
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class SkeletorizeCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):

    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            onExecute = SkeletorizeCommandExecuteHandler()
            cmd.execute.add(onExecute)
            onDestroy = SkeletorizeCommandDestroyHandler()
            cmd.destroy.add(onDestroy)

            # keep the handlers referenced beyond this function
            handlers.append(onExecute)
            handlers.append(onDestroy)

            #define the inputs
            inputs = cmd.commandInputs

            bodyInput = inputs.addSelectionInput('body', 'Body', 'Please select a Body to skeletorize')
            bodyInput.addSelectionFilter(adsk.core.SelectionCommandInput.Bodies);
            bodyInput.setSelectionLimits(1, 1)

            initBoneDiameter = adsk.core.ValueInput.createByString(defaultBoneDiameter)
            inputs.addValueInput('boneDiameter', 'Bone Diameter', 'mm', initBoneDiameter)

            operationInput = inputs.addDropDownCommandInput('operation', 'Operation', 0)
            operationInput.listItems.add('New Body', True, 'Resources/NewBody/')
            operationInput.listItems.add('New Component', False, 'Resources/NewComponent/')

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


def run(context):

    try:
        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)
        if not design:
            ui.messageBox('It is not supported in current workspace, please change to MODEL workspace and try again.')
            return
        commandDefinitions = ui.commandDefinitions
        #check the command exists or not
        cmdDef = commandDefinitions.itemById('Skeletorize')
        if not cmdDef:
            cmdDef = commandDefinitions.addButtonDefinition('Skeletorize',
                                                            'Skeletorize a body',
                                                            'Skeletorize a body.')

        onCommandCreated = SkeletorizeCommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        # keep the handler referenced beyond this function
        handlers.append(onCommandCreated)
        inputs = adsk.core.NamedValues.create()
        cmdDef.execute(inputs)

        # prevent this module from being terminate when the script returns, because we are waiting for event handlers to fire
        adsk.autoTerminate(False)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))