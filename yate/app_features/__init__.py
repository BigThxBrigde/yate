"""Application feature layer.

Each module here implements one application feature that used to live
inline on :class:`yate.app.YateApp` (ex commands, completion, explorer
file operations, terminal lifecycle).  Features receive the app instance
explicitly and keep no state except what their feature owns, so YateApp
stays the single owner of shared session state.
"""
