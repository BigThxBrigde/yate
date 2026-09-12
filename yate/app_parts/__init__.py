"""Extracted YateApp collaborators.

Each module here owns one slice of the application glue that used to live
inline on :class:`yate.app.YateApp` (ex commands, completion orchestration,
explorer file operations, terminal lifecycle).  They all receive the app
instance explicitly and keep no state except what their feature owns, so
YateApp stays the single owner of shared session state.
"""
