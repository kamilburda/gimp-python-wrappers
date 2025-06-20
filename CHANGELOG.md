# 5.5

* pypdb: Fixed handling of enum values if a GIMP installation contains PyGObject version 3.50.0 or later.
* pypdb: Fixed GEGL operations containing `_` in their names not being accessible.
* pypdb: Passing positional arguments to GIMP PDB procedures now yields a clearer error message.
* procedure: Added `init_gegl` parameter that allows toggling automatic calling of `Gegl.init()` when a procedure starts.


# 5.4

* Provided a workaround for registration of procedure arguments or return values whose type represents a GIMP-related object, e.g. `Gegl.Color`.


# 5.3

* Allowed registration of procedures of type `Gimp.ExportProcedure`, `Gimp.BatchProcedure` and `Gimp.VectorLoadProcedure`.
* Further clarified the Readme.
* The `generate-pdb-stubs.py` file is now executable.


# 5.2

* Clarified contents of Readme for improved readability.


# 5.1

* The stub generator is now guaranteed to be accessible in GIMP even if no images are opened.


# 5.0

* Updated the `pdb` object, script and the generated stubs according to changes in GIMP 3.0.0-RC3.
* Added more information to several parameter types in the generated stub file. For example, the description for numeric parameters now contains minimum and maximum values (if different from the default minimum and maximum values), the description for `Gio.File` parameters indicates whether they are files or folders for opening/saving, etc.
* Object array parameters (images, drawables, ...) are now annotated in the stub file as lists.
* Updated type annotations for parameters that can be `None` (e.g. `Gimp.Image` or `Gimp.Layer`) in the stub file.
* Slightly optimized access to PDB procedures and GEGL operations via the `pdb` object.
* Improved GUI for the output directory for the stub generator.
* Arguments whose names match a Python keyword can now be passed with a trailing `_`, e.g. `lambda_` (passing `lambda=<value>` would result in a syntax error).


# 4.2

* Fixed `CRITICAL` warnings issued by GIMP when applying layer effects.


# 4.1

* Added allowed string values to the function documentation of the generated stub file for `Gimp.Choice` arguments or GEGL enums converted to `Gimp.Choice` arguments.
* Default values for string arguments in the function documentation are now quoted for improved readability.
* Fixed a potential bug where certain GEGL enums were unnecessarily converted to a string (since GIMP converts many of these enums to strings for readability).


# 4.0

* Added support for layer effects (filters, GEGL operations). These can be called via the `pdb` object. For example, the `gegl:gaussian-blur` effect can be called as `pdb.gegl__gaussian_blur(layer, std_dev_x=5.0, std_dev_y=5.0)`.
* Procedures can now only be called with keyword arguments (i.e. it is no longer possible to call procedures with positional arguments). This change is meant to encourage plug-in developers to make the client code more readable. The only positional argument allowed is a `Gimp.Layer` instance for layer effects.
* Updated the script and the generated stubs according to changes in GIMP 3.0.0-RC2.
* The `procedure` module now automatically initializes the `Gegl` module by invoking `Gegl.init()` before the start of a procedure.
* The generated stub file `pypdb.pyi` now also contains private attributes from the `_PyPDB` class, `PDBProcedure` class and all its subclasses. This avoids IDE warnings related to unrecognized attributes.


# 3.2

* Fixed procedure registration if the same list of arguments was reused for multiple plug-in procedures.


# 3.1

* Fixed calling PDB procedures with keyword arguments containing underscores.


# 3.0

* Updated the script and the generated stubs to work with GIMP 3.0.0-RC1.
* For the pre-generated stub, default values in descriptions are now only included for "basic" types, specifically `int`, `float`, `bool`, `str` and `bytes`.
* For the pre-generated stub, fixed formatting of arguments and return values without a description (blurb).


# 2.0

* Added a module to simplify registration of plug-ins.
* Updated the script to work with GIMP 2.99.18. GIMP 2.99.16 is no longer supported.
* Updated the signature of PDB procedures. All arguments can now be omitted and their default values will be used. However, note that the stub file will display `None` as the default value for all arguments even if it is not the default (since the user can save different defaults for a particular PDB procedure, the defaults displayed in the stub file would no longer be accurate).


# 1.3

* Arguments to PDB procedures are now automatically wrapped with `GObject.Value()`.
* Updated the stub file to remove `GObject.Value` as an accepted type for PDB arguments.


# 1.2

* Prevented errors when importing the `pypdb` module when GIMP is not fully initialized.


# 1.1

* Allowed access to PDB procedures via strings as `pdb['some-procedure-name']`.
* Python exceptions are now raised if attempting to access non-existent procedure names.


# 1.0

* Initial release.
