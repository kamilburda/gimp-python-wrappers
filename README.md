# Wrappers for GIMP Python Plug-ins

This repository aims to improve development of Python plug-ins for [GIMP 3.0](https://www.gimp.org/downloads/devel/) by providing the following:

* A simplified means to call GIMP plug-ins, built-in procedures, and apply layer effects (GEGL operations):
  ```
  ...
  pdb.plug_in_jigsaw(image=image, drawables=[layer])
  ...
  pdb.gegl__gaussian_blur(layer, std_dev_x=5.0, std_dev_y=4.0, abyss_policy='clamp')
  ...
  ```

* A stub file that can be used in integrated development environments (IDEs) to display code completion suggestions for GIMP procedures, plug-ins and layer effects (arguments, return values, documentation) as you type. A pre-generated stub file is provided, but you may generate one yourself if you use custom plug-ins. Stub files are supported by several IDEs such as [PyCharm](https://www.jetbrains.com/help/pycharm/stubs.html), [PyDev](https://www.pydev.org/manual_101_install.html) (an Eclipse plug-in) or [Visual Studio Code via a plug-in](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance).

* A simplified means to register Python plug-ins. See the bottom of the [`generate-pdb-stubs` module](generate-pdb-stubs/generate-pdb-stubs.py) for an example.


## Requirements

* GIMP 3.0 or later
* Python 3.9 or later


## Usage

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

IDEs supporting the `.pyi` stub files should now display suggested functions as you type. 

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
    pdb.plug_in_jigsaw(image=image, drawables=[layer])
    ...
    pdb.gegl__gaussian_blur(layer, std_dev_x=5.0, std_dev_y=4.0, abyss_policy='clamp')
    ...
```

Alternatively, you can call the functions as strings:

```
    pdb['plug-in-jigsaw'](image=image, drawables=[layer])
    ...
    pdb['gegl:gaussian-blur'](layer, std_dev_x=5.0, std_dev_y=4.0, abyss_policy='clamp')
    ...
```

The names of layer effects (GEGL operations) start with  `gegl__` or `svg__`.
The `-` and `:` characters in the original names of GIMP procedures/plug-ins/layer effects are replaced with `_` and `__`, respectively.

Function arguments can only be specified as keyword arguments (`<argument name>=<value>`).
The only positional argument allowed is a `Gimp.Layer` object as the first argument, and only for layer effects.

You can omit any arguments, in which case their default values will be used.
Note, however, that omitting some arguments may result in an error, e.g. if a function requires an image or a layer that is left unspecified.

All layer effects have the following common parameters (all of them end with `_` to avoid possible name clashes with other parameters):
* `blend_mode_` - the `Gimp.LayerMode` for the effect (default, dodge, burn, hard light, ...).
* `opacity_` - the opacity of the effect.
* `merge_filter_` - if ``True``, the effect will be applied destructively, i.e. will be merged into the layer.
* `visible_` - if ``False``, the effect will be added, but will not be applied.
* `filter_name_` - a custom name for the effect. If omitted, a default name is assigned by GIMP.

Return values are returned as a Python list (in case of multiple return values) or directly as a Python object (in case of a single return value). Functions having no return values return `None`.

The exit status is available as the `pdb.last_status` property (in the official GIMP API, this is a part of the returned `Gimp.ValueArray` as the first element). This does not apply to layer effects.

The `pdb.last_error` attribute contains an error message if the last function called via `pdb` failed. Likewise, this does not apply to layer effects.


### Registering your Python plug-in procedures

1. Copy the `wrappers/procedure.py` module to your plug-in directory.
2. Within the main file of your plug-in (a Python script with same name as its parent directory) import the `procedure` module and call `procedure.register_procedure()` to register a single PDB procedure. See the bottom of the [`generate-pdb-stubs` module](generate-pdb-stubs/generate-pdb-stubs.py) for an example. The `procedure.register_procedure()` function documentation contains details on the parameters and how they must be formatted.
3. At the end of your main Python module, call `procedure.main()`.


### Running the Stub Generator

While this repository provides a pre-generated stub file, it may quickly become obsolete in future GIMP versions and does not display hints for custom plug-ins and scripts you have installed.
In such cases, you may want to generate the stub file yourself as described below.

To generate a new stub file, this repository must be installed as a GIMP plug-in.

1. Locate the directory for plug-ins in your GIMP installation by going to `Edit → Preferences → Folders → Plug-Ins`.
2. Choose one of the listed directories there (preferably the one located under a user directory rather than the system directory) and copy the `gimp-python-wrappers` directory to one of the directories listed in step 1.
3. If you have GIMP opened, restart GIMP.

To run the stub generator, open GIMP and choose `Filters → Development → Python-Fu → Generate GIMP PDB Stubs for Python`.

You may adjust the output directory.

Alternatively, you can run the generator from the Python-Fu console - choose `Filters -> Development -> Python-Fu -> Python Console` and enter

```
procedure = Gimp.get_pdb().lookup_procedure('generate-pdb-stubs')
config = procedure.create_config()
config.set_property('output-dirpath', <your desired output directory>)
procedure.run(config)
```
