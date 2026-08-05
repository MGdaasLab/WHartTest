# THIRD-PARTY SOFTWARE NOTICES

This product includes third-party software components.
The original licenses and notices of these components must be preserved
when redistributing this product (source or binary).

## Components used in this service

| Component | Used by | License | Notes for redistribution |
| --- | --- | --- | --- |
| Playwright (Python) | UI automation engine and script execution | Apache-2.0 | Keep license text and attribution in distributed artifacts. |
| Pillow | Document image parsing (`PIL.Image`) | MIT-CMU | Keep license text and attribution in distributed artifacts. |
| Chromium headless shell (downloaded by Playwright) | Headless browser runtime | Mixed Chromium third-party licenses | Keep bundled Chromium license files and notices in distributed artifacts. |
| FFmpeg binary (downloaded by Playwright) | Browser media codec/runtime support | LGPL-2.1+ (default Playwright package) | Keep LGPL text and related notices in distributed artifacts. If rebuilt with GPL options, obligations change. |
| NLTK | Knowledge base text processing (`knowledge.services`) | Apache-2.0 | Keep license text and attribution in distributed artifacts. |

## Source links

- Playwright: https://github.com/microsoft/playwright-python
- Pillow: https://github.com/python-pillow/Pillow
- Chromium project: https://chromium.googlesource.com/chromium/src
- FFmpeg legal and checklist: https://ffmpeg.org/legal.html
- NLTK: https://github.com/nltk/nltk

## Compliance packaging in this repository

The Docker image build collects license/notice files into:

- `/app/third_party_licenses/THIRD_PARTY_NOTICES.md`
- `/app/third_party_licenses/python/*`
- `/app/third_party_licenses/playwright-browsers/*`

If you distribute Docker images or packaged binaries externally, verify
these files are present in the final artifact before release.
