#!/usr/bin/env python3

"""GIMP plug-in that provides a convenience wrapper for invoking GIMP PDB
procedures and generates stubs for PDB procedures to allow displaying code
completion suggestions in IDEs."""

import sys

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
from gi.repository import GObject
from gi.repository import GLib

import stubgen_pdb


def generate_pdb_stubs(procedure, config, _data):
  run_mode = config.get_property('run-mode')

  if run_mode == Gimp.RunMode.INTERACTIVE:
    GimpUi.init('generate-pdb-stubs')

    dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config, title=None)
    dialog.fill(['output-dirpath'])

    is_ok_pressed = dialog.run()
    if is_ok_pressed:
      dialog.destroy()
    else:
      dialog.destroy()
      return Gimp.PDBStatusType.CANCEL

  output_dirpath = config.get_property('output-dirpath')
  if not output_dirpath:
    output_dirpath = stubgen_pdb.MODULE_DIRPATH

  stubgen_pdb.generate_pdb_stubs(output_dirpath)

  return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class PdbStubGenerator(Gimp.PlugIn):
  run_mode = GObject.Property(
    type=Gimp.RunMode,
    default=Gimp.RunMode.NONINTERACTIVE,
    nick='Run mode',
    blurb='The run mode')

  output_dirpath = GObject.Property(
    type=str,
    default=stubgen_pdb.MODULE_DIRPATH,
    nick='Output _directory path',
    blurb=f'Output directory path (default: "{stubgen_pdb.MODULE_DIRPATH}")')

  def do_set_i18n(self, name):
    return False

  def do_query_procedures(self):
    return ['generate-pdb-stubs']

  def do_create_procedure(self, name):
    procedure = Gimp.Procedure.new(
      self,
      name,
      Gimp.PDBProcType.PLUGIN,
      generate_pdb_stubs,
      None)

    procedure.set_image_types('')
    procedure.set_documentation(
      ('Generates a stub file for the GIMP procedural database (PDB) for Python plug-ins'
       f' named "{stubgen_pdb.PYPDB_MODULE_NAME}.pyi".'),
      (f'The "{stubgen_pdb.PYPDB_MODULE_NAME}.py" file provides a convenience wrapper'
       ' to simplify calls to GIMP PDB procedures from Python plug-ins.'
       f' The generated "{stubgen_pdb.PYPDB_MODULE_NAME}.pyi" stub file can then be used'
       ' in integrated development environments (IDEs) to display code completion suggestions'
       ' for GIMP PDB procedures.'),
      name)
    procedure.set_attribution('Kamil Burda', '', '2023')
    procedure.set_menu_label('Generate GIMP PDB Stubs for Python')
    procedure.add_menu_path('<Image>/Filters/Development/Python-Fu')

    procedure.add_argument_from_property(self, 'run-mode')
    procedure.add_argument_from_property(self, 'output-dirpath')

    return procedure


Gimp.main(PdbStubGenerator.__gtype__, sys.argv)
