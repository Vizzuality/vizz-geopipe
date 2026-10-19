"""Turn Python keyword arguments into ``gdal`` command-line flags."""

from collections.abc import Mapping
from collections.abc import Sequence

REPEATED_FLAGS: Mapping[str, str] = {
    "creation_options": "--co",
    "layer_creation_options": "--lco",
    "open_options": "--oo",
    "config": "--config",
}
"""Options given as a mapping, written as one ``--flag KEY=VALUE`` pair per item."""


def to_flags(**options: object) -> list[str]:
    """Return the ``gdal`` flags for ``options``, in the order given.

    ``bbox_crs="EPSG:4326"`` becomes ``--bbox-crs EPSG:4326``, ``True`` a bare flag, a
    sequence a comma-joined value, and a mapping in ``REPEATED_FLAGS`` one flag per item.
    ``None`` and ``False`` are left out, so optional arguments can be passed through as is.

    Raises:
        TypeError: If a mapping is given for an option not listed in ``REPEATED_FLAGS``.
    """
    flags: list[str] = []
    for key, value in options.items():
        if value is None or value is False:
            continue
        if isinstance(value, Mapping):
            if key not in REPEATED_FLAGS:
                raise TypeError(f"{key} does not take a mapping")
            for item_key, item_value in value.items():
                flags += [REPEATED_FLAGS[key], f"{item_key}={item_value}"]
            continue
        flag = "--" + key.replace("_", "-")
        if value is True:
            flags.append(flag)
        elif isinstance(value, Sequence) and not isinstance(value, str):
            flags += [flag, ",".join(str(item) for item in value)]
        else:
            flags += [flag, str(value)]
    return flags
