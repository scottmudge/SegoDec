import cv2 as cv
import sys
import os

import numpy
import numpy as np


RootPath = os.path.dirname(os.path.realpath(__file__))
Quiet = True

"""
Segment Mask - Segments are index like so:

    ####          0 0
   #    #       5     1
   #    #       5     1
    ####   ==>    6 6
   #    #       4     2
   #    #       4     2
    ####          3 3

    The segment mask indicates which segments are active
    during each displayed number.
"""
SegmentMask = (
    (1, 1, 1, 1, 1, 1, 0),  # 0
    (0, 1, 1, 0, 0, 0, 0),  # 1
    (1, 1, 0, 1, 1, 0, 1),  # 2
    (1, 1, 1, 1, 0, 0, 1),  # 3
    (0, 1, 1, 0, 0, 1, 1),  # 4
    (1, 0, 1, 1, 0, 1, 1),  # 5
    (1, 0, 1, 1, 1, 1, 1),  # 6
    (1, 1, 1, 0, 0, 1, 0),  # 7
    (1, 1, 1, 1, 1, 1, 1),  # 8
    (1, 1, 1, 1, 0, 1, 1)   # 9
)

NumSegments = 7

# Globals
# -------------------------------------------------------------------------------
NumChars = 6

CropX = 113
CropY = 169
CropW = 595
CropH = 163

ThresholdPct = 0.5

# Default is black characters on white background
Invert = False

CharStartX = 4
CharStartY = 15
CharHeight = 143
CharWidth = 83


# List of values describing space after each character.
CharSpacing = (
    12, 12, 45, 12, 12
    )

# A set of points (tuple of (x,y) tuples) for each of the 7 segments
SegmentTestPoints = (
    ((29, 20),  (49, 20)),       # 0
    ((68, 30),  (68, 56)),       # 1
    ((68, 93),  (68, 113)),      # 2
    ((29, 130), (49, 130)),      # 3
    ((13, 93),  (13, 113)),      # 4
    ((13, 30),  (13, 56)),       # 5
    ((29, 74),  (49, 74)),       # 6
)

# How many pixels around test point to average., NxN
TestWindowSize: int = 3
# -------------------------------------------------------------------------------


# Utility Functions
def apply_brightness_contrast(input_img, brightness=0, contrast=0):
    if brightness != 0:
        if brightness > 0:
            shadow = brightness
            highlight = 255
        else:
            shadow = 0
            highlight = 255 + brightness
        alpha_b = (highlight - shadow) / 255
        gamma_b = shadow

        buf = cv.addWeighted(input_img, alpha_b, input_img, 0, gamma_b)
    else:
        buf = input_img.copy()

    if contrast != 0:
        f = 131 * (contrast + 127) / (127 * (131 - contrast))
        alpha_c = f
        gamma_c = 127 * (1 - f)

        buf = cv.addWeighted(buf, alpha_c, buf, 0, gamma_c)

    return buf


def print_usage():
    print("Usage: segodec.py [input] [options]")
    print("\tOptions:")
    print("\t: #Todo")


# CORE FUNCTIONS
# -------------------------------------------------------------------------------
def load_image(filename: str) -> np.ndarray:
    """Loads and crops image."""
    if not os.path.exists(filename):
        raise FileNotFoundError("Input file not found.")
    in_img = cv.imread(filename, cv.IMREAD_GRAYSCALE)
    return in_img[CropY:CropY + CropH, CropX:CropX + CropW]


def proc_image(inp: np.ndarray) -> np.ndarray:
    clip = 4.1
    grid = (5, 3)
    #kernel = np.ones((8, 8), np.uint8)
    clahe = cv.createCLAHE(clipLimit=clip, tileGridSize=grid)

    # inp = cv.fastNlMeansDenoising(inp, None, 5, 7, 21)
    # inp = cv2.morphologyEx(inp, cv.MORPH_OPEN, kernel)
    inp = clahe.apply(inp)
    # morph = cv2.morphologyEx(morph, cv.MORPH_CLOSE, kernel)
    return apply_brightness_contrast(clahe.apply(inp), 50, 100)


def determine_segment(img: np.ndarray) -> int:
    if len(img.shape) > 2 and img.shape[2] != 1:
        raise TypeError("Input image is not grayscale.")

    half_window = int(TestWindowSize / 2)
    max_val = np.iinfo(img.dtype).max
    is_seg_active = list()

    for seg in range(NumSegments):
        test_pts = SegmentTestPoints[seg]
        num_pts = len(test_pts)
        pt_vals = list()

        for pt_idx in range(num_pts):
            num_px = 0
            px_val: int = 0
            pt = test_pts[pt_idx]
            for x in range(-half_window, half_window):
                for y in range(-half_window, half_window):
                    px_val += int(img.item(pt[1] + y, pt[0] + x))
                    num_px += 1
            pt_vals.append(int(px_val / num_px))

        seg_mean = sum(pt_vals) / num_pts
        pct = float(seg_mean / max_val)
        active = 0

        if not Invert:
            if pct <= ThresholdPct:
                active = 1
        else:
            if pct >= ThresholdPct:
                active = 1

        is_seg_active.append(active)

    for seg_num, mask in enumerate(SegmentMask):
        if len(is_seg_active) != len(mask):
            raise ValueError("seg_active size != mask size")

        matched = True

        for x, seg_val in enumerate(mask):
            if seg_val != is_seg_active[x]:
                matched = False
                break

        if matched:
            return seg_num
    return -1


def extract_chars(img: numpy.ndarray) -> list:
    """Crops and extracts characters into new list"""
    out = list()
    height, width = img.shape
    if not Quiet:
        print("Input Stats:\n\t> Width: %d\n\t> Height: %d\n\t> Num Chars: %d"%(width, height, NumChars))
    cur_x = CharStartX
    cur_y = CharStartY
    if not Quiet:
        print("Processing image...")
    proc = proc_image(img)

    if len(CharSpacing) < (NumChars -1):
        raise IndexError("Not enough values in CharSpacing")

    for i in range(NumChars):
        crop_wid = CharWidth

        if (cur_x + crop_wid) > width:
            crop_wid = (width - cur_x) - 1

        out.append(proc[cur_y:(cur_y + CharHeight), cur_x:(cur_x + crop_wid)])

        if i < (NumChars - 1):
            cur_x += (CharWidth + CharSpacing[i])

    return out


if __name__ == '__main__':
    if not Quiet:
        print("SegoDec - Seven Segment OCR Decoder")
        print("\t> Written By Scott Mudge")
    out_file = str()

    if len(sys.argv) < 1:
        print_usage()

    img = load_image(sys.argv[1])
    chars = extract_chars(img)
    digits = list()

    for char in chars:
        digits.append(determine_segment(char))

    str_out = str()

    for digit in digits:
        if digit < 0 or digit > 9:
            print("Indeterminate")
            sys.exit(-1)
        str_out += "%d"%digit

    print(str_out)











