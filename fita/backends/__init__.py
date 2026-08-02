"""
fita.backends -- pluggable storage engines for the FITA data model.

Available backends
------------------
  fits  : default FITS/MEF storage  (fita.io)
  hdf5  : HDF5 storage via h5py     (fita.backends.hdf5)
  zarr  : Zarr cloud storage        (fita.backends.zarr)

All backends implement the same read() / write() signature as fita.io.
"""

from .hdf5 import read as read_hdf5, write as write_hdf5
from .zarr import read as read_zarr, write as write_zarr

__all__ = ["read_hdf5", "write_hdf5", "read_zarr", "write_zarr"]
