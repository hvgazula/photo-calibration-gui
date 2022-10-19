import numpy as np
import cv2
from argparse import ArgumentParser, ArgumentTypeError
import re
import sys

# additional type
def coords(s):
    seps = r"[;.]"
    try:
        situp = []
        for si in re.split(seps, s):
            situp.append(tuple(map(float, si.split(","))))
        return situp
    except:
        raise ArgumentTypeError(
            "Coordinates must be given divided by commas and space, dot, or semicolon e.g.: 'x,y k,l,'"
        )


def perform_registration(args):
    """This function performs the registration and close the GUI automatically"""

    # screen_width, screen_height = args.screen_width, args.screen_height
    args.scale_down_factor_screen = None

    if len(args.pos_tuple) == 4:
        true_width = args.e1
        true_height = args.e2
    elif len(args.pos_tuple) == 2:
        # We pretend the user clicked on the 4 corners of the image
        # and make the true_width and true_height proportional to the provided length
        pix_dist = (
            np.sqrt(
                (args.pos_tuple[0][0] - args.pos_tuple[1][0]) ** 2
                + (args.pos_tuple[0][1] - args.pos_tuple[1][1]) ** 2
            )
            / args.scale_down_factor_screen
        )
        pix_siz = float(args.e1) / pix_dist
        true_width = pix_siz * args.img_fullres[0]
        true_height = pix_siz * args.img_fullres[1]
        args.pos_tuple = [
            [0, 0],
            [0, args.img_fullres[1] * args.scale_down_factor_screen - 1],
            [args.img_fullres[0] * args.scale_down_factor_screen - 1, 0],
            [
                args.img_fullres[0] * args.scale_down_factor_screen - 1,
                args.img_fullres[1] * args.scale_down_factor_screen - 1,
            ],
        ]
    else:
        raise ValueError("Wrong number of clicks")

    reference_pixel_size = 0.1

    centers_target = np.array(args.pos_tuple) / args.scale_down_factor_screen
    centers_target = centers_target[:, np.newaxis, :]

    # Now we only have to compute the final transform. The only caveat is the ordering of the corners...
    # We reorder then to NW, NE, SW, SE
    centers_target_reordered = np.zeros_like(centers_target)

    cost = centers_target[:, 0, 0] + centers_target[:, 0, 1]
    idx = np.argmin(cost)
    centers_target_reordered[0, 0, :] = centers_target[idx, 0, :]
    centers_target[idx, 0, :] = 0

    cost = -centers_target[:, 0, 0] + centers_target[:, 0, 1]
    cost[cost == 0] = 1e10
    idx = np.argmin(cost)
    centers_target_reordered[1, 0, :] = centers_target[idx, 0, :]
    centers_target[idx, 0, :] = 0

    cost = centers_target[:, 0, 0] - centers_target[:, 0, 1]
    cost[cost == 0] = 1e10
    idx = np.argmin(cost)
    centers_target_reordered[2, 0, :] = centers_target[idx, 0, :]
    centers_target[idx, 0, :] = 0

    cost = -centers_target[:, 0, 0] - centers_target[:, 0, 1]
    cost[cost == 0] = 1e10
    idx = np.argmin(cost)
    centers_target_reordered[3, 0, :] = centers_target[idx, 0, :]
    centers_target[idx, 0, :] = 0

    # We now define the target coordinates using the reerence resolution
    ref_coords = np.zeros_like(centers_target)

    ref_coords[0, 0, 0] = 0
    ref_coords[0, 0, 1] = 0

    ref_coords[1, 0, 0] = np.round(true_width / reference_pixel_size) - 1
    ref_coords[1, 0, 1] = 0

    ref_coords[2, 0, 0] = 0
    ref_coords[2, 0, 1] = np.round(true_height / reference_pixel_size) - 1

    ref_coords[3, 0, 0] = np.round(true_width / reference_pixel_size) - 1
    ref_coords[3, 0, 1] = np.round(true_height / reference_pixel_size) - 1

    # We compute the final perspective transform
    M2, _ = cv2.findHomography(centers_target_reordered, ref_coords)
    args.deformed_image = cv2.warpPerspective(
        np.asarray(args.img_fullres),
        M2,
        (
            ref_coords[1, 0, 0].astype(int) + 1,
            ref_coords[2, 0, 1].astype(int) + 1,
        ),
    )

    image_with_ruler = np.zeros(
        (
            args.deformed_image.shape[0] + args.horizontal_ruler.shape[0],
            args.deformed_image.shape[1] + args.vertical_ruler.shape[1],
            3,
        ),
        dtype="uint8",
    )

    image_with_ruler[
        0 : args.deformed_image.shape[0], 0 : args.deformed_image.shape[1], :
    ] = cv2.cvtColor(args.deformed_image, cv2.COLOR_RGB2BGR)
    image_with_ruler[
        args.deformed_image.shape[0] :, 0 : -args.vertical_ruler.shape[1], :
    ] = args.horizontal_ruler[:, 0 : args.deformed_image.shape[1], :]
    image_with_ruler[
        0 : args.deformed_image.shape[0], -args.vertical_ruler.shape[1] :, :
    ] = args.vertical_ruler[0 : args.deformed_image.shape[0], :, :]

    cv2.imwrite(args.output_image, image_with_ruler)


if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument(
        "--points", help="Coordinate", dest="pos_tuple", type=coords, nargs="?"
    )
    parser.add_argument(
        "--width", nargs="?", type=float, dest="e1", default=None
    )
    parser.add_argument(
        "--height", nargs="?", type=float, dest="e2", default=None
    )
    parser.add_argument(
        "--img_fullres", type=coords, dest="img_fullres", default=None
    )
    parser.add_argument(
        "--img_displayres", type=coords, dest="img_displayres", default=None
    )

    # If running the code in debug mode
    gettrace = getattr(sys, "gettrace", None)

    if gettrace():
        sys.argv = [
            "func_registration.py",
            "--points",
            "1, 2; 3, 4; 5, 6; 7, 8",
            "--width",
            "10",
            "--height",
            "15",
            "--img_fullres",
            "100,100",
        ]

    args = parser.parse_args()

    perform_registration(args)

    # example call:
    # fsython func_registration.py --points 1, 2; 3, 4; 5, 6; 7, 8 --width 10 --height 15 --img_fullres 100, 100
