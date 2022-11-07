import argparse
import os
import sys

import cv2
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


class SplitArgs(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, self.split(values))

    def chunks(self, lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i : i + n]

    def split(self, s):
        s = list(map(float, s[0].split()))
        coords = list(self.chunks(s, 2))
        if len(coords[-1]) != 2:
            print("Invalid coordinates")
            sys.exit()
        return coords


def get_euclidean(a, b):
    """Calculate Euclidean Distance between two points a and b
    Args:
        a (float): center
        b (float): edge
    Returns:
        float: radius
    """
    a = np.array(a)
    b = np.array(b)

    return np.linalg.norm(a - b)


def get_radii(point_pairs):
    """Calculate radius using (center, edge) pair
    Args:
        point_pairs (list): list of lists where each element is a [center, edge] pair
    Returns:
        list: list of radii (size if equal to len(point_pairs))
    """
    return [get_euclidean(pair[0], pair[1]) for pair in point_pairs]


def get_pairs(point_list):
    """Converts list of point clicks to pairs of points
    A pair represents (center, edge)
    Args:
        point_list (list): list of ordered click on the template
    Returns:
        list: list of lists where each sublist represents a (center, edge) pair
    """
    n = 2
    return [point_list[i : i + n] for i in range(0, len(point_list) - n + 1, n)]


def calculate_centers_and_radii(mouse_clicks):
    """Calculate centers and radius of the balls on the template
    Args:
        mouse_clicks (list): ordered list of mouse clicks
    Returns:
        tuple: (centers, radius)
    """
    centers = mouse_clicks[::2]
    point_set = get_pairs(mouse_clicks)
    radii = get_radii(point_set)

    centers = np.array(centers)
    radii = np.array(radii)

    for idx, (center, radius) in enumerate(zip(centers, radii)):
        print(f"Center {idx}: {(center[0], center[1])}, Radius: {radius:.2f}")

    return centers, radii


def prospective_calibration(args):
    """This function performs the calibration/registration and close the GUI automatically"""
    true_w, true_h = args.e1, args.e2

    # extract centers and radius
    centers, radii = calculate_centers_and_radii(args.pos_tuple)

    # Open image
    img = Image.open(args.in_img)

    # get width and height of image
    width, height = img.width, img.height
    print(f"Image Width: {width}, Height: {height}")

    sift_res = 1024
    screen_res = 512

    scale_down_factor_sift = sift_res / np.min(np.array([width, height]))
    scale_down_factor_screen = screen_res / np.min(np.array([width, height]))

    # resize image to fit on screen
    new_im_width = int(width * scale_down_factor_sift)
    new_im_height = int(height * scale_down_factor_sift)

    img_sift = img.resize((new_im_width, new_im_height), Image.ANTIALIAS)

    # resize image to fit on screen
    new_im_width = int(width * scale_down_factor_screen)
    new_im_height = int(height * scale_down_factor_screen)
    img = img.resize((new_im_width, new_im_height), Image.ANTIALIAS)

    centers = centers * scale_down_factor_sift
    radii = (
        radii * scale_down_factor_sift * 0.9
    )  # we don't want to detect keypoints on the circle
    sift = cv2.SIFT_create()
    template = np.array(img_sift.convert("LA"))[:, :, 0]
    kp_template, des_template = sift.detectAndCompute(template, None)

    # Keep only keypoints within radius
    kp_tmp = []
    des_tmp = np.zeros(shape=(0, des_template.shape[1]), dtype="float32")
    for c in range(4):
        for i in range(len(kp_template)):
            dist = np.sqrt(np.sum((kp_template[i].pt - centers[c, :]) ** 2))
            if dist < (radii[c]):
                # kp_tmp.append(kp_template[i])

                temp = (
                    kp_template[i].pt,
                    kp_template[i].size,
                    kp_template[i].angle,
                    kp_template[i].response,
                    kp_template[i].octave,
                    kp_template[i].class_id,
                )
                kp_tmp.append(temp)

                des_tmp = np.vstack((des_tmp, des_template[i, :]))

    kp_template = kp_tmp
    des_template = des_tmp

    model_file = os.path.join(args.out_dir, "calibration_file")

    np.savez(
        model_file,
        img_template=template,
        kp_template=kp_template,
        des_template=des_template,
        true_w=true_w,
        true_h=true_h,
        centers=centers,
    )

    if False:  # TODO:  if DEBUG or something like that?
        # A bit silly, but we need to reassemble the key points (which we split for saving to disk)
        kp = []
        for point in kp_template:
            temp = cv2.KeyPoint(
                x=point[0][0],
                y=point[0][1],
                size=point[1],
                angle=point[2],
                response=point[3],
                octave=point[4],
                class_id=point[5],
            )
            kp.append(temp)

        kp_im_template = template.copy()
        kp_im_template = cv2.drawKeypoints(
            template,
            kp,
            kp_im_template,
            flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS,
        )

        plt.figure()
        plt.imshow(kp_im_template, aspect="equal")
        plt.title("Key points in template image"),
        plt.savefig(os.path.join(args.out_dir, "keypoints.png"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--in_img", type=str, dest="in_img", default=None)
    parser.add_argument(
        "--points", nargs="+", dest="pos_tuple", action=SplitArgs
    )
    parser.add_argument(
        "--width", nargs="?", type=float, dest="e1", default=None
    )
    parser.add_argument(
        "--height", nargs="?", type=float, dest="e2", default=None
    )
    parser.add_argument("--out_dir", type=str, dest="out_dir", default=None)

    # If running the code in debug mode
    gettrace = getattr(sys, "gettrace", None)

    if gettrace():
        sys.argv = [
            "func_prospective_calibration.py",
            "--in_img",
            "/space/calico/1/users/Harsha/photo-calibration-gui/misc/cal_input/prospective_without_tissue.jpg",
            "--points",
            "22 17 40 9 478 25 492 9 18 465 30 451 462 472 478 460",
            "--width",
            "272",
            "--height",
            "272",
            "--out_dir",
            "/space/calico/1/users/Harsha/photo-calibration-gui/misc/cal_output",
        ]

    args = parser.parse_args()

    prospective_calibration(args)

    # example call:
    # fspython func_prospective_calibration.py \
    #   --in_img /space/calico/1/users/Harsha/photo-calibration-gui/misc/photos/2604.01.JPG \
    #   --points 22 17 40 9 478 25 492 9 18 465 30 451 462 472 478 460 \
    #   --width 272 --height 272 \
    #   --out_dir /space/calico/1/users/Harsha/photo-calibration-gui/misc/deformed/
