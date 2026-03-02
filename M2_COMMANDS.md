# Helpful Macaulay2 CLI Commands

This note collects commands that are useful when introspecting Core builtins for structured docs generation.

## Documentation and Descriptions

- `help name`  
  Show builtin documentation for `name`.

- `about name`  
  Show a description view that can differ slightly from `help name`.

## Object and Type Introspection

- `peek x`  
  Show a more primitive/internal representation of `x` than printing `x` directly.

- `class X`  
  Return the class/type of `X`.

- `parent x`  
  Return the parent object type/domain for `x`.

- `toString x`  
  Convert `x` to a string representation.

## Methods and Options

- `options x`  
  List available options for method/function `x`.

- `methods x`  
  List installed methods associated with function/domain `x`.

## Class and Structure Trees

- `showClassStructure`  
  Display tree-like class/type structure information.

- `showStructure`  
  Display tree-like object/type structure information.

## Package Prerequisites for Doc Class Access

Load these before exploring some documentation class objects:

- `needsPackage "Text";`
- `needsPackage "Macaulay2Doc";`

Combined one-liner:

- `needsPackage "Text"; needsPackage "Macaulay2Doc";`

## Suggested Quick Session

```m2
needsPackage "Text"; needsPackage "Macaulay2Doc";
about ideal
help ideal
class ideal
methods ideal
options ideal
peek ideal
```
