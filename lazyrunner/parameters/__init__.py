from presets import processPModule, preset, presetTree, allPresets, \
     applyPreset, updatePresetCompletionCache, \
     getPresetHelpList, validatePresets, getParameterTree,           \
     registerPreset, BadPreset, defaults, group, PCall

from control import finalize, resetAndInitialize

# Set up a universal caller for the presets	
pcall = PCall(None)