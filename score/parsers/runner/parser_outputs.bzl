"""Provider shared by parser rules and the aggregate runner rule."""

ParserOutputsInfo = provider(fields = {
    "registry_file": "Serialized ModelRegistry pickle output.",
})
