# -*- coding: utf-8 -*-
"""
Created on Wed Sep 29 17:44:48 2021

@author: Coralie
"""

import csv
import datetime
import glob
import os
import random
import sys
import wave
from math import floor
from pathlib import Path

import numpy as np
import pyaudio
import scipy.io.wavfile as wav
from psychopy import core, event, gui, prefs, visual

prefs.general["audioLib"] = ["pyo"]


def get_stim_info(file_name, folder):
    # read stimulus information stored in same folder as file_name, with a .txt extension
    # returns a list of values
    info_file_name = os.path.join(folder, os.path.splitext(file_name)[0] + ".txt")
    info = []
    with open(info_file_name, "r") as file:
        reader = csv.reader(file)
        for row in reader:
            info.append(row)
    return info


def generate_trial_files(
    condition="rise",
    subject_number=1,
    n_blocks=3,
    n_stims=400,
    n_stims_total=1200,
    deviant_proportion=0.2,
    initial_standard=5,
    minimum_standard=3,
    isi=0.6,
    block_wait=10,
):
    # generates n_block trial files per subject
    # each block contains n_stim trials, randomized from folder which name is inferred from subject_number
    # returns an array of n_block file names

    condition_folder = PARAMS[condition]["folder"]

    # glob all deviant files in stim folder
    sound_folder = root_path + "/sounds/%s/" % (condition_folder)
    deviant_files = [
        "sounds/%s/" % (condition_folder) + os.path.basename(x)
        for x in glob.glob(sound_folder + "/deviant_*.wav")
    ]
    n_deviants = len(deviant_files)  # normally 1 (rough or tone)
    print("Found %d types of deviants" % (n_deviants))

    # glob standard files in stim folder
    standard_files = [
        "sounds/%s/" % (condition_folder) + os.path.basename(x)
        for x in glob.glob(sound_folder + "/standard_*.wav")
    ]
    print("Found %d type(s) of standard(s) (expected: 1)" % (len(standard_files)))
    standard_file = standard_files[0]

    # generate list of deviants containing of n_total_stims * deviant_proportion stims
    if (
        n_stims_total * deviant_proportion < n_deviants
    ):  # if we need less deviant than n_deviant, do nothing
        deviant_file_list = deviant_files
    else:  # duplicate the nb of deviants
        deviant_file_list = deviant_files * (
            floor(n_stims_total * deviant_proportion / n_deviants)
        )  # this ensures that we have the same proportion of all deviants
    random.shuffle(deviant_file_list)

    # generate list of trials, with the constraint that each deviant is preceded by at least "minimum_standard" standards
    stim_list = [
        [standard_file] * minimum_standard + [dev] for dev in deviant_file_list
    ]

    # add the rest of standards (with the exception of the first initial_standards, to be added later)
    n_trials_so_far = len([trial for trial_pair in stim_list for trial in trial_pair])
    if n_stims_total > n_trials_so_far + initial_standard:
        stim_list += [[standard_file]] * (
            n_stims_total - n_trials_so_far - initial_standard
        )

    # shuffle and flatten
    random.shuffle(stim_list)

    # add beginning initial_standards
    stim_list = [[standard_file]] * initial_standard + stim_list

    # flatten list
    stim_list = [trial for trial_pair in stim_list for trial in trial_pair]

    sequence_analytics(stim_list, isi=isi, n_blocks=n_blocks, block_wait=block_wait)

    # write trials by blocks of n_stims
    trial_files = []
    for block, block_num in blockify(stim_list, n_stims):
        trial_file = Path(
            root_path
            + "/trials/%s/trials_subj%d" % (condition_folder, subject_number)
            + "_condition_"
            + condition
            + "_block"
            + str(block_num + 1)
            + "_"
            + date.strftime("%y%m%d_%H.%M")
            + ".csv"
        )
        trial_file.parent.mkdir(parents=True, exist_ok=True)
        print("generate trial file ", trial_file)
        trial_files.append(trial_file)
        with open(trial_file, "w+", newline="") as file:
            # write header
            writer = csv.writer(file)
            writer.writerow(["Stimulus"])
            # write trials of the block
            for item in block:
                writer.writerow([item])
    return trial_files, standard_file


def sequence_analytics(stim_list, isi=0.6, n_blocks=1, block_wait=20):
    # provides analytics about the sequence: how many stims of each type, and estimate total duration
    print("*******************************************")
    print("Sequence analytics")
    print("*******************************************")

    print("Sequence of size %d" % len(stim_list))
    stims = np.unique(stim_list)
    print("Contains %d stimulus types: " % len(stims))
    duration = 0
    stims, counts = np.unique(stim_list, return_counts=True)
    for [stim, count] in zip(stims, counts):
        print("- %d : %s" % (count, os.path.basename(stim)))
        duration += count * (get_stimulus_duration(stim) + isi)

    print("In %d blocks" % n_blocks)
    duration += (n_blocks - 1) * block_wait

    print("Estimated duration: %s " % str(datetime.timedelta(seconds=duration)))
    print("*******************************************")


def get_stimulus_duration(stim):
    # returns wavfile duration in sec.
    sr, data = wav.read(stim)
    return len(data) / sr


def blockify(x, n_stims):
    # generator to cut a signal into non-overlapping frames
    # returns all complete frames, but a last frame with any trailing samples
    for i in range(len(x) // n_stims):
        start = n_stims * i
        end = n_stims * (i + 1)
        yield (x[start:end], i)
    if end < len(x):
        yield (x[end : len(x)], i + 1)


def read_trials(trial_file):
    # read all trials in a block of trial, stored as a CSV trial file
    with open(trial_file, "r") as fid:
        reader = csv.reader(fid)
        trials = list(reader)
    trials = ["".join(trial) for trial in trials]
    return trials[1:]  # trim header


def generate_result_file(condition, subject_number):

    condition_folder = PARAMS[condition]["folder"]

    result_file = Path(
        root_path
        + "results/%s/results_subj%d" % (condition_folder, subject_number)
        + "_condition_"
        + condition
        + "_"
        + date.strftime("%y%m%d_%H.%M")
        + ".csv"
    )
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_headers = [
        "subject_number",
        "subject_name",
        "sex",
        "age",
        "handedness",
        "date",
        "condition",
        "session",
        "block_number",
        "trial_number",
        "sound_file",
        "stim_type",
        "stim_marker_code",
    ]
    with open(result_file, "w+") as file:
        writer = csv.writer(file)
        writer.writerow(result_headers)
    return result_file


def show_text_and_wait(file_name=None, message=None):
    event.clearEvents()
    if message is None:
        # with codecs.open (file_name, 'r', 'utf-8') as file :
        with open(file_name, "r") as file:
            message = file.read()
    text_object = visual.TextStim(win, text=message, color="white")
    text_object.height = 0.1
    text_object.draw()
    win.flip()
    while True:
        if len(event.getKeys()) > 0:
            core.wait(0.2)
            break
        event.clearEvents()
        core.wait(0.2)
        text_object.draw()
        win.flip()


def show_fixation_cross(message="+", color="deepskyblue"):
    event.clearEvents()
    text_object = visual.TextStim(win, text=message, color=color)
    text_object.height = 0.2
    text_object.draw()
    win.flip()


def play_sound(sound):
    # play sound
    audio = pyaudio.PyAudio()
    #        sr,wave = wav.read(fileName)
    wf = wave.open(sound)

    def play_audio_callback(in_data, frame_count, time_info, status):
        data = wf.readframes(frame_count)
        return (data, pyaudio.paContinue)

    # define data stream for playing audio and start it
    output_stream = audio.open(
        format=audio.get_format_from_width(wf.getsampwidth()),
        channels=wf.getnchannels(),
        rate=wf.getframerate(),
        output=True,
        stream_callback=play_audio_callback,
    )
    output_stream.start_stream()
    while output_stream.is_active():
        core.wait(0.01)
        continue


###########################################################################################
###      DEFINE HOW MANY TRIALS IN HOW MANY BLOCKS
###
###########################################################################################

root_path = "./"
N_STIMS_TOTAL = 500  # total nb of stimuli (dev + std)
DEVIANT_PROPORTION = 0.2
N_BLOCKS = 5
ISI = 0.6  # in sec
JITTER = 0.05  # in sec.
BLOCK_WAIT = 10  # in sec.

ROUGH_PARAMS = {
    "condition": "rough",
    "fixation_cross_color": "deepskyblue",
    "folder": "rough",
    "deviants": ["rough"],
    "markers_codes": {
        "standard": 2,  # standard, roughly 80% of time
        "rough": 5,
    },  # one of 2 types of deviants, with rough vocal characteristics
}

TONE_PARAMS = {
    "condition": "tone",
    "fixation_cross_color": "green",
    "folder": "tone",
    "deviants": ["tone"],
    "markers_codes": {
        "standard": 2,  # standard, roughly 80% of time
        "tone": 8,
    },  # one of 2 types of deviants, a tone
}

PARAMS = {"rough": ROUGH_PARAMS, "tone": TONE_PARAMS}

###########################################################################################

# get participant nb, age, sex
subject_info = {
    u"number": 1,
    u"name": "Bobby",
    u"age": 20,
    u"sex": u"f/m",
    u"handedness": "right",
    u"condition": u"rough/tone",
    u"session": 1,
}
dlg = gui.DlgFromDict(
    subject_info,
    title=u"Own-name",
    order=["number", "condition", "session", "name", "age", "sex", "handedness"],
)
if dlg.OK:
    subject_number = subject_info[u"number"]
    subject_name = subject_info[u"name"]
    subject_age = subject_info[u"age"]
    subject_sex = subject_info[u"sex"]
    subject_handedness = subject_info[u"handedness"]
    condition = subject_info[u"condition"]
    session = subject_info[u"session"]
else:
    core.quit()  # the user hit cancel so exit
date = datetime.datetime.now()
time = core.Clock()

# retrieve condition parameters
if not condition in PARAMS:
    raise AssertionError("Can't find condition: " + condition)
params = PARAMS[condition]

# check if stimulus folder exists
stimulus_folder = root_path + "sounds/%s/" % (params["folder"])
if not os.path.exists(stimulus_folder):
    raise AssertionError("Can't find stimulus folder: %s " % (stimulus_folder))

# create psychopy black window where to show instructions
win = visual.Window(np.array([1920, 1080]), fullscr=False, color="black", units="norm")

# generate data files
result_file = generate_result_file(
    condition, subject_number
)  # renvoie 1 filename en csv

trial_files, standard_file = generate_trial_files(
    condition=condition,
    subject_number=subject_number,
    n_blocks=N_BLOCKS,
    n_stims=round(N_STIMS_TOTAL / N_BLOCKS),
    n_stims_total=N_STIMS_TOTAL,
    deviant_proportion=DEVIANT_PROPORTION,
    isi=ISI,
    block_wait=BLOCK_WAIT,
)

# start_experiment
show_text_and_wait(file_name=root_path + "intro.txt")
trial_count = 0
n_blocks = len(trial_files)
for block_count, trial_file in enumerate(trial_files):

    show_fixation_cross(message="+", color=params["fixation_cross_color"])
    # show_video()

    block_trials = read_trials(trial_file)

    for trial in block_trials:
        row = [
            subject_number,
            subject_name,
            subject_age,
            subject_sex,
            subject_handedness,
            date,
            condition,
            session,
            block_count + 1,
            trial_count + 1,
        ]
        sound = root_path + trial

        # find stim stype from stimulus filename
        if "standard" in trial:
            stim_type = "standard"
        else:
            for deviant in params["deviants"]:
                if deviant in os.path.basename(trial):
                    stim_type = deviant

        # send stim marker
        stim_marker_code = params["markers_codes"][stim_type]
        print("%s: " % stim_type, end="")

        # play sound
        print("file: %s:" % sound)
        play_sound(sound)

        # wait ISI
        core.wait(ISI + random.uniform(-JITTER, JITTER))

        # log trial in result_file
        with open(result_file, "a") as file:
            writer = csv.writer(file, lineterminator="\n")
            result = row + [trial, stim_type, stim_marker_code]
            writer.writerow(result)

        trial_count += 1

    # pause at the end of subsequent blocks
    if block_count < n_blocks - 1:
        print("<<< BLOCK WAIT >>>")
        core.wait(BLOCK_WAIT)
        # show_text_and_wait(message = "Vous avez fait "+str(Fraction(block_count+1, n_blocks))+ " de l'experience. \n Nous vous proposons de faire une pause. \n\n (Veuillez attendre l'experimentateur pour reprendre l'experience).")


# End of experiment
show_text_and_wait(root_path + "end.txt")

# Close Python
win.close()
core.quit()
sys.exit()
