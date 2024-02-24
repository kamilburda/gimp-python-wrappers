# Wrappers for GIMP Python Plug-ins

This repository aims to improve development of Python plug-ins for [GIMP 2.99.18](https://www.gimp.org/downloads/devel/) by providing the following:

* A simplified interface to call procedures and plug-ins from the GIMP procedural database (PDB) - the same style used in Python plug-ins for GIMP 2.10 and lower:
  
  ```
  pdb.some_procedure_name(argument1, argument2, ...)
  ```

* A stub file that can be used in IDEs to display code completion suggestions for GIMP PDB procedures (arguments, return values, documentation) as you type. A pre-generated stub file is provided, but you may generate one yourself if you use custom plug-ins. Stub files are supported by several IDEs such as [PyCharm](https://www.jetbrains.com/help/pycharm/stubs.html), [PyDev](https://www.pydev.org/manual_101_install.html) (an Eclipse plug-in) or [Visual Studio Code via a plug-in](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance).

* A simplified interface to register plug-ins, resembling the style used in Python plug-ins for GIMP 2.10 and lower. See the [`generate-pdb-stubs` module](generate-pdb-stubs/generate-pdb-stubs.py#L52) for an example.


## Requirements

* GIMP 2.99.18 (will **not** work in earlier versions, might work in later versions)
* Python 3.9 or later


## Usage

### Running the Stub Generator

While this repository provides a pre-generated stub file, it may quickly become obsolete in future GIMP versions and does not display hints for custom plug-ins and scripts you have installed.
In such cases, you may want to generate the stub file yourself as described below.

To generate a new stub file, this repository must be installed as a GIMP plug-in.

1. Locate the directory for plug-ins in your GIMP installation by going to `Edit → Preferences → Folders → Plug-Ins`.
2. Choose one of the listed directories there (preferably the one located under a user directory rather than the system directory) and copy the `gimp-python-pdb-wrapper` directory to one of the directories listed in step 1.
3. If you have GIMP opened, restart GIMP.

To run the stub generator, open GIMP and choose `Filters → Development → Python-Fu → Generate GIMP PDB Stubs for Python`.

You may adjust the output directory.

Alternatively, you can run the generator from the Python-Fu console - choose `Filters -> Development -> Python-Fu -> Console` and enter

```
procedure = Gimp.get_pdb().lookup_procedure('generate-pdb-stubs')
config = procedure.create_config()
config.set_property('output-dirpath', <your desired output directory>)
procedure.run(config)
```

### Adding the GIMP PDB wrapper and the stub file to your IDE

Place the `pypdb.py` and the `pypdb.pyi` file in the same subdirectory within your Python plug-in.

Example:

```
<directory containing GIMP plug-ins>/
    some-plug-in/
        some-plug-in.py
        pypdb.py
        pypdb.pyi
```

IDEs supporting the `.pyi` stub files should now display suggested PDB procedures as you type. 

It is also advised to add `.pyi` files to your `.gitignore` so that git ignores these files:

```
*.pyi
```


### Using the GIMP PDB wrapper

Example of importing and using the PDB wrapper in a GIMP Python plug-in:

```
from pypdb import pdb


def run_plugin(procedure, run_mode, image, drawable, n_drawables, config, data):
    ...
    pdb.plug_in_gauss(image, drawable, 5.0, 4.0, 1)
    ...
```

Instead of specifying all arguments, you can omit any arguments and specify them as keyword arguments:

```
pdb.plug_in_gauss(image, drawable, vertical=4.0)
```

Other arguments will be assigned their default values.

You can adjust the run mode by passing the `run_mode=` keyword argument. If not specified, the run mode defaults to `Gimp.RunMode.NONINTERACTIVE`.

Returned values are returned as a Python list (in case of multiple return values) or directly as a Python object (in case of a single return value). Procedures having no return values return `None`.

The exit status that was a part of the `Gimp.ValueArray` as the first element is now available as the `pdb.last_status` property.

You can access GIMP PDB procedure information ([`Gimp.Procedure`](https://developer.gimp.org/api/3.0/libgimp/class.Procedure.html) object) via the `info` property, e.g. `pdb.plug_in_gauss.info`.

### Registering plug-in procedures

Import the `wrappers/procedure.py` module and call `procedure.register_procedure()` to register a single PDB procedure. See the [`generate-pdb-stubs` module](generate-pdb-stubs/generate-pdb-stubs.py#L52) for an example.

At the end of your main Python module, call `procedure.main()`.
