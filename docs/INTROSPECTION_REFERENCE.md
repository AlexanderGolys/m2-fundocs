# Introspection Reference by Object Kind

This document maps object kinds to the runtime commands and documentation pages used
by the extraction pipeline.

## Shared setup

Run this first when you need documentation classes loaded:

```m2
needsPackage "Text";
needsPackage "Macaulay2Doc";
```

## Core documentation pages

- Macaulay2 language overview:
  `https://macaulay2.com/doc/Macaulay2/share/doc/Macaulay2/Macaulay2Doc/html/___The_sp__Macaulay2_splanguage.html`
- Symbols used as optional argument names/values:
  `https://macaulay2.com/doc/Macaulay2/share/doc/Macaulay2/Macaulay2Doc/html/_symbols_spused_spas_spthe_spname_spor_spvalue_spof_span_spoptional_spargument.html`

The optional-argument symbol list in docs is treated as a seed list. Runtime probing is
authoritative for discovering additional symbols.

## Function

Use these commands on callable names such as `ideal`:

- `class f` to classify method function type
- `methods f` to list installed methods and dispatch domains
- `options f` to list optional arguments
- `peek f` for a low-level view
- `toString f` for stable textual display
- `help f` and `about f` for user-facing descriptions

Collected fields:

- brief/description/examples
- inputs/outputs
- options
- installed methods
- dispatch metadata

## Installed method variant

Primary source is `methods f`. Each entry is normalized into a separate method object.

- Signature is parsed from method tuple `(name, InputType, ...)`
- Input types become explicit links
- Reverse links are added from each input type back to the method

Recommended command while debugging one method signature:

- `methods f`

## Type

Use these commands on type-like symbols and values:

- `class T`
- `parent T`
- `showClassStructure`
- `showStructure`
- `peek T`
- `help T` and `about T`

Collected fields:

- brief/description/examples
- type name/class
- parent type (required)
- reverse links to methods that accept this type as input

## Operator

Operators are represented as a separate kind from functions even though they are method-like.

Use these commands:

- `operatorAttributes op` where available
- `methods op` (or corresponding callable form)
- `help op`, `about op`
- `class op`, `peek op`

Collected fields:

- operator form (binary/prefix/postfix/other)
- precedence
- installable/flexible flag
- augmented assignment syntax variants (when present)
- method dispatch links

## Symbol used in options

These symbols can appear as option keys and option values.

Use these commands:

- `options f` to discover key/value symbols
- `help sym`, `about sym`, `peek sym`, `class sym`

Collected fields:

- symbol identity and kind
- where used as option key
- where used as option value
- reverse links back from symbol to all referencing functions/methods

## Notes on bidirectional linking

Pipeline requirement:

- every forward relation is accompanied by a reverse index entry

Examples:

- `method -> inputType` implies `type -> usableByMethods`
- `function -> hasMethod` implies `method -> function`
- `function -> acceptsOptionSymbol` implies `symbol -> usedBy`
