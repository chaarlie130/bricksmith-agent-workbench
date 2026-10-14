with open("scripts/test_catalog_builder.py") as f:
    text = f.read()

bad = """if not res.get("passed"):
    for err in res.get("errors", []):
        if "component_members" in err:
            for c in err["component_members"]:
                for err in res.get("errors", []):
        if err.get("kind") == "gravity_equilibrium_infeasible":
            print("EQ details:", err.get("details"))
    print("Disconnected comp:", [ce.lines[idx+4].strip() for idx in c if idx+4 < len(ce.lines)])"""

good = """if not res.get("passed"):
    for err in res.get("errors", []):
        if err.get("kind") == "gravity_equilibrium_infeasible":
            print("EQ details:", err.get("details"))
        if "component_members" in err:
            for c in err["component_members"]:
                print("Disconnected comp:", [ce.lines[idx+4].strip() for idx in c if idx+4 < len(ce.lines)])"""

text = text.replace(bad, good)
with open("scripts/test_catalog_builder.py", "w") as f:
    f.write(text)

