#!/usr/bin/env python
from dataclasses import dataclass
from typing import Dict
from typing import Optional
import argparse
import datetime
import numpy
import os
import re
import shutil
import subprocess
import sys

from PIL import Image
from moviepy.video.io.VideoFileClip import VideoFileClip
import imagehash


YT_FORMAT = 160  # mp4 256x144 30fps (see: yt-dlp --list-formats)
SEEK_SECS = 0.25
SKIP_SECS = 10.0
ROUND_START_MAX_OFFSET_SECS = 20.0

DATA_DIRPATH = os.path.join(
    os.path.dirname(__file__),
    "data",
)


@dataclass
class PotentialMatch:
    vs_sec: int
    vs_clip_frame_img: Image
    left_char_key: str
    right_char_key: str
    left_hash_diff: int
    right_hash_diff: int
    round_start_sec: Optional[int] = None
    clause_hash_diff: Optional[int] = None


def load_image(filename: str) -> Image:
    return Image.open(f"{DATA_DIRPATH}/images/{filename}").convert("RGB")


def load_char_hashes(dirname: str, suffix: str) -> Dict[str, imagehash.ImageHash]:
    filename_suffix = f"{suffix}.png"
    box = CHAR_LEFT_IMAGE_BOX if suffix == "-left" else CHAR_RIGHT_IMAGE_BOX
    char_hashes = {}
    for filename in os.listdir(f"{DATA_DIRPATH}/{dirname}"):
        if filename.endswith(filename_suffix):
            char_key = os.path.splitext(filename)[0]
            img = Image.open(f"{DATA_DIRPATH}/{dirname}/{filename}").convert("RGB")
            char_hashes[char_key] = imagehash.dhash(img.crop(box))
    return char_hashes


VS_IMAGE_BOX = [97, 26, 97+20, 26+93]
VS_IMAGE = load_image("vs.png")
VS_IMAGE_HASH = imagehash.dhash(VS_IMAGE.crop(VS_IMAGE_BOX))
VS_IMAGE_HASH_THRESHOLD = 10

CLAUSE_IMAGE_BOX = [80, 16, 80+54, 16+113]
CLAUSE_IMAGE = load_image("clause.png")
CLAUSE_IMAGE_HASH = imagehash.dhash(CLAUSE_IMAGE.crop(CLAUSE_IMAGE_BOX))
CLAUSE_IMAGE_HASH_THRESHOLD = 20

CHAR_LEFT_IMAGE_BOX = [19, 16, 19+61, 16+84]
CHAR_RIGHT_IMAGE_BOX = [134, 16, 134+61, 16+84]
CHAR_LEFT_HASHES = load_char_hashes("chars", "-left")
CHAR_RIGHT_HASHES = load_char_hashes("chars", "-right")
CHAR_IMAGE_HASH_THRESHOLD = 10


def clip_frame_to_image(clip_frame: numpy.ndarray) -> Image:
    return Image.fromarray(clip_frame.astype("uint8"), "RGB")


def format_timestamp(sec: float) -> str:
    return f"[{datetime.timedelta(seconds=int(sec))}]"


def format_title(match: PotentialMatch) -> str:
    char_name = lambda s: s.split("-")[0].capitalize()
    sec = int(match.round_start_sec or match.vs_sec)
    return f"{format_timestamp(sec)} {char_name(match.left_char_key)} vs {char_name(match.right_char_key)}"


def remove_video_file(vid_filepath: str) -> None:
    try:
        os.remove(vid_filepath)
    except Exception:
        pass


def run_potential_match_debug(debug_dir: str, potential_match: PotentialMatch) -> None:
    sec = potential_match.vs_sec
    clip_frame_img = potential_match.vs_clip_frame_img
    left_char_key = potential_match.left_char_key
    right_char_key = potential_match.right_char_key

    print(format_timestamp(sec))
    print(f"\t({potential_match.left_hash_diff}, {left_char_key})")
    print(f"\t({potential_match.right_hash_diff}, {right_char_key})")

    clip_frame_img.save(
        f"{debug_dir}/{format_timestamp(sec)}.{left_char_key}.{right_char_key}.png".replace(":", "."),
    )

    left_img = Image.new("RGBA", (256, 144), color=None)
    left_img.paste(
        clip_frame_img.crop(CHAR_LEFT_IMAGE_BOX),
        box=CHAR_LEFT_IMAGE_BOX,
    )
    left_img.save(
        f"{debug_dir}/chars/{format_timestamp(sec)}-left.png".replace(":", "."),
    )

    right_img = Image.new("RGBA", (256, 144), color=None)
    right_img.paste(
        clip_frame_img.crop(CHAR_RIGHT_IMAGE_BOX),
        box=CHAR_RIGHT_IMAGE_BOX,
    )
    right_img.save(
        f"{debug_dir}/chars/{format_timestamp(sec)}-right.png".replace(":", "."),
    )


def run_round_start_debug(debug_dir: str, clip_frame_img: Image, potential_match: PotentialMatch) -> None:
    sec = potential_match.round_start_sec
    vs_sec = potential_match.vs_sec

    print(f"\tclause_hash_diff={potential_match.clause_hash_diff}")

    clip_frame_img.save(
        f"{debug_dir}/{format_timestamp(vs_sec)}.png".replace(":", "."),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse uni2 youtube video for matches")
    parser.add_argument(
        "youtube_url",
        type=str,
        help="youtube video URL",
    )
    parser.add_argument(
        "-l",
        "--local-video",
        type=str,
        help="use already downloaded local youtube video filepath instead of redownloading",
    )
    parser.add_argument(
        "-o",
        "--output-filepath",
        type=str,
        default="matches.html",
        help="filepath to output parsed matches html file"
    )
    parser.add_argument(
        "--delete-video",
        action="store_true",
        help="delete downloaded youtube video file after parsing",
    )
    parser.add_argument(
        "--debug-dir",
        type=str,
        help="debug output directory (the dir will be wiped!)",
    )
    args = parser.parse_args()

    if args.debug_dir:
        shutil.rmtree(args.debug_dir, ignore_errors=True)
        os.mkdir(args.debug_dir)
        os.mkdir(f"{args.debug_dir}/chars")


    # Download youtube video
    ########################
    if args.local_video:
        video_filepath = args.local_video
    else:
        try:
            yt_dlp_output = subprocess.check_output(
                f"yt-dlp \"{args.youtube_url}\" --format {YT_FORMAT} --no-continue",
                shell=True,
            ).decode("utf-8")

            m = re.search(r"Destination: (?P<filename>.+$)", yt_dlp_output, re.MULTILINE)
            if m:
                video_filepath = [f for f in os.listdir('.') if f.endswith(m.group("filename"))][0]
            else:
                print(f"error parsing yt-dlp destination: {yt_dlp_output}")
                sys.exit(1)
        except Exception as e:
            print(f"yt-dlp error: {e}")
            sys.exit(1)

    clip = VideoFileClip(video_filepath, audio=False)


    # Find match start timestamps
    #############################
    next_sec = 0
    last_vs_sec = 0
    vs_clip_frame_imgs = []
    potential_matches = []

    for sec, clip_frame in clip.iter_frames(with_times=True):
        if sec < next_sec:
            continue

        clip_frame_img = clip_frame_to_image(clip_frame)
        vs_img_hash_diff = imagehash.dhash(clip_frame_img.crop(VS_IMAGE_BOX)) - VS_IMAGE_HASH

        # Detect 1st clause image
        if sec - last_vs_sec < ROUND_START_MAX_OFFSET_SECS and potential_matches:
            clause_img_hash_diff = imagehash.dhash(clip_frame_img.crop(CLAUSE_IMAGE_BOX)) - CLAUSE_IMAGE_HASH
            if clause_img_hash_diff < CLAUSE_IMAGE_HASH_THRESHOLD:
                potential_matches[-1].round_start_sec = sec
                potential_matches[-1].clause_hash_diff = clause_img_hash_diff

                if args.debug_dir:
                    run_round_start_debug(args.debug_dir, clip_frame_img, potential_matches[-1])

                next_sec = max(last_vs_sec + ROUND_START_MAX_OFFSET_SECS, sec + SKIP_SECS)
            else:
                next_sec = sec + SEEK_SECS

        # Detect VS image
        elif vs_img_hash_diff < VS_IMAGE_HASH_THRESHOLD:
            vs_clip_frame_imgs.append(clip_frame_img)
            next_sec = sec + SEEK_SECS

        # Potential match
        elif vs_clip_frame_imgs:
            vs_clip_frame_img = vs_clip_frame_imgs[len(vs_clip_frame_imgs) // 2]

            left_img = vs_clip_frame_img.crop(CHAR_LEFT_IMAGE_BOX)
            left_hash_diffs = sorted([
                (imagehash.dhash(left_img) - char_hash, char_key)
                for char_key, char_hash in CHAR_LEFT_HASHES.items()
            ])

            right_img = vs_clip_frame_img.crop(CHAR_RIGHT_IMAGE_BOX)
            right_hash_diffs = sorted([
                (imagehash.dhash(right_img) - char_hash, char_key)
                for char_key, char_hash in CHAR_RIGHT_HASHES.items()
            ])

            potential_matches.append(
                PotentialMatch(
                    vs_sec=sec,
                    vs_clip_frame_img=vs_clip_frame_img,
                    left_char_key=left_hash_diffs[0][1],
                    right_char_key=right_hash_diffs[0][1],
                    left_hash_diff=left_hash_diffs[0][0],
                    right_hash_diff=right_hash_diffs[0][0],
                )
            )

            last_vs_sec = sec
            vs_clip_frame_imgs = []

            if args.debug_dir:
                run_potential_match_debug(args.debug_dir, potential_matches[-1])

            next_sec = sec + SEEK_SECS

        else:
            next_sec = sec + SEEK_SECS

    clip.reader.close()


    # Write matches file
    ####################
    norm_url = re.sub(r"\?t=\d+", "?", args.youtube_url)
    norm_url = re.sub(r"&t=\d+", "", norm_url)
    norm_url = re.sub(r"#t=\d+", "", norm_url)

    with open(args.output_filepath, "w") as f:
        f.write("<ol reversed>\n")
        for match in potential_matches[::-1]:
            match_sec = int(match.round_start_sec or match.vs_sec)
            f.write(f"<li><a href={norm_url}#t={match_sec}>{format_title(match)}</a></li>\n")
        f.write("</ol><br>")

    if args.delete_video and not args.local_video:
        remove_video_file(video_filepath)
