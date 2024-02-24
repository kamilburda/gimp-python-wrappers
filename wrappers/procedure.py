"""Wrappers to simplify registering and running functions as GIMP procedures.
"""

from collections.abc import Iterable
import functools
import sys
from typing import Callable, Dict, List, Optional, Tuple, Type, Union

import gi

gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
from gi.repository import GLib
from gi.repository import GObject


_PROCEDURE_NAMES_AND_DATA = {}
_PLUGIN_PROPERTIES = {}
_USE_LOCALE = False
_INIT_PROCEDURES_FUNC = None
_QUIT_FUNC = None


def register_procedure(
      procedure: Callable,
      procedure_type: Type[Gimp.Procedure] = Gimp.ImageProcedure,
      arguments: Optional[List[Union[Dict, str]]] = None,
      return_values: Optional[List[Union[Dict, str]]] = None,
      menu_label: Optional[str] = None,
      menu_path: Optional[Union[str, List[str]]] = None,
      image_types: Optional[str] = None,
      sensitivity_mask: Optional[Gimp.ProcedureSensitivityMask] = None,
      documentation: Optional[Union[Tuple[str, str], Tuple[str, str, str]]] = None,
      attribution: Optional[Tuple[str, str, str]] = None,
      auxiliary_arguments: Optional[List[Union[Dict, str]]] = None,
      run_data: Optional[List] = None,
      init_ui: bool = True,
      pdb_procedure_type: Gimp.PDBProcType = Gimp.PDBProcType.PLUGIN,
      additional_init: Optional[Callable] = None,
):
  # noinspection PyUnresolvedReferences
  """Registers a function as a GIMP procedure.

  The installed procedure can then be accessed via the GIMP procedural
  database (PDB) and, optionally, from the GIMP user interface.

  The function name is used as the procedure name as found in the GIMP PDB,
  with ``_`` characters replaced with ``-``.

  This is a wrapper for the `Gimp.PlugIn` class to simplify the registration of
  plug-ins and their procedures.

  The description of parameters is provided below. For more detailed information
  about the parameters, consult the `Gimp.Procedure` class (namely functions
  starting with ``add_`` or ``set__``).

  Args:
    procedure: The function to register.
    procedure_type:
      Type of procedure to create. Can be `Gimp.Procedure` or any of its
      subclasses, depending on the intended usage of the GIMP procedure to be
      registered. If ``procedure_type`` is `Gimp.ImageProcedure`, several PDB
      arguments will be pre-filled (see the documentation for
      `Gimp.ImageProcedure` for more information).
    arguments: List of arguments (procedure parameters).
      Each list element must either be a dictionary or a string.
      The dictionary must contain the ``'name'`` key representing the argument
      name and optionally other keys corresponding to the parameter names for
      `GObject.Property`.
      If the list element is a string, it must be the name of an argument
      already registered in a previous call to `register_procedure` (that is, a
      string can only be specified if a dictionary containing the same name was
      already specified). This allows reusing arguments for multiple plug-in
      procedures without the need to duplicate the entire dictionary for each
      procedure.
      Underscores in names (``_``) are automatically replaced with hyphens
      (``-``).
    return_values: List of return values.
      See ``arguments`` for more information about the contentsn and format of
      the list.
    menu_label: Name of the menu entry in the GIMP user interface.
    menu_path: Path of the menu entry in the GIMP user interface.
      This can be a single string or a list of strings if you want your
      procedure to be accessible from mutliple menu paths in GIMP.
    image_types: Image types to which the procedure applies.
    sensitivity_mask:
      `Gimp.ProcedureSensitivityMask` determining when the menu entry will be
      accessible (sensitive).
    documentation: Procedure documentation.
      This is either a tuple of (short description, help) strings or
      (short description, help, help ID) strings.
      The help is a detailed description of the procedure.
      The help ID is set automatically if omitted, it is not required to
      specify it explicitly.
    attribution: Plug-in authors, copyright notice and date.
      This is a tuple of (authors, copyright notice, date) strings.
    auxiliary_arguments: List of auxiliary arguments.
      See ``arguments`` for more information about the contentsn and format of
      the list.
      See `Gimp.add_aux_argument_from_property` for more information about
      auxiliary arguments.
    run_data: Custom parameters passed to ``procedure`` as its last argument.
      ``procedure`` should only contain the run data as its last argument if
      ``run_data`` is not ``None``.
    init_ui: If ``True``, user interface is initialized via `GimpUi.init`.
      See `GimpUi.init` for more information.
    pdb_procedure_type: One of the values of the `Gimp.PDBProcType` enum.
    additional_init: Function allowing customization of procedure registration.
      The function accepts a single argument - a ``Gimp.Procedure`` instance
      corresponding to the registered procedure.
      You can use this function to call registration-related functions not
      available via this function, e.g. `Gimp.Procedure.set_argument_sync`
      on individual procedure arguments.

  Example:

    >>> import pygimplib as pg
    >>> pg.register_procedure(
    ...   plug_in_awesome_filter,
    ...   arguments=[
    ...     dict(name='run_mode',
    ...          type=Gimp.RunMode,
    ...          default=Gimp.RunMode.INTERACTIVE,
    ...          nick='Run mode',
    ...          blurb='The run mode'),
    ...     dict(name='output_directory',
    ...          type=str,
    ...          default='some_dir',
    ...          nick='Output directory',
    ...          blurb='Output _directory'),
    ...   ],
    ...   return_values=[
    ...     dict(name='num_layers',
    ...          type=int,
    ...          default=0,
    ...          nick='Number of processed layers',
    ...          blurb='Number of processed layers'),
    ...   ],
    ...   menu_label='Awesome Filter',
    ...   menu_path='<Image>/Filters',
    ...   image_types='*',
    ...   documentation=('An awesome filter.',
    ...                  'Applies a mind-blowing filter to each layer.'),
    ...   attribution=('Jane Doe, John Doe', 'Jane Doe, John Doe', '2023'),
    ... )
  """
  global _INIT_PROCEDURES_FUNC
  global _QUIT_FUNC

  proc_name = procedure.__name__.replace('_', '-')

  if proc_name in _PROCEDURE_NAMES_AND_DATA:
    raise ValueError(f'procedure "{proc_name}" is already registered')

  _PROCEDURE_NAMES_AND_DATA[proc_name] = {}

  proc_dict = _PROCEDURE_NAMES_AND_DATA[proc_name]
  proc_dict['procedure'] = procedure
  proc_dict['procedure_type'] = procedure_type
  proc_dict['arguments'] = _parse_and_check_parameters(arguments)
  proc_dict['return_values'] = _parse_and_check_parameters(return_values)
  proc_dict['menu_label'] = menu_label
  proc_dict['menu_path'] = menu_path
  proc_dict['image_types'] = image_types
  proc_dict['sensitivity_mask'] = sensitivity_mask
  proc_dict['documentation'] = documentation
  proc_dict['attribution'] = attribution
  proc_dict['auxiliary_arguments'] = _parse_and_check_parameters(auxiliary_arguments)
  proc_dict['run_data'] = run_data
  proc_dict['init_ui'] = init_ui
  proc_dict['pdb_procedure_type'] = pdb_procedure_type
  proc_dict['additional_init'] = additional_init


def _parse_and_check_parameters(parameters):
  if parameters is None:
    return None

  if not isinstance(parameters, Iterable) or isinstance(parameters, str):
    raise TypeError('Arguments and return values must be specified as a list-like iterable')

  processed_parameters = {}

  for param in parameters:
    if isinstance(param, dict):
      if 'name' not in param:
        raise ValueError(
          ('Dictionary describing an argument or a return value must also contain'
           ' the "name" key representing the parameter name as registered in GIMP'))

      name = param.pop('name').replace('_', '-')
      if name not in _PLUGIN_PROPERTIES:
        _PLUGIN_PROPERTIES[name] = GObject.Property(**param)

      processed_parameters[name] = _PLUGIN_PROPERTIES[name]
    elif isinstance(param, str):
      name = param.replace('_', '-')

      if name not in _PLUGIN_PROPERTIES:
        raise ValueError(
          ('You can only specify the name of an argument or a return value if a dictionary'
           ' containing the name was already specified before'))

      processed_parameters[name] = _PLUGIN_PROPERTIES[name]
    else:
      raise TypeError(
        'Only dictionaries and strings are allowed when specifying an argument or a return value')

  return processed_parameters


def set_use_locale(enabled):
  """If ``True``, enables plug-in localization, ``False`` otherwise.

  You do not need to call this function explicitly as pygimplib will call it
  automatically. If the `locale` directory under the main plug-in directory
  exists, localization will be enabled.

  You can call this function explicitly to enable localization if you use a
  custom localization approach that does not rely on the presence of the
  ``locale`` subdirectory.
  """
  global _USE_LOCALE
  _USE_LOCALE = bool(enabled)


def set_init_procedures_func(func: Optional[Callable] = None):
  """Sets a function returning a list of procedure names, to be called during
  plug-in initialization.

  Passing ``None`` unsets the function.

  This function's behavior is identical to `Gimp.PlugIn.do_init_procedures`.
  See `Gimp.PlugIn` for more information.
  """
  global _INIT_PROCEDURES_FUNC
  _INIT_PROCEDURES_FUNC = func


def set_quit_func(func: Optional[Callable] = None):
  """Sets a function to be called before a plug-in terminates.

  Passing ``None`` unsets the function.

  See `Gimp.PlugIn` for more information.
  """
  global _QUIT_FUNC
  _QUIT_FUNC = func


def main():
  """Initializes and runs the plug-in.

  Call this function at the very end of your main plug-in script.
  """
  # noinspection PyPep8Naming
  PyPlugIn = _create_plugin_class()

  # noinspection PyUnresolvedReferences
  Gimp.main(PyPlugIn.__gtype__, sys.argv)


def _create_plugin_class(class_name='PyPlugIn', bases=(Gimp.PlugIn,)):
  class_dict = {}

  # `GObject.Property` objects must be specified when defining a `Gimp.PlugIn`
  # subclass, they cannot be added later as this will result in errors
  # (probably because the parent class of `Gimp.PlugIn`, `GObject.GObject`, has
  # a metaclass that performs property initialization upon class definition, not
  # object instantiation).
  # Therefore, the custom `Gimp.PlugIn` subclass must be created dynamically
  # where it is possible to pass a dictionary of class attributes, including
  # `GObject.Property` objects.
  for name, gobject_property in _PLUGIN_PROPERTIES.items():
    class_dict[name.replace('-', '_')] = gobject_property

  class_dict['do_query_procedures'] = _do_query_procedures
  class_dict['do_create_procedure'] = _do_create_procedure

  if not _USE_LOCALE:
    class_dict['do_set_i18n'] = _disable_locale

  if _INIT_PROCEDURES_FUNC:
    class_dict['do_init_procedures'] = _INIT_PROCEDURES_FUNC

  if _QUIT_FUNC:
    class_dict['do_quit'] = _QUIT_FUNC

  return type(
    class_name,
    bases,
    class_dict,
  )


def _do_query_procedures(plugin_instance):
  return list(_PROCEDURE_NAMES_AND_DATA)


def _do_create_procedure(plugin_instance, proc_name):
  if proc_name in _PROCEDURE_NAMES_AND_DATA:
    proc_dict = _PROCEDURE_NAMES_AND_DATA[proc_name]
  else:
    return None

  procedure = proc_dict['procedure_type'].new(
    plugin_instance,
    proc_name,
    proc_dict['pdb_procedure_type'],
    _get_procedure_wrapper(
      proc_dict['procedure'], proc_dict['procedure_type'], proc_dict['init_ui']),
    proc_dict['run_data'])

  if proc_dict['arguments'] is not None:
    for name in proc_dict['arguments']:
      procedure.add_argument_from_property(plugin_instance, name)

  if proc_dict['return_values'] is not None:
    for name in proc_dict['return_values']:
      procedure.add_return_value_from_property(plugin_instance, name)

  if proc_dict['auxiliary_arguments'] is not None:
    for name in proc_dict['auxiliary_arguments']:
      procedure.add_aux_argument_from_property(plugin_instance, name)

  if proc_dict['menu_label'] is not None:
    procedure.set_menu_label(proc_dict['menu_label'])

  menu_path = proc_dict['menu_path']
  if menu_path is not None:
    if isinstance(menu_path, str):
      procedure.add_menu_path(menu_path)
    elif isinstance(menu_path, Iterable):
      for path in menu_path:
        procedure.add_menu_path(path)
    else:
      raise TypeError(f'menu path "{menu_path}" must be a string or an iterable')

  if proc_dict['image_types'] is not None:
    procedure.set_image_types(proc_dict['image_types'])

  if proc_dict['sensitivity_mask'] is not None:
    procedure.set_sensitivity_mask(proc_dict['sensitivity_mask'])

  if proc_dict['documentation'] is not None:
    if len(proc_dict['documentation']) == 2:
      procedure.set_documentation(*proc_dict['documentation'], proc_name)
    elif len(proc_dict['documentation']) == 3:
      procedure.set_documentation(*proc_dict['documentation'])
    else:
      raise ValueError('documentation must be a tuple of 2 or 3 elements')

  if proc_dict['attribution'] is not None:
    procedure.set_attribution(*proc_dict['attribution'])

  if proc_dict['additional_init'] is not None:
    proc_dict['additional_init'](procedure)

  return procedure


def _disable_locale(plugin_instance, name):
  return False


def _get_procedure_wrapper(func, procedure_type, init_ui):
  @functools.wraps(func)
  def func_wrapper(*procedure_and_args):
    procedure = procedure_and_args[0]
    config = procedure_and_args[-2]

    if procedure_type == Gimp.ImageProcedure:
      run_mode = procedure_and_args[1]
    else:
      run_mode = next(
        (config.get_property(prop.name)
         for prop in config.list_properties() if prop.name == 'run-mode'),
        Gimp.RunMode.NONINTERACTIVE)

    if init_ui and run_mode == Gimp.RunMode.INTERACTIVE:
      GimpUi.init(procedure.get_name())

    return_values = func(*procedure_and_args)

    if return_values is None:
      return_values = []
    elif not isinstance(return_values, tuple):
      return_values = [return_values]
    else:
      return_values = list(return_values)

    if not return_values or not isinstance(return_values[0], Gimp.PDBStatusType):
      exit_status = Gimp.PDBStatusType.SUCCESS
    else:
      exit_status = return_values.pop(0)

    if exit_status in [Gimp.PDBStatusType.CALLING_ERROR, Gimp.PDBStatusType.EXECUTION_ERROR]:
      error = GLib.Error(return_values[0]) if return_values else GLib.Error()
      formatted_return_values = procedure.new_return_values(exit_status, error)
    else:
      formatted_return_values = procedure.new_return_values(exit_status, GLib.Error())
      if formatted_return_values.length() > 1:
        for i in reversed(range(1, formatted_return_values.length())):
          if i - 1 < len(return_values):
            formatted_return_values.remove(i)
            formatted_return_values.insert(i, return_values[i - 1])

    return formatted_return_values

  return func_wrapper
