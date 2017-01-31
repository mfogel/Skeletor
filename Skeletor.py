#Author-Mike Fogel
#Description-

import adsk.core, adsk.fusion, traceback

defaultBoneDiameter = '1mm'

# global set of event handlers to keep them referenced for the duration of the command
handlers = []
app = adsk.core.Application.get()
if app:
    ui = app.userInterface

product = app.activeProduct
design = adsk.fusion.Design.cast(product)


def createNewComponent(name):
    # Get the active design.
    rootComp = design.rootComponent
    allOccs = rootComp.occurrences
    component = allOccs.addNewComponent(adsk.core.Matrix3D.create()).component
    component.name = name
    return component


def createSkeleton(targetBody, boneDiameter, parentComponent):

    baseFeat = parentComponent.features.baseFeatures.add()
    baseFeat.name = "Skeletorize " + targetBody.name
    baseFeat.startEdit()

    planes = parentComponent.constructionPlanes
    sketches = parentComponent.sketches
    sweeps = parentComponent.features.sweepFeatures
    revolves = parentComponent.features.revolveFeatures

    xPosPoint = adsk.core.Point3D.create(boneDiameter/2, 0, 0)
    xNegPoint = adsk.core.Point3D.create(-boneDiameter/2, 0, 0)

    yPosPoint = adsk.core.Point3D.create(0, boneDiameter/2, 0)
    yNegPoint = adsk.core.Point3D.create(0, -boneDiameter/2, 0)

    vertexId2Sketch = {}

    for edge in targetBody.edges:

        planeInput = planes.createInput()
        planeInput.setByDistanceOnPath(edge, adsk.core.ValueInput.createByReal(0))
        planeInput.targetBaseOrFormFeature = baseFeat
        plane = planes.add(planeInput)

        #sketch = sketches.add(plane)
        sketch = sketches.addToBaseOrFormFeature(plane, baseFeat, False)
        sketch.sketchCurves.sketchArcs.addByThreePoints(xPosPoint, yPosPoint, xNegPoint)
        sketch.sketchCurves.sketchArcs.addByThreePoints(xPosPoint, yNegPoint, xNegPoint)
        vertexId2Sketch[edge.startVertex.tempId] = sketch

        path = adsk.fusion.Path.create(edge, adsk.fusion.ChainedCurveOptions.noChainedCurves)
        profile = sketch.profiles.item(0)
        sweepInput = sweeps.createInput(profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        sweepInput.targetBaseOrFormFeature = baseFeat
        sweeps.add(sweepInput)

    for vertex in targetBody.vertices:

        sketch = vertexId2Sketch.get(vertex.tempId)
        if not sketch:
            sketch = sketches.addToBaseOrFormFeature(plane, baseFeat, False)
            sketch.sketchCurves.sketchArcs.addByThreePoints(xPosPoint, yPosPoint, xNegPoint)
            sketch.sketchCurves.sketchArcs.addByThreePoints(xPosPoint, yNegPoint, xNegPoint)

        line = sketch.sketchCurves.sketchLines.addByTwoPoints(xPosPoint, xNegPoint)
        profile = sketch.profiles.item(0)

        revolveInput = revolves.createInput(profile, line, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        revolveInput.setAngleExtent(False, adsk.core.ValueInput.createByString('360deg'))
        revolveInput.baseFeature = baseFeat
        revolves.add(revolveInput)

    baseFeat.finishEdit()


class SkeletorizeCommandExecuteHandler(adsk.core.CommandEventHandler):

    def notify(self, args):
        try:
            unitsMgr = app.activeProduct.unitsManager
            command = args.firingEvent.sender
            inputs = command.commandInputs

            if inputs.count != 2:
                raise ValueError('Unexpected number of inputs: {}'.format(inputs.count))

            for input in inputs:
                if input.id == 'body':
                    targetBody = input.selection(0).entity
                elif input.id == 'boneDiameter':
                    boneDiameter = unitsMgr.evaluateExpression(input.expression, "mm")
                else:
                    raise ValueError('Unexpected input iud: {}'.format(input.id))

            # ensure our target has edges and such (ex: a sphere doesn't)
            if targetBody.edges.count == 0:
                raise ValueError('Target Body has no edges')

            # do the real work
            parentComponent = createNewComponent(targetBody.name + ' Skeleton')
            createSkeleton(targetBody, boneDiameter, parentComponent)
            targetBody.isLightBulbOn = False
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

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


def run(context):

    try:
        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)

        if not design:
            ui.messageBox('Error: Skeletorizing requires being in the Model workspace')
            return
        if design.designType is not adsk.fusion.DesignTypes.ParametricDesignType:
            ui.messageBox('Error: Skeletorizing requires being in parametric design mode (timeline must be active)')
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