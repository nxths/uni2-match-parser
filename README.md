# Overview
This script is for parsing out matches from youtube videos for Under Night In-Birth II, generating an html file containing match start times with character names. The [windowed](https://github.com/nxths/uni2-match-parser/tree/windowed) branch is used as part of [insubstantial.org/uni2-seth](https://insubstantial.org/uni2-seth/).

* ``uni2-parser.py``: download and parse youtube videos, run with ``--help`` for more details.

The source should be cross platform but has only been tested on linux and windows.

# Dependencies
* [python 3.x](https://www.python.org/)
* [moviepy](https://zulko.github.io/moviepy/)
  * [ffmpeg](https://www.ffmpeg.org/)
* [pillow](https://pillow.readthedocs.io/)
* [imagehash](https://github.com/JohannesBuchner/imagehash)
* [yt-dlp](https://github.com/yt-dlp/yt-dlp) (needs to be in PATH)

# Limitations
The script only works for fullscreen gameplay footage.
