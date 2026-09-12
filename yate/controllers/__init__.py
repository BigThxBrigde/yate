"""Controller layer of the application.

Each module here implements one feature controller that used to live
inline on :class:`yate.app.YateApp` (ex commands, completion, explorer
file operations, terminal lifecycle).  Controllers receive the app
instance explicitly and keep no state except what their feature owns,
so YateApp stays the single owner of shared session state.
"""
