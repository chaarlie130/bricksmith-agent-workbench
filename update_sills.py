lines = open("scripts/build_reichstag.py").read().splitlines()
out = []
for line in lines:
    out.append(line)
    if 'me.place("3023", TRANS_CLEAR, kx, 8, py, "R0")' in line:
        out.append('                me.place("50746", DARK_TAN, kx, 7, py, "R180")')
        out.append('                me.place("50746", DARK_TAN, kx+1, 7, py, "R180")')
    elif 'me.place("3023", TRANS_CLEAR, 4, mz, py, "R90")' in line:
        out.append('                me.place("50746", DARK_TAN, 3, mz, py, "R270")')
        out.append('                me.place("50746", DARK_TAN, 3, mz+1, py, "R270")')
    elif 'me.place("3023", TRANS_CLEAR, 59, mz, py, "R90")' in line:
        out.append('                me.place("50746", DARK_TAN, 60, mz, py, "R90")')
        out.append('                me.place("50746", DARK_TAN, 60, mz+1, py, "R90")')
    elif 'me.place("3023", TRANS_CLEAR, kx, 47, py, "R0")' in line:
        out.append('                me.place("50746", DARK_TAN, kx, 48, py, "R0")')
        out.append('                me.place("50746", DARK_TAN, kx+1, 48, py, "R0")')
open("scripts/build_reichstag.py", "w").write("\n".join(out))
