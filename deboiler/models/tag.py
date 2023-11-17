from dataclasses import dataclass


@dataclass
class TagDefinition:
    """
    To define LXML tags.
    If partial_match = True, the tag should contain the given `name`.
    Otherwise, it should be an exact match.

    For instance, `TagDefinition("div", False)` only matches to `div` tags,
    whereas `TagDefinition("nav", True)` will match to any tag that includes
    `nav`, such as `nav` and `navigation`.

    """

    name: str
    partial_match: bool = True

    def to_xpath(self):
        """
        Creates the xpath to be used to match the given tag.

        For instance:
        TagDefinition("div", False) --> "self::{div}"
        TagDefinition("nav", True)  --> "contains(local-name(), '{nav}')"

        """

        if self.partial_match:
            return f"contains(local-name(), '{self.name}')"
        else:
            return f"self::{self.name}"
