from parameters import globalDefaultTree

from presets import processPModule, preset, presetTree, allPresets, \
     applyPreset, updatePresetCompletionCache, \
     getPresetHelpList, validatePresets, getParameterTree,           \
     registerPreset, BadPreset, defaults

from context import group

# A Hack; ack
context.PresetContext.register_preset_function = registerPreset

from control import finalize, resetAndInitialize

	