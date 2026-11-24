"""资源读不出来时，选项读取应显示配置错误而不是空列表。"""

import pytest
from auto_mas_core.host.utils import io

from zzzod_adapter.tools.compendium import coffee_options, train_categories


@pytest.mark.parametrize("content", [None, "null", "[broken"])
@pytest.mark.parametrize(
    ("name", "read_options"),
    [
        ("compendium_data.yml", train_categories),
        ("coffee_data.yml", lambda root: coffee_options(root, day=1)),
    ],
)
def test_invalid_required_option_resources(tmp_path, content, name, read_options):
    directory = tmp_path / "assets" / "game_data"
    directory.mkdir(parents=True)
    resource = directory / name
    if content is not None:
        resource.write_text(content, encoding="utf-8")
    with pytest.raises(io.ConfigCorruptedError) as error:
        read_options(tmp_path)
    assert error.value.path == resource
