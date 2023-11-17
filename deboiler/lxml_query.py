from deboiler.models.lxml_node import LxmlNode, LxmlTree
from deboiler.models.tag import TagDefinition


# Tags to identify candidate subtrees
# ("div", False) - tag name should be exactly 'div'
# ("navigation", True) - tag name should contain 'navigation'
CANDIDATE_SUBTREE_TAGS = [
    TagDefinition("div", partial_match=False),
    TagDefinition("nav", partial_match=False),
    TagDefinition("form"),
    TagDefinition("navigation"),
    TagDefinition("footer"),
    TagDefinition("header"),
    TagDefinition("menu"),
    TagDefinition("top"),
    TagDefinition("bottom"),
    TagDefinition("left"),
    TagDefinition("right"),
]


def construct_query():
    # e.g. nodes of type 'nav' (exact match) or type containing 'navigation'
    # //*[self::nav or contains(local-name(), 'navigation')]
    shared_tags_query = " or ".join(tag.to_xpath() for tag in CANDIDATE_SUBTREE_TAGS)
    return f"//*[{shared_tags_query}]"


def get_candidate_nodes(parsed_content: LxmlTree) -> list[LxmlNode]:
    """
    Get all nodes (matching the query) from the input Element.
    These nodes are the candidate nodes that can be boilerplate.
    """
    query = construct_query()
    return parsed_content.xpath(query)
