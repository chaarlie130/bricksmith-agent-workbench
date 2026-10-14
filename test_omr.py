from bricksmith.workbench.omr import search_omr, fetch_omr_file

results = search_omr("United States Capitol")
print("Search results:")
for r in results:
    print(r)
