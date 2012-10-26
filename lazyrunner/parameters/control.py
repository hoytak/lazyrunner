import parameters
import context
import presets

def resetAndInitialize():
    presets.resetAndInitPresets()
    parameters.resetAndInitGlobalParameterTree()

def finalize():
    presets.finalizePresetLookup()
    parameters.finalizeDefaultTree()

