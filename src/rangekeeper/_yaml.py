"""Decode declarations with one explicit policy: no aliases or executable tags."""


def decode(content: str | bytes):
    if not isinstance(content, (str, bytes)):
        raise TypeError("YAML content must be text or bytes")
    import yaml
    from yaml.resolver import BaseResolver

    class StrictLoader(yaml.SafeLoader):
        def compose_node(self, parent, index):
            if self.check_event(yaml.AliasEvent):
                raise ValueError(
                    "YAML aliases are not supported; use explicit references"
                )
            return super().compose_node(parent, index)

    def mapping(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=True)
            if type(key) is not str:
                raise ValueError("YAML keys must be strings")
            if key in result:
                raise ValueError(f"Duplicate YAML key: {key}")
            result[key] = loader.construct_object(value_node, deep=True)
        return result

    StrictLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        return yaml.load(content, Loader=StrictLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc
