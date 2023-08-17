from typing import Optional

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp


_gimp_pdb = Gimp.get_pdb()


class _PyPDB:

  def __init__(self):
    self._last_status = None
    self._last_error = None

    self._proc_cache = {}

  @property
  def last_status(self):
    return self._last_status

  @property
  def last_error(self):
    return self._last_error

  def __getattr__(self, name):
    proc_name = name.replace('_', '-')

    if proc_name not in self._proc_cache:
      self._proc_cache[proc_name] = PyPDBProcedure(self, proc_name)

    return self._proc_cache[proc_name]


class PyPDBProcedure:

  def __init__(self, pdb_wrapper, proc_name):
    self._pdb_wrapper = pdb_wrapper
    self._name = proc_name

    self._info = _gimp_pdb.lookup_procedure(self._name)
    self._has_run_mode = self._get_has_run_mode()

  @property
  def name(self):
    return self._name

  @property
  def info(self):
    return self._info

  @property
  def has_run_mode(self):
    return self._has_run_mode

  def __call__(
        self,
        *args,
        run_mode: Gimp.RunMode = Gimp.RunMode.NONINTERACTIVE,
        config: Optional[Gimp.ProcedureConfig] = None):
    if config is None:
      if self._has_run_mode:
        result = _gimp_pdb.run_procedure(self._name, [run_mode, *args])
      else:
        result = _gimp_pdb.run_procedure(self._name, args)
    else:
      result = _gimp_pdb.run_procedure_config(self._name, config)

    if result is None:
      return None

    result_list = [result.index(i) for i in range(result.length())]

    if len(result_list) > 0:
      if isinstance(result_list[0], Gimp.PDBStatusType):
        self._pdb_wrapper._last_status = result_list.pop(0)

    if len(result_list) > 0:
      if self._pdb_wrapper._last_status in [
            Gimp.PDBStatusType.SUCCESS, Gimp.PDBStatusType.PASS_THROUGH]:
        self._pdb_wrapper._last_error = None
      else:
        self._pdb_wrapper._last_error = result_list.pop(0)

    if result_list:
      if len(result_list) == 1:
        return result_list[0]
      else:
        return result_list
    else:
      return None

  def _get_has_run_mode(self):
    proc_arg_info = self._info.get_arguments()
    if proc_arg_info and proc_arg_info[0].value_type.pytype:
      return issubclass(proc_arg_info[0].value_type.pytype, Gimp.RunMode)
    else:
      return False


pdb = _PyPDB()
