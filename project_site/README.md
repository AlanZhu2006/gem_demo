# GEM project page

A standalone static research page for **A Streaming Geometry Model Is an Episodic Memory: Monocular Multi-Goal Navigation Without a Pose Oracle**.

Prepared for `AlanZhu2006/gem`, with the intended address `https://alanzhu2006.github.io/gem/`. This is a local preview; no repository or public deployment has been created by this task.

## Preview

From this directory:

```sh
python -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/`. Use a web server rather than opening `index.html` as a file so the optional metadata JSON can load.

## Content and behavior

- Exact paper title, short research description, paper download, and full-video link.
- 11-second muted point-cloud teaser, exported without the film's title overlay. Loads and plays when visible, pauses offscreen, and respects reduced-motion preferences.
- Indoor / outdoor / simulation tabs with one large video player. Demonstrations and the full film load only when requested. Their original playback-speed labels remain visible.
- Full paper architecture and a/b/c detail views, with keyboard navigation and an enlarged figure dialog.
- HM3D / MP3D Table I counts and confidence intervals, continuous-navigation and real-world summaries, and the separate controlled-history comparison.
- Captioned full video, SRT download, and a static transcript.
- Responsive layouts, visible keyboard focus, native controls, no tracking, no external fonts, and no framework/build dependency.

## Publication metadata

Edit `site.config.json` to populate real authors/affiliations, arXiv, code, and BibTeX. Empty values stay hidden, so there are no fake links or invented author names. A populated author entry has the shape:

```json
{"name": "Full name", "url": "https://author-homepage.example/", "affiliation": "1"}
```

The included `assets/paper.pdf` is the current **anonymous** `Nav-graph-blind/projects/paper/main.pdf`. Replace it with the author-approved arXiv manuscript when author metadata is finalized. The GitHub username is used for hosting, not inferred as a paper author. No conference acceptance is claimed.

The canonical/Open Graph URLs in `index.html` are set to the intended address; update them and `project_url` if the repository name or domain changes.

## GitHub Pages

This folder can be the root of an independent `gem` repository. In the repository's **Settings → Pages**, choose **Deploy from a branch**, branch **main**, folder **/(root)**. `.nojekyll` keeps the site a plain static export. Relative asset links support project subpaths. No private experiment files or original reconstruction data are required by the site.

Source: [GitHub Pages publishing-source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

## Reproduce assets

From the parent `gem_demo` workspace:

```sh
python tools/build_project_site_assets.py
```

Requires Pillow and ffmpeg, plus the local manuscript and verified v24 video assets. It copies the exact PDF and 178-second film, encodes lighter silent demonstration clips, extracts original figure panels, and reuses the selected point-cloud/trajectory tiles for the teaser. `asset-provenance.json` records source hashes. The original videos are not modified.

## Design references

- [LoGoPlanner](https://steinate.github.io/logoplanner.github.io/): centered research identity, direct resource links, demonstrations grouped by capability.
- [Nerfies](https://nerfies.github.io/): visual evidence near the top and a clear connection between the visual and its explanation.
- [VoxPoser](https://voxposer.github.io/): separate full video and inspectable demonstrations/method visualizations.

The HTML/CSS/JavaScript is newly written for GEM. No reference-page code, logos, illustrations, or video are redistributed. The page uses GEM's paper art and recorded demonstrations.
