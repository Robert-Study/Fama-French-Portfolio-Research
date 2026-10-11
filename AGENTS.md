# Project conventions

- Use small, focused commits and plain commit messages. Comments should explain assumptions or non-obvious choices.
- Preserve `data/legacy` byte for byte. A source hash verifies identity, not financial validity.
- Keep legacy demonstration results separate from return-based FF5 research and from the future holdings-characteristic model.
- Use monthly simple decimal returns in the engine. Deduct fees once, retain ridge factor/residual cross-covariances, and do not add an overlap surcharge to empirical residual covariance.
- Run `python -m pytest` after changing financial calculations, parsing, constraints or exports. Keep synthetic test fixtures out of production data.
- Recheck the upstream branch before committing. Do not overwrite unrelated changes.
- Bump `portfolio.__version__` when model behaviour or the data contract changes so cached runs remain identifiable.
- Keep the app and repository private unless the user asks otherwise. Never commit credentials.
- The hosting target is Streamlit Community Cloud with Python 3.12. The user tests the app; do not require local developer tooling for normal use.
