rmdocs
===

A cli tool to convert .rm, .rmdoc and the `xochitl` folder of the [reMarkable 2](https://remarkable.com/) to PDFs.
It aims to reproduce reMarkable 2 output as faithfully as possible.

> [!IMPORTANT]
> It is **only** compatible with `.rm` version 6.
> See [below](#Compatibility)

> [!CAUTION]
> I still consider this in early development.

## Usage

- Convert a single `.rm` file using `rmdocs my_page.rm [destination folder]`. `[destination folder]` defaults to
  current folder.
- Convert a single `.rmdoc` file using `rmdocs my_document.rmdoc [destination folder]`. `[destination folder]` defaults
  to current folder.
- Convert a folder containing a collection of `.rm` or `.rmdoc` (can't be mixed) using `rmdocs [source folder] 
[destination folder]`. `[destination folder]` is required.
- Convert the `xochitl` folder at `/home/root/.local/share/remarkable/xochitl/` on the remarkable using `rmdocs [source folder] 
[destination folder]`. `[destination folder]` is required.

If you have compatibility or assertions issues, please refer to [below](#Compatibility).

## Installation

1. Install [pipx](https://pipx.pypa.io/stable/how-to/install-pipx/)
2. Install `libcairo2`. For instance, on debian based system use `apt install libcairo2`.
3. Install `rmdocs` via `pipx install rmdocs`

> [!NOTE]  
> Alternatively, you can use regular venv.

## Compatibility

This software is only compatible with page version 6, and I do not plan on making it support other page version. For
non-compatible pages a warning text will be shown instead of your strokes. **Going to each of these pages individually
and drawing (even if removing afterward) makes the reMarkable updates the page to v6.**

Additionally, as there is no official API for reMarkable file structure, many assertion are made based on the files
available while developing this software. The output of the software will show them as `AssertionException`. Please 
consider opening an issue when you have such errors.

## Acknowledgment, contributions and license

This uses [rmscene](https://github.com/ricklupton/rmscene), and part of svg creation is based
of [rmc](https://github.com/ricklupton/rmc).

This software is mainly released under the MIT license. Certains files (from rmc) regarding the svg creation are under
LGPL.

Contributions are welcomed :).