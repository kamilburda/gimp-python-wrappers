#!/usr/bin/env python3

"""GIMP plug-in that provides a convenience wrapper for invoking GIMP PDB
procedures and generates stubs for PDB procedures to allow displaying code
completion suggestions in IDEs."""

import inspect
import os
import sys

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
from gi.repository import Gio
from gi.repository import GObject

import stubgen

current_script_dirpath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.append(os.path.dirname(current_script_dirpath))

from wrappers import procedure


def generate_pdb_stubs(proc, config, _data):
  run_mode = config.get_property('run-mode')

  if run_mode == Gimp.RunMode.INTERACTIVE:
    GimpUi.init('generate-pdb-stubs')

    dialog = GimpUi.ProcedureDialog(procedure=proc, config=config, title=None)
    dialog.fill(['output-directory'])

    is_ok_pressed = dialog.run()
    if is_ok_pressed:
      dialog.destroy()
    else:
      dialog.destroy()
      return Gimp.PDBStatusType.CANCEL

  output_dirpath = config.get_property('output-directory').get_path()
  if not output_dirpath:
    output_dirpath = stubgen.MODULE_DIRPATH

  stubgen.generate_pdb_stubs(output_dirpath)

  return Gimp.PDBStatusType.SUCCESS


procedure.register_procedure(
  generate_pdb_stubs,
  procedure_type=Gimp.Procedure,
  arguments=[
    [
      'enum',
      'run-mode',
      'Run mode',
      'The run mode',
      Gimp.RunMode,
      Gimp.RunMode.NONINTERACTIVE,
      GObject.ParamFlags.READWRITE,
    ],
    [
      'file',
      'output-directory',
      'Output _directory',
      f'Output directory (default: "{stubgen.MODULE_DIRPATH}")',
      Gimp.FileChooserAction.SELECT_FOLDER,
      False,
      Gio.file_new_for_path(stubgen.MODULE_DIRPATH),
      GObject.ParamFlags.READWRITE,
    ],
  ],
  menu_label='Generate GIMP PDB Stubs for Python',
  menu_path='<Image>/Filters/Development/Python-Fu',
  documentation=(
    ('Generates a Python stub file for GIMP PDB procedures (built-in procedures and plug-ins) and GEGL operations (layer effects)'
     f' named "{stubgen.PYPDB_MODULE_NAME}.pyi".'),
    (f'The "{stubgen.PYPDB_MODULE_NAME}.py" file provides a convenience wrapper'
     ' to simplify calls to GIMP PDB procedures and GEGL operations from Python plug-ins.'
     f' The generated "{stubgen.PYPDB_MODULE_NAME}.pyi" stub file can then be used'
     ' in integrated development environments (IDEs) to display code completion suggestions'
     ' for GIMP PDB procedures and GEGL operations.'),
  ),
  attribution=('Kamil Burda', '', '2023'),
  sensitivity_mask=Gimp.ProcedureSensitivityMask.ALWAYS,
)

procedure.main()
