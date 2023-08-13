"""Generating stubs for the GIMP procedural database (PDB)."""

import ast
import inspect
import os
import re
import textwrap

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp


CURRENT_MODULE_DIRPATH = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

PYPDB_MODULE_NAME = 'pypdb'
PYPDB_MODULE_FILEPATH = os.path.join(CURRENT_MODULE_DIRPATH, f'{PYPDB_MODULE_NAME}.py')
STUB_MODULE_FILEPATH = os.path.join(CURRENT_MODULE_DIRPATH, f'{PYPDB_MODULE_NAME}.pyi')
TEXT_FILE_ENCODING = 'utf-8'

_PYPDB_CLASS_NAME = '_PyPDB'

_INDENT = '    '
_BODY_INDENT = _INDENT * 2
_DOCSTRING_LINE_LENGTH = 80


def generate_pdb_stubs(output_filepath):
  if not os.path.isfile(PYPDB_MODULE_FILEPATH):
    raise RuntimeError(f'pypdb module does not exist at "{os.path.dirname(PYPDB_MODULE_FILEPATH)}"')

  with open(PYPDB_MODULE_FILEPATH, 'r', encoding=TEXT_FILE_ENCODING) as f:
    root_node = ast.parse(f.read())

  _remove_implementation_of_functions(root_node)

  pypdb_class_node = _get_pypdb_class_node(root_node)

  for proc_name, proc in sorted(_get_pdb_procedures().items()):
    _insert_pdb_procedure_node(pypdb_class_node, proc_name, proc)

  write_stub_file(output_filepath, root_node)


def _remove_implementation_of_functions(root_node):
  for child in ast.walk(root_node):
    if isinstance(child, ast.FunctionDef):
      child.body = [ast.Pass()]


def _get_pypdb_class_node(root_node):
  pypdb_class_node = next(
    (child for child in root_node.body
     if isinstance(child, ast.ClassDef) and child.name == _PYPDB_CLASS_NAME),
    None)

  if pypdb_class_node is None:
    raise RuntimeError(f'"{_PYPDB_CLASS_NAME}" class not found in "{PYPDB_MODULE_FILEPATH}"')

  return pypdb_class_node


def _insert_pdb_procedure_node(pypdb_class_node, procedure_name, procedure):
  procedure_node = _create_pdb_procedure_node(procedure_name, procedure)

  _insert_pdb_procedure_arguments(procedure_node, procedure)
  _insert_pdb_procedure_docstring(procedure_node, procedure)

  pypdb_class_node.body.append(procedure_node)


def _create_pdb_procedure_node(procedure_name, procedure):
  func_name = _pythonize(procedure_name)

  # Constructing a `FunctionDef` node this way is more readable and less error-prone.
  func_positional_args_str = 'self, *'
  func_run_mode_arg_str = 'run_mode: Gimp.RunMode = Gimp.RunMode.NONINTERACTIVE'
  func_config_arg_str = 'config: Optional[Gimp.ProcedureConfig] = None'

  has_run_mode = _has_procedure_run_mode_argument(procedure)
  if has_run_mode:
    func_base_arguments_str = (
      f'{func_positional_args_str}, {func_run_mode_arg_str}, {func_config_arg_str}')
  else:
    func_base_arguments_str = f'{func_positional_args_str}, {func_config_arg_str}'

  func_base_docstring = '""'

  func_base_signature_str = (
    f'def {func_name}({func_base_arguments_str}):\n{_INDENT}{func_base_docstring}\n{_INDENT}pass')

  procedure_node = ast.parse(func_base_signature_str).body[0]

  return procedure_node


def _insert_pdb_procedure_arguments(procedure_node, procedure):
  proc_args = procedure.get_arguments()

  if _has_procedure_run_mode_argument(procedure):
    proc_args = proc_args[1:]

  for proc_arg in reversed(proc_args):
    arg_node = ast.arg(
      arg=_pythonize(proc_arg.name),
      annotation=None,
      col_offset=None,
      end_col_offset=None,
      lineno=None,
      end_lineno=None,
      type_comment=None,
    )
    procedure_node.args.args.insert(1, arg_node)


def _insert_pdb_procedure_docstring(procedure_node, procedure):
  proc_docstring = ''

  proc_docstring = _add_proc_blurb_to_docstring(procedure, proc_docstring)
  proc_docstring = _add_image_types_to_docstring(procedure, proc_docstring)
  proc_docstring = _add_proc_help_to_docstring(procedure, proc_docstring)
  proc_docstring = _add_proc_params_to_docstring(procedure, proc_docstring)

  proc_docstring += f'\n{_BODY_INDENT}'

  procedure_node.body[0].value.value = proc_docstring


def _add_proc_blurb_to_docstring(procedure, proc_docstring):
  proc_blurb = procedure.get_blurb()
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


def _add_image_types_to_docstring(procedure, proc_docstring):
  proc_image_types = procedure.get_image_types()
  if proc_image_types:
    if proc_docstring:
      proc_docstring += f'\n{_BODY_INDENT}' * 2
    proc_docstring += f'Image types: {proc_image_types}'

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
  proc_args = procedure.get_arguments()

  if _has_procedure_run_mode_argument(procedure):
    proc_args = proc_args[1:]

  if not proc_args:
    return proc_docstring

  proc_params = 'Parameters:'
  param_prefix = '* '

  for arg in proc_args:
    if arg.default_value is not None:
      default_value_str = f' (default: {arg.default_value})'
    else:
      default_value_str = ''

    name = _pythonize(arg.name)

    description = arg.blurb
    if description:
      if not description.endswith('.'):
        description += '.'
    else:
      description = ''

    param_str = f'{param_prefix}{name}{default_value_str} - {description}'
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


def _pythonize(str_):
  return str_.replace('-', '_')


def _has_procedure_run_mode_argument(proc):
  proc_args = proc.get_arguments()
  if proc_args and proc_args[0].value_type.pytype is not None:
    return issubclass(proc_args[0].value_type.pytype, Gimp.RunMode)
  else:
    return False


def _get_pdb_procedures():
  """Retrieves a list of GIMP PDB procedures."""
  return {
    proc_name: Gimp.get_pdb().lookup_procedure(proc_name)
    for proc_name in Gimp.get_pdb().run_procedure('gimp-pdb-query', [''] * 7).index(1)
  }


def write_stub_file(filepath, root_node):
  os.makedirs(os.path.dirname(filepath), exist_ok=True)

  with open(filepath, 'w', encoding=TEXT_FILE_ENCODING) as stub_file:
    stub_file.write(ast.unparse(root_node))
