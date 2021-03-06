#!/usr/bin/python3
"""
@author: Gregory Kramida
@licence: Apache v2

Copyright 2016 Gregory Kramida

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import sys
import os.path as osp
import argparse as ap
from enum import Enum
from common.args import required_length, string_arr
from yaml import load, dump
from calib.app_synced import ApplicationSynced
from calib.app_unsynced import ApplicationUnsynced
import re

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


class Argument(object):
    def __init__(self, default,
                 nargs=1,
                 arg_type=str,
                 action='store',
                 arg_help="Documentation N/A",
                 console_only=False,
                 required=False,
                 shorthand=None):
        """
        @rtype: Argument
        @type name: str
        @param name: argument name -- to be used in both console and config file
        @type default: object
        @param default: the default value
        @type nargs: int | str
        @param nargs: number of arguments. See python documentation for ArgumentParser.add_argument.
        @type arg_type: type | str
        @param arg_type: type of value to expect during parsing
        @type action: str | function
        @param action: action to perform with the argument value during parsing
        @type arg_help: str
        @param arg_help: documentation for this argument
        @type console_only: bool
        @param console_only: whether the argument is for console use only or for both config file & console
        @type required: bool
        @param required: whether the argument is required
        @type shorthand: str
        @param shorthand: shorthand to use for argument in console
        """
        self.default = default
        self.required = required
        self.console_only = console_only
        self.nargs = nargs
        self.type = arg_type
        self.action = action
        self.help = arg_help
        if shorthand is None:
            self.shorthand = None
        else:
            self.shorthand = "-" + shorthand


# TODO: investigate enum inheritance. There is too much duplicate code between this script file and others, like
# sync_based_on_audio.py and multistereo.py
class Setting(Enum):
    # ================= SETTING FILE STORAGE ==========================================================================#
    settings_file = Argument(None, '?', str, 'store',
                             "File (absolute or relative-to-execution path) where to save and/or " +
                             "load settings for the program in YAML format.",
                             console_only=True, required=False)
    save_settings = Argument(False, '?', 'bool_flag', 'store_true',
                             "Save (or update) setting file.",
                             console_only=True, required=False)
    # ================= WORK FOLDER, INPUT & OUTPUT FILES =============================================================#
    folder = Argument("./", '?', str, 'store',
                      "Path to root folder to work in. If set to '!settings_file_location' and a " +
                      " settings file is provided, will be set to the location of the settings file.",
                      console_only=False, required=False)
    videos = Argument(["left.mp4", "right.mp4"], '+', string_arr, required_length(1, 10),
                      "Input videos. May be multiple videos for unsynced mode, a stereo video tuple (left, right), " +
                      "or a single video file, specified relative to the work folder (see 'folder' argument).",
                      console_only=False, required=False)
    input_calibration = Argument(None, '+', string_arr, required_length(1, 10),
                                 "Existing calibration file[s] to initialize calibration parameters. " +
                                 "Optional for synced mode, mandatory for unsynced mode.",
                                 console_only=False, required=False)
    output = Argument(None, '?', str, 'store',
                      "Output file to store calibration results (relative to work folder, see 'folder' setting)",
                      console_only=False, required=False)

    filtered_image_folder = Argument("frames", '?', str, 'store',
                                     "Filtered frames will be saved into this folder (relative to work folder " +
                                     "specified in 'folder'). Synced mode only.",
                                     console_only=False, required=False, shorthand="if")
    aux_data_file = Argument("aux.npz", '?', str, 'store',
                             "File (relative to 'folder') where to load from and/or save to inner corner positions, " +
                             "calibration time ranges, frame numbers, and other auxiliary data.",
                             console_only=False, required=False, shorthand="df")
    # ============== STORAGE CONTROL FLAGS ============================================================================#
    # calibration intervals:
    save_calibration_intervals = Argument(False, '?', 'bool_flag', 'store_true',
                                          "Save the calculated time bounds of calibration period within the video for" +
                                          " future re-use.",
                                          console_only=False, required=False)
    load_calibration_intervals = Argument(False, '?', 'bool_flag', 'store_true',
                                          "Load the previously-determined time bounds of calibration period within " +
                                          "video (avoids potentially-long computation that seeks out the calibration " +
                                          "in the video)",
                                          console_only=False, required=False)
    # frame data
    save_frame_data = Argument(False, '?', 'bool_flag', 'store_true',
                               "Save (or update) the gathered locations of inner board corners and other frame data.",
                               console_only=False, required=False)
    load_frame_data = Argument(False, '?', 'bool_flag', 'store_true',
                               "Load the previously-gathered locations of inner board corners and other frame data " +
                               "(skips gathering frame data).",
                               console_only=False, required=False)
    # output calibration
    skip_saving_output = Argument(False, '?', 'bool_flag', 'store_true',
                                  "Skip saving the output file. Usually, you don't want to skip that.",
                                  console_only=False, required=False)

    # cherry-picked frame images
    save_images = Argument(False, '?', 'bool_flag', 'store_true',
                           "Save images picked out for calibration. Synced mode only.",
                           console_only=False, required=False)
    save_checkerboard_overlays = Argument(default=False, arg_type='bool_flag', action='store_true',
                                          arg_help="Save checkerboard overlays alongside the actual raw frame " +
                                                   "images picked out. Only works when `save_images` is enabled.")

    load_images = Argument(False, '?', 'bool_flag', 'store_true',
                           "Load images previously picked out for calibration (skips frame gathering). Synced only.",
                           console_only=False, required=False)

    # TODO: enable saving rvec & tvec of camera pose obtained during calibration
    # ============== CALIBRATION PREVIEW ==============================================================================#
    preview = Argument(False, '?', 'bool_flag', 'store_true',
                       "Save (or update) setting file.",
                       console_only=False, required=False)
    preview_files = Argument(["left.png", "right.png"], '+', string_arr, required_length(1, 10),
                             "Test calibration result on left/right frame pair (currently only for stereo in synced " +
                             "mode).", console_only=False, required=False)
    # ============== BOARD DIMENSIONS =================================================================================#
    board_width = Argument(9, '?', int, 'store',
                           "Checkerboard horizontal inner corner count (width in squares - 1).",
                           console_only=False, required=False)
    board_height = Argument(6, '?', int, 'store',
                            "Checkerboard vertical inner corner count (height in squares - 1).",
                            console_only=False, required=False)
    board_square_size = Argument(0.0198888, '?', float, 'store',
                                 "Checkerboard square size, in meters.",
                                 console_only=False, required=False)
    # ============== FRAME FILTERING CONTROLS ======================================================#
    sharpness_threshold = Argument(55.0, '?', float, 'store',
                                   "Sharpness threshold based on variance of " +
                                   "Laplacian; used to filter out frames that are too blurry. Synced mode only.",
                                   console_only=False, required=False, shorthand="fs")
    difference_threshold = Argument(.4, '?', float, 'store',
                                    "Per-pixel difference (in range [0,1.0]) between current and previous frames to "
                                    + "filter out frames that are too much alike. Synced mode only.",
                                    console_only=False, required=False, shorthand="fd")
    manual_filter = Argument(False, '?', 'bool_flag', 'store_true',
                             "Pick which (pre-filtered)frames to use manually" +
                             "one-by-one (use 'a' key to approve). Synced mode only.",
                             console_only=False, required=False, shorthand="fm")
    frame_count_target = Argument(-1, '?', int, 'store',
                                  "Total number of frames (from either camera) to target for calibration usage." +
                                  "Synced mode only.",
                                  console_only=False, required=False, shorthand="ft")
    frame_number_filter = Argument(False, '?', 'bool_flag', 'store_true',
                                   "Use only frame numbers specified in the auxiliary data file.",
                                   console_only=False, required=False, shorthand="fn")
    time_range_hint = Argument(None, 2, int, 'store',
                               "Look at frames only within this time range (in seconds) when seeking exact periods of" +
                               "calibration in all videos. A good hint will decrease the search time, but any frames " +
                               "outside the range hint will not be used. Unsynced mode only.",
                               console_only=False, required=False)
    # ============== CALIBRATION & DISTORTION MODEL CONTROLS ==========================================================#
    max_iterations = Argument(100, '?', int, 'store',
                              "Maximum number of iterations for the stereo  for calibration (optimization) loop.",
                              console_only=False, required=False, shorthand="ci")
    precalibrate_solo = Argument(False, '?', 'bool_flag', 'store_true',
                                 "calibrate each camera individually (in case of stereo calibration) first, then " +
                                 "perform stereo calibration.",
                                 console_only=False, required=False, shorthand="cs")
    stereo_only = Argument(False, '?', 'bool_flag', 'store_true',
                           "Use in conjunction with the input_calibration option. " +
                           "Does nothing for single-camera calibration. Synced mode only.",
                           console_only=False, required=False, shorthand="cso")
    use_rational_model = Argument(False, '?', 'bool_flag', 'store_true',
                                  "Use the newer OpenCV rational model (8 distortion coefficients w/ tangential " +
                                  "ones, 6 without) as opposed to the old 3+2 polynomial coefficient model.",
                                  console_only=False, required=False, shorthand="cr")
    use_tangential_coeffs = Argument(False, '?', 'bool_flag', 'store_true',
                                     "Use tangential distortion coefficients (usually unnecessary).",
                                     console_only=False, required=False, shorthand="ct")
    use_thin_prism = Argument(False, '?', 'bool_flag', 'store_true',
                              "Use thin prism coefficients / model",
                              console_only=False, required=False, shorthand="cp")
    fix_thin_prism = Argument(False, '?', 'bool_flag', 'store_true',
                              "Fix the thin prism coefficients",
                              console_only=False, required=False, shorthand="cfp")
    fix_radial = Argument(False, '?', 'bool_flag', 'store_true',
                          "Fix radial distortion coefficients",
                          console_only=False, required=False, shorthand="cfr")
    # TODO: test fisheye
    use_fisheye_model = Argument(False, '?', 'bool_flag', 'store_true',
                                 "Use the fisheye distortion model.",
                                 console_only=False, required=False, shorthand="cf")
    test = Argument(False, '?', 'bool_flag', 'store_true',
                    "Will fix all calibration parameters and run only one iteration, " +
                    "in order to simply print out the reprojection error. Does not save results.")
    # ============== TIME SYNCHRONIZATION CONTROLS ====================================================================#
    unsynced = Argument(False, '?', 'bool_flag', 'store_true',
                        "Used to find extrinsics between multiple unsynchronized cameras."
                        "The multiple videos need to contain a long sequence of frames" +
                        "with the calibration board taken during the same session with all " +
                        "cameras in static positions relative to each-other. However, you must supply reliable " +
                        "intrinsics for each camera (see input_calibration) and an appropriate max_frame_offset. ",
                        console_only=False, required=False)
    max_frame_offset = Argument(100, '?', int, 'store',
                                "Used for unsynced calibration only: maximum delay, in frames, between videos.",
                                console_only=False, required=False)
    seek_miss_count = Argument(5, '?', int, arg_help="Increase sensitivity and seek time of calibration intervals")
    use_all_frames = Argument(False, '?', 'bool_flag', 'store_true', 'Use all frames (skips calibration seeking)')
    # ============== VERBOSITY CONTROLS   =============================================================================#
    skip_printing_output = Argument(False, '?', 'bool_flag', 'store_true',
                                    "Skip printing output.",
                                    console_only=False, required=False)

    @staticmethod
    def generate_missing_shorthands():
        for item in Setting:
            if item.value.shorthand is None:
                item.value.shorthand = "-" + "".join([item[1] for item in re.findall(r"(:?^|_)(\w)", item.name)])

    @staticmethod
    def generate_defaults_dict():
        """
        @rtype: dict
        @return: dictionary of Setting defaults
        """
        dict = {}
        for item in Setting:
            dict[item.name] = item.value.default
        return dict

    @staticmethod
    def generate_parser(defaults, console_only=False, description="Description N/A", parents=None):
        """
        @rtype: argparse.ArgumentParser
        @return: either a console-only or a config_file+console parser using the specified defaults and, optionally,
        parents.
        @type defaults: dict
        @param defaults: dictionary of default settings and their values.
        For a conf-file+console parser, these come from the config file. For a console-only parser, these are generated.
        @type console_only: bool
        @param console_only: accept only command-line/terminal arguments, not a configuration file
        @type description: str
        @param description: description of the program that uses the parser, to be used in the help file
        @type parents: list[argparse.ArgumentParser] | None

        """
        if console_only:
            parser = ap.ArgumentParser(description=description, formatter_class=ap.RawDescriptionHelpFormatter,
                                       add_help=False)
        else:
            if parents is None:
                raise ValueError("A conf-file+console parser requires at least a console-only parser as a parent.")
            parser = ap.ArgumentParser(parents=parents)

        for item in Setting:
            if (item.value.console_only and console_only) or (not item.value.console_only and not console_only):
                if item.value.type == 'bool_flag':
                    parser.add_argument(item.value.shorthand, '--' + item.name, action=item.value.action,
                                        default=defaults[item.name], required=item.value.required,
                                        help=item.value.help)
                else:
                    parser.add_argument(item.value.shorthand, '--' + item.name, action=item.value.action,
                                        type=item.value.type, nargs=item.value.nargs, required=item.value.required,
                                        default=defaults[item.name], help=item.value.help)
        if not console_only:
            parser.set_defaults(**defaults)
        return parser


def load_app_from_config(path):
    """
    Generate app directly from config file, bypassing command line settings (useful for testing in ipython)
    """
    Setting.generate_missing_shorthands()
    defaults = Setting.generate_defaults_dict()
    if osp.isfile(path):
        file_stream = open(path, "r", encoding="utf-8")
        config_defaults = load(file_stream, Loader=Loader)
        file_stream.close()
        for key, value in config_defaults.items():
            defaults[key] = value
    else:
        raise ValueError("Settings file not found at: {0:s}".format(path))
    args = ap.Namespace()
    for key, value in defaults.items():
        args.__dict__[key] = value
    if args.unsynced:
        app = ApplicationUnsynced(args)
    else:
        app = ApplicationSynced(args)
    return app


def main():
    Setting.generate_missing_shorthands()
    defaults = Setting.generate_defaults_dict()
    conf_parser = \
        Setting.generate_parser(defaults, console_only=True, description=
        "Use one or more .mp4 video files to perform calibration: " +
        "find the cameras' intrinsics and/or extrinsics.")

    # ============== STORAGE/RETRIEVAL OF CONSOLE SETTINGS ===========================================#
    args, remaining_argv = conf_parser.parse_known_args()
    defaults[Setting.save_settings.name] = args.save_settings
    if args.settings_file:
        defaults[Setting.settings_file.name] = args.settings_file
        if osp.isfile(args.settings_file):
            file_stream = open(args.settings_file, "r", encoding="utf-8")
            config_defaults = load(file_stream, Loader=Loader)
            file_stream.close()
            for key, value in config_defaults.items():
                defaults[key] = value
        else:
            raise ValueError("Settings file not found at: {0:s}".format(args.settings_file))

    parser = Setting.generate_parser(defaults, parents=[conf_parser])
    args = parser.parse_args(remaining_argv)

    # process "special" setting values
    if args.folder == "!settings_file_location":
        if args.settings_file and osp.isfile(args.settings_file):
            args.folder = osp.dirname(args.settings_file)

    # save settings if prompted to do so
    if args.save_settings and args.settings_file:
        setting_dict = vars(args)
        file_stream = open(args.settings_file, "w", encoding="utf-8")
        file_name = setting_dict[Setting.save_settings.name]
        del setting_dict[Setting.save_settings.name]
        del setting_dict[Setting.settings_file.name]
        dump(setting_dict, file_stream, Dumper=Dumper)
        file_stream.close()
        setting_dict[Setting.save_settings.name] = file_name
        setting_dict[Setting.settings_file.name] = True

    if args.unsynced:
        app = ApplicationUnsynced(args)
        app.gather_frame_data()
        app.calibrate_time_reprojection(save_data=True)
    else:
        app = ApplicationSynced(args)
        app.gather_frame_data()
        app.run_calibration()
    return 0


if __name__ == "__main__":
    sys.exit(main())
