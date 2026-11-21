from bricksmith.workbench.omr import fetch_omr_file

text = fetch_omr_file("21030-1")
with open("21030-1.mpd", "w") as f:
    f.write(text)
