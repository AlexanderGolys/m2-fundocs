-- Helper for extracting help text in a structured envelope.

helpProbeText = method()

joinLines = items -> (
    out := "";
    for i from 0 to #items - 1 do (
        if i > 0 then out = concatenate(out, "\n");
        out = concatenate(out, items#i);
    );
    out
);

joinComma = items -> (
    out := "";
    for i from 0 to #items - 1 do (
        if i > 0 then out = concatenate(out, ",");
        out = concatenate(out, items#i);
    );
    out
);

isSectionHeaderAt = (docLines, i) -> (
    i + 1 < #docLines and docLines#i != "" and match("^[=-]{3,}$", docLines#(i + 1))
);

findSectionIndex = (docLines, titlePattern) -> (
    found := -1;
    for i from 0 to #docLines - 2 do (
        if found == -1 and match(titlePattern, docLines#i) and match("^[=-]{3,}$", docLines#(i + 1)) then (
            found = i;
        );
    );
    found
);

findNextSectionIndex = (docLines, startIndex) -> (
    next := #docLines;
    for i from startIndex to #docLines - 2 do (
        if next == #docLines and isSectionHeaderAt(docLines, i) then (
            next = i;
        );
    );
    next
);

signatureIdFromTuple = tuple -> (
    name := toString(tuple_0);
    inputNames := {};
    for i from 1 to length tuple - 1 do (
        inputNames = append(inputNames, toString(tuple_i));
    );
    concatenate(name, "(", joinComma inputNames, ")")
);

parseNetHelp = netText -> (
    docLines := lines netText;
    header := if #docLines > 0 then docLines#0 else "";

    descriptionLines := {};
    descriptionHeader := findSectionIndex(docLines, "^Description$");
    if descriptionHeader != -1 then (
        start := descriptionHeader + 2;
        while start < #docLines and docLines#start == "" do start = start + 1;
        stop := findNextSectionIndex(docLines, start);
        for i from start to stop - 1 do (
            line := docLines#i;
            if not match("^\\+-[-+]*\\+$", line) and not match("^\\|", line) then (
                descriptionLines = append(descriptionLines, line);
            );
        );
    );

    examples := {};
    inExample := false;
    current := {};
    for i from 0 to #docLines - 1 do (
        line := docLines#i;
        if match("^\\+-[-+]*\\+$", line) then (
            if not inExample then (
                inExample = true;
                current = {line};
            ) else (
                current = append(current, line);
                nextIsPipe := i + 1 < #docLines and match("^\\|", docLines#(i + 1));
                if not nextIsPipe then (
                    examples = append(examples, joinLines current);
                    inExample = false;
                    current = {};
                );
            );
        ) else if inExample then (
            current = append(current, line);
        );
    );

    ways := {};
    waysHeader := findSectionIndex(docLines, "^Ways to use .*$");
    if waysHeader != -1 then (
        waysStart := waysHeader + 2;
        while waysStart < #docLines and docLines#waysStart == "" do waysStart = waysStart + 1;
        waysStop := findNextSectionIndex(docLines, waysStart);
        for i from waysStart to waysStop - 1 do (
            line := docLines#i;
            if match("^  \\* ", line) then (
                ways = append(ways, substring(line, 4, #line - 4));
            );
        );
    );

    new HashTable from {
        "header" => header,
        "description" => joinLines descriptionLines,
        "examples" => examples,
        "ways" => ways
    }
);

emitParsedBlock = (prefix, parsed) -> (
    out := concatenate(
        "M2HELP2|", prefix, "HEADER=", parsed#"header", "\n",
        "M2HELP2|", prefix, "DESCRIPTION_BEGIN\n",
        parsed#"description", "\n",
        "M2HELP2|", prefix, "DESCRIPTION_END\n"
    );

    for example in parsed#"examples" do (
        out = concatenate(
            out,
            "M2HELP2|", prefix, "EXAMPLE_BEGIN\n",
            example,
            "\nM2HELP2|", prefix, "EXAMPLE_END\n"
        );
    );

    for way in parsed#"ways" do (
        out = concatenate(out, "M2HELP2|", prefix, "WAYS_ITEM=", way, "\n");
    );
    out
);

helpProbeText String := symbolName -> (
    helpProbeText(symbolName, false)
)

helpProbeText (String, Boolean) := (symbolName, includeMethods) -> (
    target := getGlobalSymbol symbolName;
    netText := toString net help target;
    parsedTop := parseNetHelp netText;
    out := concatenate(
        "M2HELP2|SYMBOL=", symbolName, "\n",
        emitParsedBlock("", parsedTop)
    );

    if includeMethods then (
        methodTuples := try(toList methods(value target)) else {};
        for methodTuple in methodTuples do (
            signatureId := signatureIdFromTuple methodTuple;
            methodText := try(toString net help methodTuple) else null;
            if methodText =!= null then (
                parsedMethod := parseNetHelp methodText;
                out = concatenate(
                    out,
                    "M2HELP2|METHOD_BEGIN=", signatureId, "\n",
                    emitParsedBlock("METHOD_", parsedMethod),
                    "M2HELP2|METHOD_END\n"
                );
            );
        );
    );
    out
)
