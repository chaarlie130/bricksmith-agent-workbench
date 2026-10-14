with open("scripts/test_full_cathedral.py") as f:
    text = f.read()

# Don't unlink if error
text = text.replace("p.unlink()", """if not res.get("passed"):
    for err in res.get("errors", []):
        if "line_pairs" in err:
            for lp in err["line_pairs"]:
                print(f"COLLISION: {lines[lp[0]-1].strip()} VS {lines[lp[1]-1].strip()}")
else:
    p.unlink()""")

with open("scripts/test_full_cathedral.py", "w") as f:
    f.write(text)

