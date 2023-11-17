from dataclasses import dataclass

from deboiler import Deboiler
from deboiler.dataset import JsonDataset
from deboiler.dataset.list_dataset import ListDataset
from deboiler.tests.fixtures import get_fixture_path


@dataclass
class ExamplePage:
    url: str
    should_contain: list[str]


def get_record(json_dataset, url):
    page = json_dataset[url]
    return dict(url=page.url, content=page.content, status=200)


boilerplate_snippets = [
    "* What We Do",
    "* Smart Sourcing",
    "* Become a Supplier",
    "* Resource Library",
]

example_pages = [
    ExamplePage(
        url="https://www.globality.com/innovation-blog/defense-against-the-dark-arts",
        should_contain=[
            "Artificial Intelligence |",
            "Any Harry Potter fan (and there are a lot of them) can tell you that Defense against the "
            "Dark Arts is the core class at Hogwarts School of Witchcraft and Wizardry.",
            "Defense against Cyberattacks",
            "https://www.securitysales.com/research/global-cybersecurity-market-2024/",
        ],
    ),
    ExamplePage(
        url="https://www.globality.com/innovation-blog/how-ai-can-help-brands-find-the-best-agency-talent",
        should_contain=[
            "Artificial Intelligence |",
            "Marketers simply don’t have time to scan the marketplace in search of the best agency at the right "
            "price for every project. Machine learning can help.",
            "How AI Can Help Brands Find the Best Agency Talent",
            "No doubt you’ve already read about how artificial intelligence is poised to change the way we work",
        ],
    ),
]

json_dataset = JsonDataset(
    get_fixture_path() / "globality.com.jsonl", status_key=None, content_type_key=None
)
list_of_records = [get_record(json_dataset, example_page.url) for example_page in example_pages]
dataset = ListDataset(list_of_records, content_type_key=None)


def test_denoising():
    deboiler = Deboiler(n_processes=1)
    deboiler.fit(dataset)

    # Make sure boilerplate elements are found
    assert len(deboiler.boilerplate_elements) > 0

    for example_page, cleaned_page in zip(example_pages, deboiler.transform(dataset)):
        cleaned_text = cleaned_page.cleaned_text

        # Make sure noisy parts of the page are eliminated
        assert not any(
            noisy_text_snippet in cleaned_text for noisy_text_snippet in boilerplate_snippets
        )

        # Make sure the main contents are maintained
        assert all(text_snippet in cleaned_text for text_snippet in example_page.should_contain)
