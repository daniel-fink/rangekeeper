"""Document files, strict interchange codecs and append-only local revision stores.

``load`` and ``save`` read and write one document file with the documents that
it depends on; the codecs read and write one document of an explicit kind.
"""

from rangekeeper.io import json, yaml
from rangekeeper.io._document import Document
from rangekeeper.io.directory import DirectoryStore
from rangekeeper.io.files import load, save
from rangekeeper.io.geometry import GeometryProvider, geometry_providers
from rangekeeper.io.memory import MemoryStore
from rangekeeper.shared.store import RecordStore

__all__ = [
    "load",
    "save",
    "json",
    "yaml",
    "Document",
    "RecordStore",
    "MemoryStore",
    "DirectoryStore",
    "GeometryProvider",
    "geometry_providers",
]
