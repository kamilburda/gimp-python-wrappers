"""Generating stubs for the GIMP procedural database (PDB)."""

import ast
import inspect
import os
import re
import sys
import textwrap

import gi
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
from gi.repository import Gio
from gi.repository import GLib
gi.require_version('GimpUi', '3.0')
from gi.repository import GObject


MODULE_DIRPATH = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
ROOT_DIRPATH = os.path.dirname(MODULE_DIRPATH)

WRAPPERS_DIRPATH = os.path.join(ROOT_DIRPATH, 'wrappers')

if ROOT_DIRPATH not in sys.path:
  sys.path.append(ROOT_DIRPATH)

from wrappers import pypdb


PYPDB_MODULE_NAME = 'pypdb'
PYPDB_MODULE_FILEPATH = os.path.join(WRAPPERS_DIRPATH, f'{PYPDB_MODULE_NAME}.py')
STUB_MODULE_FILEPATH = os.path.join(WRAPPERS_DIRPATH, f'{PYPDB_MODULE_NAME}.pyi')
TEXT_FILE_ENCODING = 'utf-8'

_PYPDB_CLASS_NAME = '_PyPDB'

_INDENT = '    '
_BODY_INDENT = _INDENT * 2
_DOCSTRING_LINE_LENGTH = 80

_GTYPES_TO_PYTHON_TYPES = {
  'gint': 'int',
  'guint': 'int',
  'gboolean': 'bool',
  'gdouble': 'float',
  'gchararray': 'str',
  'GBytes': 'GLib.Bytes',
  'GFile': 'Gio.File',
  'GParam': 'GObject.ParamSpec',
  'GStrv': 'list[str]',
}


def generate_pdb_stubs(output_dirpath):
  if not os.path.isfile(PYPDB_MODULE_FILEPATH):
    raise RuntimeError(f'pypdb module does not exist at "{os.path.dirname(PYPDB_MODULE_FILEPATH)}"')

  with open(PYPDB_MODULE_FILEPATH, 'r', encoding=TEXT_FILE_ENCODING) as f:
    root_node = ast.parse(f.read())

  _add_imports(root_node)

  _remove_implementation_of_functions(root_node)

  pypdb_class_node = _get_pypdb_class_node(root_node)

  for proc_name in sorted(pypdb.pdb.list_all_gimp_pdb_procedures()):
    _insert_gimp_pdb_procedure_node(pypdb_class_node, proc_name)

  for proc_name in sorted(pypdb.pdb.list_all_gegl_operations()):
    _insert_gegl_procedure_node(pypdb_class_node, proc_name)

  write_stub_file(output_dirpath, root_node)


def _add_imports(root_node):
  new_import_nodes = ast.parse(
    '\n'
    + '\n'.join([
      'from typing import Any',
      'from gi.repository import GLib',
      'from gi.repository import Gio',
    ])
  )

  last_consecutive_import_node_index = 0
  encountered_first_import_node = False

  for node in root_node.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
      last_consecutive_import_node_index += 1
      encountered_first_import_node = True
    else:
      if encountered_first_import_node:
        break

  for new_import_node in reversed(new_import_nodes.body):
    root_node.body.insert(last_consecutive_import_node_index, new_import_node)


def _remove_implementation_of_functions(root_node):
  for child in ast.walk(root_node):
    if isinstance(child, ast.FunctionDef):
      if child.name == '__init__':
        _remove_all_but_attributes_and_super_calls(child)
      else:
        child.body = [ast.Pass()]


def _remove_all_but_attributes_and_super_calls(node):
  indexes_of_body_nodes_to_delete = []

  for index, body_node in enumerate(node.body):
    if isinstance(body_node, ast.Assign):
      if all(isinstance(target.value, ast.Name) and target.value.id == 'self'
             for target in body_node.targets):
        body_node.value = ast.parse('None').body[0].value
      else:
        indexes_of_body_nodes_to_delete.append(index)
    elif isinstance(body_node, ast.Expr):
      if isinstance(body_node.value, ast.Call):
        try:
          func_name = body_node.value.func.value.func.id
        except AttributeError:
          indexes_of_body_nodes_to_delete.append(index)
        else:
          if func_name != 'super':
            indexes_of_body_nodes_to_delete.append(index)
      else:
        indexes_of_body_nodes_to_delete.append(index)
    else:
      indexes_of_body_nodes_to_delete.append(index)

  for index in reversed(indexes_of_body_nodes_to_delete):
    del node.body[index]


def _get_pypdb_class_node(root_node):
  pypdb_class_node = next(
    (child for child in root_node.body
     if isinstance(child, ast.ClassDef) and child.name == _PYPDB_CLASS_NAME),
    None)

  if pypdb_class_node is None:
    raise RuntimeError(f'"{_PYPDB_CLASS_NAME}" class not found in "{PYPDB_MODULE_FILEPATH}"')

  return pypdb_class_node


def _insert_gimp_pdb_procedure_node(pypdb_class_node, procedure_name):
  procedure_node = _create_pdb_procedure_node(procedure_name)

  procedure = pypdb.GimpPDBProcedure(pypdb.pdb, procedure_name)

  _insert_gimp_pdb_procedure_arguments(procedure_node, procedure)
  _insert_gimp_pdb_procedure_docstring(procedure_node, procedure)

  pypdb_class_node.body.append(procedure_node)


def _create_pdb_procedure_node(procedure_name):
  func_name = pypdb.pdb.canonical_name_to_python_name(procedure_name)

  # Constructing a `FunctionDef` node this way is more readable and less error-prone.
  func_base_arguments_str = 'self'
  func_base_docstring = '""'
  func_base_signature_str = (
    f'def {func_name}({func_base_arguments_str}):\n{_INDENT}{func_base_docstring}\n{_INDENT}pass')

  procedure_node = ast.parse(func_base_signature_str).body[0]

  return procedure_node


def _insert_gimp_pdb_procedure_arguments(procedure_node, procedure):
  proc_args = procedure.arguments

  for proc_arg in reversed(proc_args):
    arg_node = ast.arg(
      arg=pypdb.pdb.canonical_name_to_python_name(proc_arg.name),
      annotation=_get_proc_argument_type_hint(proc_arg),
      col_offset=None,
      end_col_offset=None,
      lineno=None,
      end_lineno=None,
      type_comment=None,
    )
    procedure_node.args.args.insert(1, arg_node)

    arg_default_value = ast.Constant(
      value=_get_param_default_value(proc_arg),
      col_offset=None,
      end_col_offset=None,
      lineno=None,
      end_lineno=None,
    )

    proc_arg_default_value = proc_arg.get_default_value()
    if (isinstance(proc_arg_default_value, GObject.GEnum)
        and not isinstance(proc_arg, (Gegl.ParamEnum, Gegl.ParamSpecEnum))):
      default_value_as_string = _get_enum_value_as_string(proc_arg_default_value)
      if default_value_as_string is not None:
        arg_default_value = ast.parse(default_value_as_string).body[0].value

    procedure_node.args.defaults.insert(0, arg_default_value)

  procedure_node.returns = _get_pdb_return_values_type_hint(procedure.return_values)


def _get_pdb_return_values_type_hint(proc_return_values):
  return_type_names = [
    _get_type_hint_name(proc_return_value, default_type='Any')
    for proc_return_value in proc_return_values]

  # Use dummy code with the desired annotation. It is more convenient to create
  # an annotation node this way.
  if len(return_type_names) > 1:
    return_type_names_str = ', '.join(return_type_names)
    dummy_func_with_type_hint = f'def foo() -> tuple[{return_type_names_str}]: pass'
  elif len(return_type_names) == 1:
    dummy_func_with_type_hint = f'def foo() -> {return_type_names[0]}: pass'
  else:
    return None

  node = ast.parse(dummy_func_with_type_hint)

  return node.body[0].returns


def _get_full_type_name(type_):
  # Taken from: https://stackoverflow.com/a/2020083
  module_name = type_.__module__
  if module_name == 'builtins':
    return type_.__qualname__
  else:
    if module_name.startswith('gi.repository.'):
      module_name = module_name[len('gi.repository.'):]
    return f'{module_name}.{type_.__qualname__}'


def _insert_gimp_pdb_procedure_docstring(procedure_node, procedure):
  proc_docstring = ''

  proc_docstring = _add_proc_blurb_to_docstring(procedure.blurb, proc_docstring)

  add_extra_newline = True
  proc_docstring, is_specified = _add_field_to_docstring(
    procedure.proc.get_image_types(), proc_docstring, 'Image types', True)

  add_extra_newline = add_extra_newline and not is_specified
  proc_docstring, is_specified = _add_field_to_docstring(
    procedure.menu_label, proc_docstring, 'Menu label', add_extra_newline)

  add_extra_newline = add_extra_newline and not is_specified
  proc_docstring = _add_menu_paths_to_docstring(procedure, proc_docstring, add_extra_newline)

  proc_docstring = _add_proc_help_to_docstring(procedure, proc_docstring)

  proc_docstring = _add_proc_params_to_docstring(procedure, proc_docstring)
  proc_docstring = _add_proc_return_values_to_docstring(procedure, proc_docstring)

  proc_docstring += f'\n{_BODY_INDENT}'

  procedure_node.body[0].value.value = proc_docstring


def _add_proc_blurb_to_docstring(proc_blurb, proc_docstring):
  if proc_blurb:
    proc_blurb = proc_blurb.strip()
    if not proc_blurb.endswith('.'):
      proc_blurb += '.'
    proc_blurb = proc_blurb[0].upper() + proc_blurb[1:]

    proc_blurb = textwrap.fill(
      proc_blurb,
      width=_DOCSTRING_LINE_LENGTH - len(_BODY_INDENT) - 3,  # 3 is the length of the leading `"""`
      subsequent_indent=_BODY_INDENT,
      break_on_hyphens=False)

    proc_docstring += proc_blurb

  return proc_docstring


def _add_field_to_docstring(field, proc_docstring, prefix, add_extra_newline):
  if field:
    if proc_docstring:
      proc_docstring += f'\n{_BODY_INDENT}' * (2 if add_extra_newline else 1)
    proc_docstring += f'{prefix}: {field}'

  return proc_docstring, bool(field)


def _add_menu_paths_to_docstring(procedure, proc_docstring, add_extra_newline):
  proc_menu_paths = procedure.menu_paths
  if proc_menu_paths:
    if proc_docstring:
      proc_docstring += f'\n{_BODY_INDENT}' * (2 if add_extra_newline else 1)

    proc_menu_paths = [path.rstrip('/') for path in proc_menu_paths]
    title = 'Menu paths' if len(proc_menu_paths) > 1 else 'Menu path'

    proc_docstring += f'{title}: {", ".join(proc_menu_paths)}'

  return proc_docstring


def _add_proc_help_to_docstring(procedure, proc_docstring):
  proc_help = procedure.help
  if proc_help:
    proc_help = proc_help.strip()
    if not proc_help.endswith('.'):
      proc_help += '.'
    proc_help = proc_help[0].upper() + proc_help[1:]

    proc_help = textwrap.fill(
      proc_help, width=_DOCSTRING_LINE_LENGTH - len(_BODY_INDENT), break_on_hyphens=False)

    # Double space corresponds to two newlines originally representing
    # paragraphs before `textwrap.fill`.
    # We restore the paragraphs and re-wrap the text. We need to do this due to
    # inconsistent format of the help text - some paragraphs are split by one newline,
    # some by two newlines or an entire paragraph is already wrapped to fit a certain line width.
    proc_help = re.sub(r'(\S)  +(\S)', r'\1\n\n\2', proc_help)

    proc_help = re.sub(
      r'(\S)\n(\S)',
      rf'\1 \2',
      proc_help)

    proc_help_lines = proc_help.split('\n\n')
    proc_help_lines = [
      textwrap.fill(
        line,
        width=_DOCSTRING_LINE_LENGTH - len(_BODY_INDENT),
        subsequent_indent=_BODY_INDENT,
        break_on_hyphens=False,
      )
      for line in proc_help_lines
    ]

    proc_help = (f'\n{_BODY_INDENT}' * 2).join(proc_help_lines)

    if proc_docstring:
      proc_docstring += f'\n{_BODY_INDENT}' * 2

    proc_docstring += f'{proc_help}'

  return proc_docstring


def _add_proc_params_to_docstring(procedure, proc_docstring):
  return _add_proc_params_or_retvals_to_docstring(
    procedure,
    proc_docstring,
    'parameter',
    lambda proc: proc.arguments,
    'Parameters:',
  )


def _add_proc_return_values_to_docstring(procedure, proc_docstring):
  return _add_proc_params_or_retvals_to_docstring(
    procedure,
    proc_docstring,
    'return_value',
    lambda proc: proc.return_values,
    'Returns:',
  )


def _add_proc_params_or_retvals_to_docstring(
        procedure, proc_docstring, param_type, get_params_func, title):
  params = get_params_func(procedure)

  if not params:
    return proc_docstring

  proc_params = title
  param_prefix = '* '

  for param in params:
    name = pypdb.pdb.canonical_name_to_python_name(param.name)

    description = param.blurb
    if description:
      if not description.endswith('.'):
        description += '.'
    else:
      description = ''

    object_type_str = ''
    if _is_core_object_array(param):
      object_type_str = f' (array of {_get_core_object_array_element_type(param)} elements)'

    file_info_str = ''
    if _is_file(param):
      file_info_str = f' ({_get_file_param_info(param)})'

    gimp_unit_limitations_str = ''
    if _is_gimp_unit(param):
      gimp_unit_limitations_str = f' ({_get_gimp_unit_limitations_str(param)})'

    default_value_str = _get_param_default_value(param)
    default_enum_value_as_string = None

    param_default_value = param.get_default_value()
    if (isinstance(param_default_value, GObject.GEnum)
        and not isinstance(param, (Gegl.ParamEnum, Gegl.ParamSpecEnum))):
      default_enum_value_as_string = _get_enum_value_as_string(param_default_value)
      if default_enum_value_as_string is not None:
        default_value_str = default_enum_value_as_string

    if default_value_str is not None:
      if default_enum_value_as_string is None:
        if isinstance(default_value_str, str):
          default_value_str = f" (default: '{default_value_str}')"
        elif isinstance(default_value_str, bytes):
          default_value_str = f" (default: b'{default_value_str}')"
        else:
          default_value_str = f' (default: {default_value_str})'
      else:
        default_value_str = f' (default: {default_value_str})'
    else:
      default_value_str = ''

    can_be_none_str = ''
    if _can_param_be_none(param):
      can_be_none_str = ' (can be None)'

    param_base_info = (
      f'{param_prefix}{name}'
      f'{object_type_str}{file_info_str}{gimp_unit_limitations_str}'
      f'{default_value_str}{can_be_none_str}')

    if description:
      param_str = f'{param_base_info} - {description}'
    else:
      param_str = param_base_info

    param_str = textwrap.fill(
      param_str,
      width=_DOCSTRING_LINE_LENGTH - len(_BODY_INDENT) - len(param_prefix),
      subsequent_indent=_BODY_INDENT + ' ' * len(param_prefix),
      break_on_hyphens=False)

    param_str = f'\n{_BODY_INDENT}' * 2 + param_str

    additional_description = None
    if _is_param_numeric(param):
      minimum_value, maximum_value = _get_minimum_maximum_value(param)

      if minimum_value is not None:
        additional_description = f'Minimum value: {minimum_value}'

      if maximum_value is not None:
        if not additional_description:
          additional_description = f'Maximum value: {maximum_value}'
        else:
          additional_description = f'{additional_description}, maximum value: {maximum_value}'
    elif _is_param_gimp_choice(param):
      choice_values = _format_gimp_choice_values(_get_gimp_choice_values(param))
      additional_description = f'Allowed values: {choice_values}'
    elif _is_param_gimp_choice_from_gegl_enum(param):
      choice_values = _format_gimp_choice_values(_get_gimp_choice_values_from_gegl_enum(param))
      additional_description = f'Allowed values: {choice_values}'

    if additional_description is not None:
      additional_description = textwrap.fill(
        additional_description,
        width=_DOCSTRING_LINE_LENGTH - len(_BODY_INDENT) - len(param_prefix),
        subsequent_indent=_BODY_INDENT + ' ' * len(param_prefix),
        break_on_hyphens=False)

      additional_description = f'\n{_BODY_INDENT}{' ' * len(param_prefix)}' * 2 + additional_description
      param_str += additional_description

    proc_params += param_str

  if proc_docstring:
    proc_docstring += f'\n{_BODY_INDENT}' * 2

  proc_docstring += f'{proc_params}'

  return proc_docstring


def _get_param_default_value(param):
  param_default_value = param.get_default_value()

  # Display only defaults for basic types + enums. While there are default
  # objects allowed for types such as `Gimp.Unit` and we could provide
  # custom strings describing the default objects, this would require
  # manual maintenance as the GIMP API changes.
  if isinstance(param, (Gegl.ParamEnum, Gegl.ParamSpecEnum)):
    # GIMP internally transforms GEGL enum values to `Gimp.Choice` values:
    #  https://gitlab.gnome.org/GNOME/gimp/-/merge_requests/2008
    return param_default_value.value_nick
  elif isinstance(param_default_value, (int, float, bool, str, bytes)):
    return param_default_value
  else:
    return None


def _can_param_be_none(param):
  gtype = param.value_type

  if gtype == Gio.File.__gtype__:
    return Gimp.param_spec_file_none_allowed(param)
  elif gtype == Gimp.Image.__gtype__:
    return Gimp.param_spec_image_none_allowed(param)
  elif gtype in [
        Gimp.Item.__gtype__,
        Gimp.Drawable.__gtype__,
        Gimp.Layer.__gtype__,
        Gimp.GroupLayer.__gtype__,
        Gimp.TextLayer.__gtype__,
        Gimp.Channel.__gtype__,
        Gimp.LayerMask.__gtype__,
        Gimp.Selection.__gtype__,
        Gimp.Path.__gtype__]:
    return Gimp.param_spec_item_none_allowed(param)
  elif gtype == Gimp.DrawableFilter.__gtype__:
    return Gimp.param_spec_drawable_filter_none_allowed(param)
  elif gtype == Gimp.Display.__gtype__:
    return Gimp.param_spec_display_none_allowed(param)
  elif gtype == Gegl.Color.__gtype__:
    return Gimp.param_spec_color_has_alpha(param)
  elif gtype.parent == Gimp.Resource.__gtype__:
    return Gimp.param_spec_resource_none_allowed(param)

  return False


def _is_core_object_array(param):
  return hasattr(param.value_type, 'name') and param.value_type.name == 'GimpCoreObjectArray'


def _is_file(param):
  return isinstance(param, Gimp.ParamFile)


def _get_file_param_info(param):
  action = Gimp.param_spec_file_get_action(param)

  if action == Gimp.FileChooserAction.OPEN:
    return 'file to open'
  elif action == Gimp.FileChooserAction.SAVE:
    return 'file to save'
  elif action == Gimp.FileChooserAction.SELECT_FOLDER:
    return 'folder to select'
  elif action == Gimp.FileChooserAction.CREATE_FOLDER:
    return 'folder to create'
  else:
    return ''


def _is_gimp_unit(param):
  return param.value_type == Gimp.Unit.__gtype__


def _get_gimp_unit_limitations_str(param):
  not_allowed_strs = []

  if not Gimp.param_spec_unit_percent_allowed(param):
    not_allowed_strs.append('percent not allowed')

  if not Gimp.param_spec_unit_pixel_allowed(param):
    not_allowed_strs.append('pixels not allowed')

  not_allowed_str = ', '.join(not_allowed_strs)

  return not_allowed_str


def _get_core_object_array_element_type(param):
  array_element_gtype = Gimp.param_spec_core_object_array_get_object_type(param)

  gi_module_names = [
    'Gimp',
    'Gegl',
    'GimpUi',
    'GObject',
    'GLib',
    'Gio',
  ]

  gtype_name = array_element_gtype.name

  for module_name in gi_module_names:
    if gtype_name.startswith(module_name):
      return f'{module_name}.{gtype_name[len(module_name):]}'

  return gtype_name


def _is_param_numeric(param):
  return hasattr(param, 'minimum') and hasattr(param, 'maximum')


def _get_minimum_maximum_value(param):
  min_value = param.minimum
  if ((param.value_type == GObject.TYPE_INT and min_value == GLib.MININT)
      or (param.value_type == GObject.TYPE_DOUBLE and min_value == -GLib.MAXDOUBLE)):
    min_value = None

  max_value = param.maximum
  if ((param.value_type == GObject.TYPE_INT and max_value == GLib.MAXINT)
      or (param.value_type == GObject.TYPE_UINT and max_value == GLib.MAXUINT)
      or (param.value_type == GObject.TYPE_DOUBLE and max_value == GLib.MAXDOUBLE)):
    max_value = None

  return min_value, max_value


def _is_param_gimp_choice(param):
  return isinstance(param, Gimp.ParamChoice)


def _get_gimp_choice_values(param):
  choice = Gimp.param_spec_choice_get_choice(param)
  return choice.list_nicks()


def _is_param_gimp_choice_from_gegl_enum(param):
  return isinstance(param, (Gegl.ParamEnum, Gegl.ParamSpecEnum))


def _get_gimp_choice_values_from_gegl_enum(param):
  return [
    enum_value.value_nick
    for enum_value in type(param.get_default_value()).__enum_values__.values()
  ]


def _format_gimp_choice_values(choice_values):
  return ", ".join(f"'{value}'" for value in choice_values)


def _get_enum_value_as_string(enum_value):
  enum_type = type(enum_value)

  if enum_type.__module__.startswith('gi.repository.'):
    enum_type_module_name = enum_type.__module__[len('gi.repository.'):]
  else:
    enum_type_module_name = enum_type.__module__

  enum_value_names_to_try = [
    enum_value.value_name,
    enum_value.value_name.upper(),
    enum_value.value_name.lower(),
  ]

  default_value_name = None
  for name in dir(enum_type):
    for value_name in enum_value_names_to_try:
      if value_name.endswith(name):
        default_value_name = name
        break

    if default_value_name is not None:
      break

  if default_value_name is not None:
    return f'{enum_type_module_name}.{enum_type.__qualname__}.{default_value_name}'
  else:
    return None


def _insert_gegl_procedure_node(pypdb_class_node, procedure_name):
  procedure_node = _create_pdb_procedure_node(procedure_name)

  procedure = pypdb.GeglProcedure(pypdb.pdb, procedure_name)

  _insert_gegl_procedure_arguments(procedure, procedure_node)
  _insert_gegl_procedure_docstring(procedure, procedure_node)

  pypdb_class_node.body.append(procedure_node)


def _insert_gegl_procedure_arguments(procedure, procedure_node):
  proc_args = procedure.arguments

  for proc_arg in reversed(proc_args):
    arg_node = ast.arg(
      arg=pypdb.pdb.canonical_name_to_python_name(proc_arg.name),
      annotation=_get_proc_argument_type_hint(proc_arg),
      col_offset=None,
      end_col_offset=None,
      lineno=None,
      end_lineno=None,
      type_comment=None,
    )
    procedure_node.args.args.insert(1, arg_node)

    arg_default_value = ast.Constant(
      value=_get_param_default_value(proc_arg),
      col_offset=None,
      end_col_offset=None,
      lineno=None,
      end_lineno=None,
    )

    proc_arg_default_value = proc_arg.get_default_value()
    if (isinstance(proc_arg_default_value, GObject.GEnum)
        and not isinstance(proc_arg, (Gegl.ParamEnum, Gegl.ParamSpecEnum))):
      default_value_as_string = _get_enum_value_as_string(proc_arg_default_value)
      if default_value_as_string is not None:
        arg_default_value = ast.parse(default_value_as_string).body[0].value

    procedure_node.args.defaults.insert(0, arg_default_value)

  procedure_node.returns = None


def _insert_gegl_procedure_docstring(procedure, procedure_node):
  proc_docstring = procedure.menu_label

  proc_docstring += f'\n{_BODY_INDENT}' * 2

  proc_docstring = _add_proc_blurb_to_docstring(procedure.blurb, proc_docstring)

  proc_docstring = _add_proc_params_or_retvals_to_docstring(
    procedure,
    proc_docstring,
    'parameter',
    lambda proc: proc.arguments,
    'Parameters:',
  )

  proc_docstring += f'\n{_BODY_INDENT}'

  procedure_node.body[0].value.value = proc_docstring


def _get_proc_argument_type_hint(proc_arg):
  arg_type_name = _get_type_hint_name(proc_arg, default_type='GObject.Value')

  if _can_param_be_none(proc_arg):
    arg_type_name = f'Optional[{arg_type_name}]'

  # Use placeholder code with the desired annotation. It is more convenient to
  # create an annotation node this way.
  node = ast.parse(f'def foo(arg: {arg_type_name}): pass')

  return node.body[0].args.args[0].annotation


def _get_type_hint_name(proc_arg, default_type=None):
  value_type = proc_arg.value_type

  if value_type is None or not value_type.name:
    return default_type

  if isinstance(proc_arg, (Gegl.ParamEnum, Gegl.ParamSpecEnum)):
    # GIMP internally transforms GEGL enum values to `Gimp.Choice` values,
    #  and `pdb` also allows passing strings beside enum values.
    #  https://gitlab.gnome.org/GNOME/gimp/-/merge_requests/2008
    #  Since the enum values are not easily accessible, only the string type
    #  will be displayed as a type hint.
    return 'str'
  elif proc_arg.value_type.name == 'GimpCoreObjectArray':
    core_object_array_element_type = Gimp.param_spec_core_object_array_get_object_type(proc_arg)
    element_type_name = _get_type_hint_name_from_gtype(core_object_array_element_type, default_type)
    # We use `List` as the `PyPDB` instance converts `GimpCoreObjectArray`s to
    # lists.
    return f'list[{element_type_name}]'
  else:
    return _get_type_hint_name_from_gtype(value_type, default_type)


def _get_type_hint_name_from_gtype(value_type, default_type):
  if value_type.name.startswith('Gimp'):
    try:
      getattr(Gimp, value_type.name[len('Gimp'):])
    except AttributeError:
      return default_type
    else:
      return f"Gimp.{value_type.name[len('Gimp'):]}"
  elif value_type.name.startswith('Gegl'):
    try:
      getattr(Gegl, value_type.name[len('Gegl'):])
    except AttributeError:
      return default_type
    else:
      return f"Gegl.{value_type.name[len('Gegl'):]}"
  elif value_type.name in _GTYPES_TO_PYTHON_TYPES:
    return _GTYPES_TO_PYTHON_TYPES[value_type.name]
  else:
    if value_type.pytype is not None:
      return _get_full_type_name(value_type.pytype)
    else:
      return default_type


def write_stub_file(dirpath, root_node):
  os.makedirs(dirpath, exist_ok=True)

  stub_filepath = os.path.join(dirpath, f'{PYPDB_MODULE_NAME}.pyi')
  with open(stub_filepath, 'w', encoding=TEXT_FILE_ENCODING) as stub_file:
    stub_file.write(ast.unparse(root_node))
