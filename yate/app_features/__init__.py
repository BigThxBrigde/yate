"""Application feature layer.

Each module implements one application feature (ex commands, completion,
explorer file operations, terminal lifecycle, doc viewers).  Features hold
their own state and depend on the narrow host protocols defined next to
them; ``YateApp`` only composes them and implements those protocols, so
the feature layer never imports :mod:`yate.app`.
"""
