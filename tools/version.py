"""Print the installed Rangekeeper version; --dotnet prints its SemVer 2 form.

setuptools-scm derives the version from git tags when the package is built or
installed. The C# example takes the same version through MSBuild:

    dotnet build -p:Version=$(python tools/version.py --dotnet)
"""

import argparse
from importlib.metadata import version

from packaging.version import Version


def dotnet(value: Version) -> str:
    """Return a SemVer 2 version that NuGet and MSBuild accept."""
    text = value.base_version
    labels = []
    if value.pre is not None:
        letter, number = value.pre
        labels += [{"a": "alpha", "b": "beta", "rc": "rc"}[letter], str(number)]
    if value.dev is not None:
        labels += ["dev", str(value.dev)]
    if labels:
        text += "-" + ".".join(labels)
    if value.local is not None:
        text += "+" + value.local
    return text


def main() -> None:
    """Print the version in the requested form."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dotnet", action="store_true")
    args = parser.parse_args()
    current = Version(version("rangekeeper"))
    print(dotnet(current) if args.dotnet else current)


if __name__ == "__main__":
    main()
