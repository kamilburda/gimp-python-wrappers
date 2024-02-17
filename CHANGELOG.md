Upcoming
========

* Updated the script to work with GIMP 2.99.18. GIMP 2.99.16 is no longer supported.
* Updated the signature of PDB procedures. All arguments can now be omitted and their default values will be used. However, note that the stub file will display `None` as the default value for all arguments even if it is not the default (since the user can save different defaults for a particular PDB procedure, the defaults displayed in the stub file would no longer be accurate).

1.3
===

* Arguments to PDB procedures are now automatically wrapped with `GObject.Value()`.
* Updated the stub file to remove `GObject.Value` as an accepted type for PDB arguments.

1.2
===

* Prevented errors when importing the `pypdb` module when GIMP is not fully initialized.


1.1
===

* Allowed access to PDB procedures via strings as `pdb['some-procedure-name']`.
* Python exceptions are now raised if attempting to access non-existent procedure names.


1.0
===

* Initial release.
