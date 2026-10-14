"""Keep local sync conflict files out of source and wheel distributions."""
from setuptools import setup
from setuptools.command.build_py import build_py

class SourceBuild(build_py):
    def find_package_modules(self, package, package_dir):
        return [item for item in super().find_package_modules(package, package_dir)
                if ".sync-conflict-" not in item[2]]

setup(cmdclass={"build_py": SourceBuild})
