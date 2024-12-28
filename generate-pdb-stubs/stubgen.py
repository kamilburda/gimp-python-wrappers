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
  'GStrv': 'List[str]',
}


def generate_pdb_stubs(output_dirpath):
  if not os.path.isfile(PYPDB_MODULE_FILEPATH):
    raise RuntimeError(f'pypdb module does not exist at "{os.path.dirname(PYPDB_MODULE_FILEPATH)}"')

  with open(PYPDB_MODULE_FILEPATH, 'r', encoding=TEXT_FILE_ENCODING) as f:
    root_node = ast.parse(f.read())

  _add_imports(root_node)

  _remove_implementation_of_functions(root_node)

  pypdb_class_node = _get_pypdb_class_node(root_node)

  for proc_name, proc in sorted(_get_gimp_pdb_procedures().items()):
    _insert_gimp_pdb_procedure_node(pypdb_class_node, proc_name, proc)

  for proc_name in sorted(_get_gegl_procedures()):
    _insert_gegl_procedure_node(pypdb_class_node, proc_name)

  write_stub_file(output_dirpath, root_node)


def _add_imports(root_node):
  new_import_nodes = ast.parse(
    '\n'
    + '\n'.join([
      'from typing import Any, List, Tuple, Union',
      'from gi.repository import GLib',
      'from gi.repository import Gio',
      'from gi.repository import GObject',
    ])
  )

  for new_import_node in reversed(new_import_nodes.body):
    root_node.body.insert(0, new_import_node)


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


def _insert_gimp_pdb_procedure_node(pypdb_class_node, procedure_name, procedure):
  procedure_node = _create_pdb_procedure_node(procedure_name)

  _insert_gimp_pdb_procedure_arguments(procedure_node, procedure)
  _insert_gimp_pdb_procedure_docstring(procedure_node, procedure)

  pypdb_class_node.body.append(procedure_node)


def _create_pdb_procedure_node(procedure_name):
  func_name = _pythonize(procedure_name)

  # Constructing a `FunctionDef` node this way is more readable and less error-prone.
  func_base_arguments_str = 'self'
  func_base_docstring = '""'
  func_base_signature_str = (
    f'def {func_name}({func_base_arguments_str}):\n{_INDENT}{func_base_docstring}\n{_INDENT}pass')

  procedure_node = ast.parse(func_base_signature_str).body[0]

  return procedure_node


def _insert_gimp_pdb_procedure_arguments(procedure_node, procedure):
  proc_args = procedure.get_arguments()

  for proc_arg in reversed(proc_args):
    arg_node = ast.arg(
      arg=_pythonize(proc_arg.name),
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

    if isinstance(proc_arg.get_default_value(), GObject.GEnum):
      default_value_as_string = _get_enum_value_as_string(proc_arg.get_default_value())
      if default_value_as_string is not None:
        arg_default_value = ast.parse(default_value_as_string).body[0].value

    procedure_node.args.defaults.insert(0, arg_default_value)

  procedure_node.returns = _get_pdb_return_values_type_hint(procedure.get_return_values())


def _get_pdb_return_values_type_hint(proc_return_values):
  return_type_names = [
    _parse_type(proc_return_value, default_type='Any') for proc_return_value in proc_return_values]

  # Use dummy code with the desired annotation. It is more convenient to create
  # an annotation node this way.
  if len(return_type_names) > 1:
    return_type_names_str = ', '.join(return_type_names)
    dummy_func_with_type_hint = f'def foo() -> Tuple[{return_type_names_str}]: pass'
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

  proc_docstring = _add_proc_blurb_to_docstring(procedure.get_blurb(), proc_docstring)

  add_extra_newline = True
  proc_docstring, is_specified = _add_field_to_docstring(
    procedure.get_image_types(), proc_docstring, 'Image types', True)

  add_extra_newline = add_extra_newline and not is_specified
  proc_docstring, is_specified = _add_field_to_docstring(
    procedure.get_menu_label(), proc_docstring, 'Menu label', add_extra_newline)

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
  proc_menu_paths = procedure.get_menu_paths()
  if proc_menu_paths:
    if proc_docstring:
      proc_docstring += f'\n{_BODY_INDENT}' * (2 if add_extra_newline else 1)

    proc_menu_paths = [path.rstrip('/') for path in proc_menu_paths]
    title = 'Menu paths' if len(proc_menu_paths) > 1 else 'Menu path'

    proc_docstring += f'{title}: {", ".join(proc_menu_paths)}'

  return proc_docstring


def _add_proc_help_to_docstring(procedure, proc_docstring):
  proc_help = procedure.get_help()
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
    lambda proc: proc.get_arguments(),
    'Parameters:',
  )


def _add_proc_return_values_to_docstring(procedure, proc_docstring):
  return _add_proc_params_or_retvals_to_docstring(
    procedure,
    proc_docstring,
    'return_value',
    lambda proc: proc.get_return_values(),
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
    name = _pythonize(param.name)

    description = param.blurb
    if description:
      if not description.endswith('.'):
        description += '.'
    else:
      description = ''

    default_value_str = _get_param_default_value(param)

    if isinstance(param.get_default_value(), GObject.GEnum):
      default_enum_value_as_string = _get_enum_value_as_string(param.get_default_value())
      if default_enum_value_as_string is not None:
        default_value_str = default_enum_value_as_string

    if default_value_str is not None:
      default_value_str = f' (default: {default_value_str})'
    else:
      default_value_str = ''

    if description:
      param_str = f'{param_prefix}{name}{default_value_str} - {description}'
    else:
      param_str = f'{param_prefix}{name}{default_value_str}'

    param_str = textwrap.fill(
      param_str,
      width=_DOCSTRING_LINE_LENGTH - len(_BODY_INDENT) - len(param_prefix),
      subsequent_indent=_BODY_INDENT + ' ' * len(param_prefix),
      break_on_hyphens=False)

    param_str = f'\n{_BODY_INDENT}' * 2 + param_str

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


def _get_enum_value_as_string(enum_value):
  enum_type = type(enum_value)

  if enum_type.__module__.startswith('gi.repository.'):
    enum_type_module_name = enum_type.__module__[len('gi.repository.'):]
  else:
    enum_type_module_name = enum_type.__module__

  default_value_name = None
  for name in dir(enum_type):
    if enum_value.value_name.endswith(name):
      default_value_name = name
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
      arg=_pythonize(proc_arg.name),
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

    if isinstance(proc_arg.get_default_value(), GObject.GEnum):
      default_value_as_string = _get_enum_value_as_string(proc_arg.get_default_value())
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


def _pythonize(str_):
  return str_.replace('-', '_').replace(':', '__')


def _get_proc_argument_type_hint(proc_arg):
  arg_type_name = _parse_type(proc_arg, default_type='GObject.Value')

  # Use dummy code with the desired annotation. It is more convenient to create
  # an annotation node this way.
  dummy_func_with_type_hint = f'def foo(arg: {arg_type_name}): pass'

  node = ast.parse(dummy_func_with_type_hint)

  return node.body[0].args.args[0].annotation


def _parse_type(proc_arg, default_type=None):
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
  elif value_type.name.startswith('Gimp'):
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


def _get_gimp_pdb_procedures():
  """Retrieves a list of GIMP PDB procedures."""
  query_procedure = Gimp.get_pdb().lookup_procedure('gimp-pdb-query')
  config = query_procedure.create_config()
  for prop in config.list_properties():
    if prop.value_type == Gimp.Procedure.__gtype__:
      continue

    config.set_property(prop.name, '')

  return {
    proc_name: Gimp.get_pdb().lookup_procedure(proc_name)
    for proc_name in query_procedure.run(config).index(1)
  }


def _get_gegl_procedures():
  """Retrieves a list of GEGL operations."""
  return Gegl.list_operations()


def write_stub_file(dirpath, root_node):
  os.makedirs(dirpath, exist_ok=True)

  stub_filepath = os.path.join(dirpath, f'{PYPDB_MODULE_NAME}.pyi')
  with open(stub_filepath, 'w', encoding=TEXT_FILE_ENCODING) as stub_file:
    stub_file.write(ast.unparse(root_node))
