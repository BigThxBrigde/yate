--[[
yate bundled extension: games pack entry point (games.lua)

Registers the one ":game" command that launches any game of the pack:

    :game                 list the available games
    :game snake           start a game
    :game player          show the player name used in the high scores
    :game player alice    change that name

The command itself is a thin dispatcher: game_engine resolves the available
names from the registered "game-*" actions and each game script registers its
own launcher, so adding a game means adding one file and nothing else.

Entry form: module-table style -- this file returns mod and yate calls
mod.setup(api) at load and mod.teardown(api) on unload.
]]

local engine = require("game_engine")

local mod = {}

function mod.setup(_api)
  -- The dispatcher lives in the shared engine: every game file only calls
  -- engine.register(name, launch), which records the "game-<name>" action.
  yate.register_command("game", engine.dispatch, "launch a bundled game")
end

function mod.teardown(_api)
  -- Nothing to release: the games own their canvases and close them in their
  -- own teardown hooks.
end

return mod
