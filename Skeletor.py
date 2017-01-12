#Author-Mike Fogel
#Description-

import adsk.core, adsk.fusion, traceback

defaultBoneDiameter = '1mm'

# global set of event handlers to keep them referenced for the duration of the command
handlers = []
app = adsk.core.Application.get()
if app:
    ui = app.userInterface


class SkeletorizeCommandExecuteHandler(adsk.core.CommandEventHandler):

    def notify(self, args):
        try:
            unitsMgr = app.activeProduct.unitsManager
            command = args.firingEvent.sender
            inputs = command.commandInputs

            for input in inputs:
                if input.id == 'body':
                    targetBody = input.selection(0)
                if input.id == 'boneDiameter':
                    boneDiameter = unitsMgr.evaluateExpression(input.expression, "mm")

            ui.messageBox('{} {}'.format(targetBody, boneDiameter))
            args.isValidResult = True

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