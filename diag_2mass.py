"""Diagnose 2MASS J SkyView data and calibration headers."""
import numpy as np
from astroquery.skyview import SkyView
import astropy.units as u
import warnings
warnings.filterwarnings("ignore")

imgs = SkyView.get_images(
    position='299.901 +22.721',
    survey=['2MASS-J'],
    radius=20 * u.arcmin,
    pixels=300,
)
hdu = imgs[0][0]
data = hdu.data.astype('float32')
finite = data[np.isfinite(data)]

print(f"2MASS-J SkyView shape : {data.shape}")
print(f"finite pixels         : {finite.size} / {data.size}  ({100*finite.size/data.size:.0f}%)")
if finite.size > 0:
    print(f"value range           : {finite.min():.2f}  ..  {finite.max():.2f}")
    print(f"median                : {np.median(finite):.2f}")
print()
print("Header (non-WCS):")
skip = {'COMMENT','HISTORY',''}
for k, v in hdu.header.items():
    if k in skip or k.startswith('CD') or k.startswith('PC'):
        continue
    print(f"  {k:12s} = {v!r}")
