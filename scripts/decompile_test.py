import uncompyle6
with open("import_options_data.py", "w") as fileobj:
    uncompyle6.decompile_file("__pycache__/import_options_data.cpython-313.pyc", fileobj)
