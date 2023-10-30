# Updating Documentation:

1. Make sure the Github Pages is being built with the `gh-pages` branch, from the `/`(root) directory
2. Make sure `ghp-import` is installed with: `pip install ghp-import` 
3. Build via `poetry run jupyter-book build walkthrough/`
4. Commit any changes to the `main` branch
5. While in the `main` branch, run `ghp-import -n -p -f _build/html` from `../Rangekeeper/walkthrough` directory