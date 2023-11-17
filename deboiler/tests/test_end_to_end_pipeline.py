from deboiler import Deboiler
from deboiler.dataset import JsonDataset
from deboiler.tests.fixtures import get_fixture_path


def test_pipeline_end_to_end():
    domain = "globality"
    json_path = get_fixture_path() / f"{domain}.com.jsonl"

    deboilers, output_pages = [], []
    for operation_mode, n_processors in [
        ("memory", 1),
        ("memory", 2),
        ("performance", 1),
    ]:
        dataset = JsonDataset(json_path, status_key=None, content_type_key=None)
        deboilers.append(Deboiler(n_processes=n_processors, operation_mode=operation_mode))

        deboilers[-1].fit(dataset, chunksize=5)
        output_pages.append(list(deboilers[-1].transform(dataset, chunksize=5)))

    assert (
        deboilers[0].boilerplate_elements
        == deboilers[1].boilerplate_elements
        == deboilers[2].boilerplate_elements
    )
    assert output_pages[0] == output_pages[1] == output_pages[2]
