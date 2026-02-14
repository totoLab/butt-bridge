"""
Generate a unique GUID for cx_Freeze upgrade_code
Run this once and copy the GUID to your setup.py
"""

import uuid

print("=" * 60)
print("GUID Generator for cx_Freeze MSI Installer")
print("=" * 60)
print()
print("Copy this GUID to your setup.py in the 'upgrade_code' field:")
print()
guid = str(uuid.uuid4())
print(f'"{{{guid}}}"')
print()
print("Full line for setup.py:")
print(f'"upgrade_code": "{{{guid}}}",')
print()
print("IMPORTANT: Keep this GUID the same across all versions")
print("of your application for proper upgrade detection!")
print("=" * 60)