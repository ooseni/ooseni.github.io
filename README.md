# ooseni.github.io

Portfolio of Oseni Sakariyau Oluwadamilare, Cloud DevOps Engineer in Lagos, Nigeria. Live at **https://ooseni.github.io**.

A single static page in plain HTML and CSS, published by GitHub Pages from the default branch. There is no build step and nothing is loaded from third parties: no web fonts, scripts or trackers. The page follows the visitor's light or dark system theme.

| File | Contents |
|---|---|
| `index.html` | The page: featured project, DevOps work, other projects, journey, toolbox, contact |
| `style.css` | Layout, and colour tokens for light and dark mode |
| `favicon.svg` | Site icon |
| `assets/` | The CertWatch architecture diagram (light SVG, dark PNG), copied from [ooseni/certwatch](https://github.com/ooseni/certwatch) |
| `scripts/update_certwatch_card.py` | Regenerates the CertWatch card's status line and its Built, Next and Decisions bullets from [ooseni/certwatch](https://github.com/ooseni/certwatch) |
| `.github/workflows/update-certwatch-card.yml` | Runs that script every day and on demand, and commits only when the card changes |

To preview locally, open `index.html` in a browser, or run `python -m http.server` and visit http://localhost:8000.

## The CertWatch card updates itself

The featured CertWatch card follows the project through its phases. `scripts/update_certwatch_card.py` reads CertWatch's roadmap (the ✅ and ⬜ phases in its README) and the status of each architecture decision record in `docs/decisions`. It then rewrites only the parts of `index.html` between `<!-- certwatch:... -->` markers: the status line and the Built, Next and Decisions bullets. The other bullets stay hand-written.

The **Update the CertWatch card** workflow runs it every day at 06:17 UTC and can be started by hand. It commits only when the card has changed, then asks GitHub Pages to publish. To run it yourself:

```bash
python scripts/update_certwatch_card.py            # show what would change
python scripts/update_certwatch_card.py --write    # update index.html
gh workflow run update-certwatch-card.yml          # run the workflow now
```

## License

Released under the [MIT License](LICENSE).
