import sys
sys.argv.append('build')

from cx_Freeze import setup, Executable
# Dependencies are automatically detected, but it might need
# fine tuning.
build_options = {'packages': [], 'excludes': [],'build_exe': 'result'}

base = 'gui'

executables = [
    Executable('DualDisplayTool.py', base=base, target_name = 'DualDisplayTool',icon = "Icons/display.ico")
]

setup(name='DualDisplayTool',
      version = '1.0',
      description = 'Steuerung des zweiten Bildschirms für Dozenten',
      options = {'build_exe': build_options},
      executables = executables)

import shutil
shutil.copytree('Icons', 'result/Icons')